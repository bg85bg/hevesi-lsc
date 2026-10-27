-- NEO24-Hevesi LSC – Edzőknek: adatbázis és jogosultságok
-- Futtasd egyszer a Supabase SQL Editorban (SQL Editor → New query → beillesztés → Run).

-- Tagok: csak ők látják és írják a pályanaptárt. Szerep: 'coach' (edző) vagy 'admin' (vezetőség).
create table if not exists public.members (
  email      text primary key,
  name       text not null default '',
  role       text not null default 'coach' check (role in ('coach', 'admin')),
  created_at timestamptz not null default now()
);

-- Edzésfoglalások. kind = 'once' (egyszeri, date) vagy 'weekly' (hetente, from_date..until_date, a from_date napján).
create table if not exists public.bookings (
  id          uuid primary key default gen_random_uuid(),
  team        text not null,
  pitch       text not null,
  part        text not null default 'full' check (part in ('full', 'A', 'B')),
  start_time  text not null,
  end_time    text not null,
  kind        text not null check (kind in ('once', 'weekly')),
  date        date,
  from_date   date,
  until_date  date,
  skip        date[] not null default '{}',
  note        text not null default '',
  created_by  text not null default lower(coalesce(auth.jwt() ->> 'email', '')),
  created_at  timestamptz not null default now()
);

create or replace function public.is_member() returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.members where email = lower(auth.jwt() ->> 'email'))
$$;

create or replace function public.is_admin() returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.members where email = lower(auth.jwt() ->> 'email') and role = 'admin')
$$;

-- Engedélyek a Data API-hoz (akkor is működik, ha az „Automatically expose new tables” ki van kapcsolva).
-- A tényleges hozzáférést a lenti sorszintű szabályok (RLS) korlátozzák.
grant usage on schema public to anon, authenticated;
grant select, insert, update, delete on public.members, public.bookings to authenticated;
grant execute on function public.is_member(), public.is_admin() to authenticated;

alter table public.members  enable row level security;
alter table public.bookings enable row level security;

drop policy if exists "tagok olvashatják a tagokat" on public.members;
drop policy if exists "vezetőség kezeli a tagokat" on public.members;
create policy "tagok olvashatják a tagokat" on public.members for select to authenticated using (public.is_member());
create policy "vezetőség kezeli a tagokat"  on public.members for all    to authenticated using (public.is_admin()) with check (public.is_admin());

drop policy if exists "tagok olvassák a foglalásokat" on public.bookings;
drop policy if exists "tagok foglalhatnak" on public.bookings;
drop policy if exists "saját vagy vezetőség módosít" on public.bookings;
drop policy if exists "saját vagy vezetőség töröl" on public.bookings;
create policy "tagok olvassák a foglalásokat" on public.bookings for select to authenticated using (public.is_member());
create policy "tagok foglalhatnak"            on public.bookings for insert to authenticated with check (public.is_member() and created_by = lower(auth.jwt() ->> 'email'));
create policy "saját vagy vezetőség módosít"  on public.bookings for update to authenticated
  using (public.is_member() and (created_by = lower(auth.jwt() ->> 'email') or public.is_admin()))
  with check (public.is_member());
create policy "saját vagy vezetőség töröl"    on public.bookings for delete to authenticated
  using (public.is_member() and (created_by = lower(auth.jwt() ->> 'email') or public.is_admin()));

-- Az első vezető: a klubnaptár tulajdonosa. Továbbiakat már a honlap „Felhasználók” fülén lehet felvenni.
insert into public.members (email, name, role) values ('bgabor085@gmail.com', 'Gábor', 'admin')
on conflict (email) do update set role = 'admin';

-- Élő frissítés: ha egy edző foglal, a többiek oldalán azonnal megjelenik.
do $$ begin
  alter publication supabase_realtime add table public.bookings;
exception when duplicate_object then null; end $$;
