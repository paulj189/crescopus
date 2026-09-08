-- Crescopus: clean-slate reset of the public schema.
-- Leaves the Supabase `auth` schema (and existing user accounts) untouched.
-- Run in the Supabase SQL Editor.

begin;

-- 1. Drop the auth trigger that calls handle_new_user(), if it exists
drop trigger if exists on_auth_user_created on auth.users;

-- 2. Drop all tables in public (CASCADE clears dependent views/FKs/policies too).
--    Doing this before touching auth.users removes tables like
--    connection_requests that reference profiles.id, so nothing is left
--    blocking the auth.users delete below.
do $$
declare
  r record;
begin
  for r in (select tablename from pg_tables where schemaname = 'public') loop
    execute 'drop table if exists public.' || quote_ident(r.tablename) || ' cascade';
  end loop;
end $$;

-- 3. Now safe to delete all authenticated users (cascades to sessions/identities/tokens).
--    Only run this if you actually want to wipe test accounts too —
--    for just a couple of accounts, deleting them manually via
--    Dashboard > Authentication > Users is simpler and safer.
delete from auth.users;

-- 3. Drop all custom enum types in public (e.g. stream_type, partnership_status)
do $$
declare
  r record;
begin
  for r in (
    select t.typname
    from pg_type t
    join pg_namespace n on t.typnamespace = n.oid
    where n.nspname = 'public' and t.typtype = 'e'
  ) loop
    execute 'drop type if exists public.' || quote_ident(r.typname) || ' cascade';
  end loop;
end $$;

-- 4. Drop any leftover functions in public (e.g. handle_new_user)
do $$
declare
  r record;
begin
  for r in (
    select p.proname, pg_get_function_identity_arguments(p.oid) as args
    from pg_proc p
    join pg_namespace n on p.pronamespace = n.oid
    where n.nspname = 'public'
  ) loop
    execute 'drop function if exists public.' || quote_ident(r.proname) || '(' || r.args || ') cascade';
  end loop;
end $$;

commit;

-- Sanity check: should return no rows if the wipe worked
select tablename from pg_tables where schemaname = 'public';
