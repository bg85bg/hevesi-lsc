-- 3. frissítés: hazai meccsek pályájának kézi beállítása (pl. egyik meccs a műfüvesen, a másik az edzőpályán).
create table if not exists public.match_overrides (
  key        text primary key,            -- csapatkód|dátum, pl. 'U16|2026-10-29'
  team       text not null,
  pitch      text not null,
  part       text not null default 'full' check (part in ('full', 'A', 'B')),
  updated_by text not null default lower(coalesce(auth.jwt() ->> 'email', '')),
  updated_at timestamptz not null default now()
);
grant select, insert, update, delete on public.match_overrides to authenticated;
alter table public.match_overrides enable row level security;
drop policy if exists "tagok olvassák a meccspályákat" on public.match_overrides;
drop policy if exists "csapat edzője vagy vezetőség állítja" on public.match_overrides;
create policy "tagok olvassák a meccspályákat" on public.match_overrides for select to authenticated using (public.is_member());
create policy "csapat edzője vagy vezetőség állítja" on public.match_overrides for all to authenticated
  using (public.is_member() and public.can_book(team)) with check (public.is_member() and public.can_book(team));
do $$ begin
  alter publication supabase_realtime add table public.match_overrides;
exception when duplicate_object then null; end $$;
