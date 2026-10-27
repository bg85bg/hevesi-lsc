-- 2. frissítés: csapatonkénti jogosultság, kapus- és egyéni edzés, összevont korosztályok.
-- Futtasd egyszer a Supabase SQL Editorban (New query → beillesztés → Run).

-- Melyik csapat(ok)nak írhat be edzést az edző. Különleges értékek: 'KAPUS' (kapusedzés), 'EGYENI' (egyéni edzés).
alter table public.members  add column if not exists teams      text[] not null default '{}';
-- Kapus/egyéni edzésnél: kik vesznek részt (pl. „U12–U15 kapusok”, játékos neve).
alter table public.bookings add column if not exists title      text   not null default '';
-- Összevont edzés: a fő csapat mellett ezek a csapatok is edzenek (pl. U12 + U13).
alter table public.bookings add column if not exists with_teams text[] not null default '{}';

create or replace function public.can_book(t text) returns boolean
language sql stable security definer set search_path = public as $$
  select public.is_admin() or exists (
    select 1 from public.members where email = lower(auth.jwt() ->> 'email') and t = any(teams))
$$;
grant execute on function public.can_book(text) to authenticated;

drop policy if exists "tagok foglalhatnak" on public.bookings;
drop policy if exists "saját vagy vezetőség módosít" on public.bookings;
create policy "tagok foglalhatnak" on public.bookings for insert to authenticated
  with check (public.is_member() and created_by = lower(auth.jwt() ->> 'email') and public.can_book(team));
create policy "saját vagy vezetőség módosít" on public.bookings for update to authenticated
  using (public.is_member() and (created_by = lower(auth.jwt() ->> 'email') or public.is_admin()))
  with check (public.is_member() and public.can_book(team));
