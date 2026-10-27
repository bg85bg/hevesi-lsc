-- 4. frissítés: Csapatom – játékosok, értékelések, meccskeretek, felállások, jegyzőkönyvek, fotók.
-- Futtasd egyszer a Supabase SQL Editorban (New query → beillesztés → Run).

-- Bajnoki csapatkód → korosztály (az U13 két bajnokságban is játszik, de egy csapat).
create or replace function public.squad_of(code text) returns text
language sql immutable as $$
  select case
    when code in ('F2', 'KUPA', 'MAKL') then 'FELNOTT'
    when code in ('U14R', 'U14H') then 'U14'
    when code in ('U13R', 'U13H') then 'U13'
    else code end
$$;

-- A régi, bajnoksági kódokkal mentett jogosultságok és foglalások átírása korosztályra.
update public.members set teams = coalesce((select array_agg(distinct public.squad_of(x)) from unnest(teams) x), '{}');
update public.bookings set team = public.squad_of(team),
  with_teams = coalesce((select array_agg(distinct public.squad_of(x)) from unnest(with_teams) x), '{}');

-- Az adott korosztályt kezelheti-e (vezetőség mindet, edző a hozzá rendelteket).
create or replace function public.can_squad(sq text) returns boolean
language sql stable security definer set search_path = public as $$
  select public.is_admin() or exists (
    select 1 from public.members where email = lower(auth.jwt() ->> 'email') and public.squad_of(sq) = any(teams))
$$;
create or replace function public.can_book(t text) returns boolean
language sql stable security definer set search_path = public as $$
  select public.can_squad(t)
$$;
grant execute on function public.squad_of(text), public.can_squad(text), public.can_book(text) to authenticated;

-- Játékosok. Minden edző látja (kisegítéshez kell), de csak a korosztály edzője és a vezetőség módosítja.
create table if not exists public.players (
  id         uuid primary key default gen_random_uuid(),
  squad      text not null,
  name       text not null,
  num        text not null default '',
  birth      date,
  foot       text not null default '',
  pos        text[] not null default '{}',
  photo      text not null default '',          -- útvonal a player-photos tárhelyen
  mlsz_id    text unique,
  mlsz       jsonb,                              -- MLSZ-statisztika (a szinkron írja)
  list       text not null default '',
  active     boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Képesség-értékelés és edzői megjegyzés: csak a korosztály edzője és a vezetőség látja.
create table if not exists public.player_evals (
  player_id  uuid primary key references public.players(id) on delete cascade,
  squad      text not null,
  sk         jsonb not null default '{}',
  note       text not null default '',
  updated_by text not null default lower(coalesce(auth.jwt() ->> 'email', '')),
  updated_at timestamptz not null default now()
);

-- Meccskeret és felállás meccsenként. key = bajnoki csapatkód|dátum, pl. 'U13R|2026-10-24'.
create table if not exists public.squad_matches (
  key        text primary key,
  squad      text not null,
  sel        text[] not null default '{}',
  lineup     jsonb not null default '{"f": "3-3-2", "s": ["","","","","","","","",""]}',
  res        text not null default '',
  note       text not null default '',
  updated_by text not null default lower(coalesce(auth.jwt() ->> 'email', '')),
  updated_at timestamptz not null default now()
);

-- Hivatalos jegyzőkönyvek (kezdők, cserék, gólok, lapok) – csak az automatikus szinkron írja.
create table if not exists public.match_reports (
  key        text primary key,
  squad      text not null,
  mlsz_id    text,
  url        text not null default '',
  status     text not null default '',
  start      jsonb not null default '[]',
  subs       jsonb not null default '[]',
  updated_at timestamptz not null default now()
);

grant select, insert, update, delete on public.players, public.player_evals, public.squad_matches to authenticated;
grant select on public.match_reports to authenticated;
grant all on public.players, public.player_evals, public.squad_matches, public.match_reports to service_role;

alter table public.players       enable row level security;
alter table public.player_evals  enable row level security;
alter table public.squad_matches enable row level security;
alter table public.match_reports enable row level security;

drop policy if exists "tagok látják a játékosokat" on public.players;
drop policy if exists "korosztály edzője kezeli a játékosokat" on public.players;
create policy "tagok látják a játékosokat" on public.players for select to authenticated using (public.is_member());
create policy "korosztály edzője kezeli a játékosokat" on public.players for all to authenticated
  using (public.can_squad(squad)) with check (public.can_squad(squad));

drop policy if exists "korosztály edzője kezeli az értékelést" on public.player_evals;
create policy "korosztály edzője kezeli az értékelést" on public.player_evals for all to authenticated
  using (public.can_squad(squad)) with check (public.can_squad(squad));

drop policy if exists "tagok látják a meccskereteket" on public.squad_matches;
drop policy if exists "korosztály edzője kezeli a meccskeretet" on public.squad_matches;
create policy "tagok látják a meccskereteket" on public.squad_matches for select to authenticated using (public.is_member());
create policy "korosztály edzője kezeli a meccskeretet" on public.squad_matches for all to authenticated
  using (public.can_squad(squad)) with check (public.can_squad(squad));

drop policy if exists "tagok látják a jegyzőkönyveket" on public.match_reports;
create policy "tagok látják a jegyzőkönyveket" on public.match_reports for select to authenticated using (public.is_member());

-- Játékosfotók: nem nyilvános tárhely, útvonal: <korosztály>/<játékos-id>.jpg
insert into storage.buckets (id, name, public) values ('player-photos', 'player-photos', false)
on conflict (id) do nothing;
drop policy if exists "tagok látják a fotókat" on storage.objects;
drop policy if exists "korosztály edzője tölt fel fotót" on storage.objects;
drop policy if exists "korosztály edzője módosít fotót" on storage.objects;
drop policy if exists "korosztály edzője töröl fotót" on storage.objects;
create policy "tagok látják a fotókat" on storage.objects for select to authenticated
  using (bucket_id = 'player-photos' and public.is_member());
create policy "korosztály edzője tölt fel fotót" on storage.objects for insert to authenticated
  with check (bucket_id = 'player-photos' and public.can_squad(split_part(name, '/', 1)));
create policy "korosztály edzője módosít fotót" on storage.objects for update to authenticated
  using (bucket_id = 'player-photos' and public.can_squad(split_part(name, '/', 1)));
create policy "korosztály edzője töröl fotót" on storage.objects for delete to authenticated
  using (bucket_id = 'player-photos' and public.can_squad(split_part(name, '/', 1)));

-- Élő frissítés a meccskeretekre (két edző egyszerre szerkeszt).
do $$ begin
  alter publication supabase_realtime add table public.squad_matches;
exception when duplicate_object then null; end $$;
