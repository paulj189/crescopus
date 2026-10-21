-- =====================================================================
-- Crescopus: CrescoPlan + CrescoLedger (UI rethink, Oct 2026)
-- Additive migration — safe to run on the live database without a reset.
-- Safe to re-run: every step checks before creating.
--
-- What it does
--   1. Needs / Offers fields on profiles and listings (text + filter tags)
--   2. profile_verifications  — trust badges, written by the server only
--   3. cresco_plans, plan_actions, plan_measures, plan_signoffs,
--      plan_versions            — the shared plan, with version history
--   4. ledger_entries          — the shared ledger
--   5. Functions (RPCs) that do every plan/ledger write, so the rules
--      (who may confirm, version bumps, locking) are enforced in the
--      database, not just in Flask
--   6. RLS on every new table (read-only for the two parties; all
--      writes go through the functions in step 5)
--   7. A plan is created automatically for every partnership, and
--      existing partnerships / revenue reports are backfilled
-- =====================================================================


-- ---------- 1. Needs / Offers --------------------------------------

alter table profiles
  add column if not exists needs_html  text,
  add column if not exists offers_html text,
  add column if not exists needs_tags  text[] not null default '{}',
  add column if not exists offers_tags text[] not null default '{}';

alter table listings
  add column if not exists needs_html  text,
  add column if not exists offers_html text,
  add column if not exists needs_tags  text[] not null default '{}',
  add column if not exists offers_tags text[] not null default '{}';

create index if not exists profiles_needs_tags_idx  on profiles using gin (needs_tags);
create index if not exists profiles_offers_tags_idx on profiles using gin (offers_tags);
create index if not exists listings_needs_tags_idx  on listings using gin (needs_tags);
create index if not exists listings_offers_tags_idx on listings using gin (offers_tags);


-- ---------- 2. Trust badges ----------------------------------------
-- Separate table so users can't award themselves a badge by updating
-- their own profile row. Only the server (secret key) writes here.

create table if not exists profile_verifications (
  profile_id  uuid not null references profiles(id) on delete cascade,
  kind        text not null check (kind in ('email', 'phone', 'id', 'github', 'linkedin', 'app_ownership')),
  verified_at timestamptz not null default now(),
  detail      text,
  primary key (profile_id, kind)
);

alter table profile_verifications enable row level security;

drop policy if exists "Verifications are public" on profile_verifications;
create policy "Verifications are public"
  on profile_verifications for select using (true);
-- No insert/update/delete policies: server-only.


-- ---------- 3. CrescoPlan ------------------------------------------

create table if not exists cresco_plans (
  id                 uuid primary key default gen_random_uuid(),
  partnership_id     uuid not null unique references partnerships(id) on delete cascade,
  agreed_needs_html  text,
  agreed_offers_html text,
  version            integer not null default 1,
  ledger_currency    text not null default 'GBP',
  updated_by         uuid references profiles(id),
  updated_at         timestamptz not null default now(),
  created_at         timestamptz not null default now()
);

create table if not exists plan_actions (
  id         uuid primary key default gen_random_uuid(),
  plan_id    uuid not null references cresco_plans(id) on delete cascade,
  position   integer not null default 0,
  title      text not null,
  owner_role text not null check (owner_role in ('builder', 'grower', 'both')),
  due_date   date,
  status     text not null default 'not_started' check (status in ('not_started', 'in_progress', 'done')),
  updated_at timestamptz not null default now()
);
create index if not exists plan_actions_plan_idx on plan_actions (plan_id, position);

create table if not exists plan_measures (
  id          uuid primary key default gen_random_uuid(),
  plan_id     uuid not null references cresco_plans(id) on delete cascade,
  position    integer not null default 0,
  measure     text not null,
  target      text,
  evidence    text,
  review_date date,
  owner_role  text not null check (owner_role in ('builder', 'grower', 'both'))
);
create index if not exists plan_measures_plan_idx on plan_measures (plan_id, position);

-- One row per person: the version they last agreed to. The plan counts as
-- agreed when both parties' version equals the plan's current version, so
-- any edit automatically "un-agrees" it.
create table if not exists plan_signoffs (
  plan_id    uuid not null references cresco_plans(id) on delete cascade,
  profile_id uuid not null references profiles(id) on delete cascade,
  version    integer not null,
  signed_at  timestamptz not null default now(),
  primary key (plan_id, profile_id)
);

-- Read-only history: a full snapshot every time the plan is saved.
create table if not exists plan_versions (
  id         uuid primary key default gen_random_uuid(),
  plan_id    uuid not null references cresco_plans(id) on delete cascade,
  version    integer not null,
  snapshot   jsonb not null,
  created_by uuid references profiles(id),
  created_at timestamptz not null default now(),
  unique (plan_id, version)
);


-- ---------- 4. CrescoLedger ----------------------------------------

create table if not exists ledger_entries (
  id                        uuid primary key default gen_random_uuid(),
  partnership_id            uuid not null references partnerships(id) on delete cascade,
  entry_date                date not null,
  kind                      text not null check (kind in ('cost', 'revenue')),
  party                     text not null check (party in ('builder', 'grower')),
  description               text not null,
  amount                    numeric(12,2) not null check (amount > 0),
  receipt_url               text,
  source                    text not null default 'manual' check (source in ('manual', 'revenuecat')),
  status                    text not null default 'pending' check (status in ('pending', 'confirmed', 'queried')),
  added_by                  uuid references profiles(id),   -- null = system (e.g. RevenueCat)
  confirmed_by              uuid references profiles(id),
  confirmed_at              timestamptz,
  query_note                text,
  legacy_revenue_report_id  uuid unique,                    -- backfill marker
  created_at                timestamptz not null default now(),
  updated_at                timestamptz not null default now()
);
create index if not exists ledger_entries_partnership_idx on ledger_entries (partnership_id, entry_date desc);


-- ---------- 5. Helper + write functions ----------------------------

create or replace function public.is_partnership_party(pid uuid)
returns boolean
language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from partnerships
    where id = pid and (developer_id = auth.uid() or grower_id = auth.uid())
  );
$$;

create or replace function public.is_plan_party(p_plan_id uuid)
returns boolean
language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from cresco_plans cp
    join partnerships p on p.id = cp.partnership_id
    where cp.id = p_plan_id and (p.developer_id = auth.uid() or p.grower_id = auth.uid())
  );
$$;

-- Saves the whole plan in one go: one version bump, one history snapshot.
-- p_actions:  [{"title","owner_role","due_date","status"}, ...]
-- p_measures: [{"measure","target","evidence","review_date","owner_role"}, ...]
create or replace function public.save_plan(
  p_plan_id uuid, p_needs_html text, p_offers_html text, p_actions jsonb, p_measures jsonb
) returns integer
language plpgsql security definer set search_path = public as $$
declare
  v_version integer;
begin
  if not is_plan_party(p_plan_id) then
    raise exception 'Not a party to this plan';
  end if;

  update cresco_plans
     set agreed_needs_html  = p_needs_html,
         agreed_offers_html = p_offers_html,
         version            = version + 1,
         updated_by         = auth.uid(),
         updated_at         = now()
   where id = p_plan_id
  returning version into v_version;

  delete from plan_actions where plan_id = p_plan_id;
  insert into plan_actions (plan_id, position, title, owner_role, due_date, status)
  select p_plan_id, x.ord, x.title, x.owner_role, x.due_date, coalesce(x.status, 'not_started')
    from rows from (jsonb_to_recordset(coalesce(p_actions, '[]'::jsonb))
                    as (title text, owner_role text, due_date date, status text))
         with ordinality as x(title, owner_role, due_date, status, ord)
   where coalesce(trim(x.title), '') <> '';

  delete from plan_measures where plan_id = p_plan_id;
  insert into plan_measures (plan_id, position, measure, target, evidence, review_date, owner_role)
  select p_plan_id, x.ord, x.measure, x.target, x.evidence, x.review_date, x.owner_role
    from rows from (jsonb_to_recordset(coalesce(p_measures, '[]'::jsonb))
                    as (measure text, target text, evidence text, review_date date, owner_role text))
         with ordinality as x(measure, target, evidence, review_date, owner_role, ord)
   where coalesce(trim(x.measure), '') <> '';

  insert into plan_versions (plan_id, version, snapshot, created_by)
  select p_plan_id, v_version,
         jsonb_build_object(
           'agreed_needs_html',  p_needs_html,
           'agreed_offers_html', p_offers_html,
           'actions',  (select coalesce(jsonb_agg(to_jsonb(a) order by a.position), '[]'::jsonb)
                          from plan_actions a where a.plan_id = p_plan_id),
           'measures', (select coalesce(jsonb_agg(to_jsonb(m) order by m.position), '[]'::jsonb)
                          from plan_measures m where m.plan_id = p_plan_id)
         ),
         auth.uid();

  return v_version;
end;
$$;

-- Progress updates on an action don't change what was agreed, so no version bump.
create or replace function public.set_action_status(p_action_id uuid, p_status text)
returns void
language plpgsql security definer set search_path = public as $$
declare
  v_plan_id uuid;
begin
  select plan_id into v_plan_id from plan_actions where id = p_action_id;
  if v_plan_id is null or not is_plan_party(v_plan_id) then
    raise exception 'Not a party to this plan';
  end if;
  update plan_actions set status = p_status, updated_at = now() where id = p_action_id;
end;
$$;

-- Agree to a specific version; refuses if the plan changed in the meantime.
create or replace function public.agree_plan(p_plan_id uuid, p_version integer)
returns void
language plpgsql security definer set search_path = public as $$
declare
  v_current integer;
begin
  if not is_plan_party(p_plan_id) then
    raise exception 'Not a party to this plan';
  end if;
  select version into v_current from cresco_plans where id = p_plan_id;
  if v_current <> p_version then
    raise exception 'The plan has changed since you opened it — please review the latest version';
  end if;
  insert into plan_signoffs (plan_id, profile_id, version, signed_at)
  values (p_plan_id, auth.uid(), p_version, now())
  on conflict (plan_id, profile_id) do update set version = excluded.version, signed_at = excluded.signed_at;
end;
$$;

create or replace function public.add_ledger_entry(
  p_partnership_id uuid, p_entry_date date, p_kind text, p_party text,
  p_description text, p_amount numeric, p_receipt_url text
) returns uuid
language plpgsql security definer set search_path = public as $$
declare
  v_id uuid;
begin
  if not is_partnership_party(p_partnership_id) then
    raise exception 'Not a party to this partnership';
  end if;
  insert into ledger_entries (partnership_id, entry_date, kind, party, description, amount, receipt_url, added_by)
  values (p_partnership_id, p_entry_date, p_kind, p_party, p_description, p_amount, nullif(trim(p_receipt_url), ''), auth.uid())
  returning id into v_id;
  return v_id;
end;
$$;

-- Only the person who added it, and only before it's confirmed.
-- Editing sends it back to pending for the other side to check again.
create or replace function public.edit_ledger_entry(
  p_entry_id uuid, p_entry_date date, p_kind text, p_party text,
  p_description text, p_amount numeric, p_receipt_url text
) returns void
language plpgsql security definer set search_path = public as $$
declare
  e ledger_entries%rowtype;
begin
  select * into e from ledger_entries where id = p_entry_id;
  if e.id is null or e.added_by is distinct from auth.uid() then
    raise exception 'Only the person who added this entry can edit it';
  end if;
  if e.status = 'confirmed' then
    raise exception 'Confirmed entries are locked — add a correcting entry instead';
  end if;
  update ledger_entries
     set entry_date = p_entry_date, kind = p_kind, party = p_party,
         description = p_description, amount = p_amount,
         receipt_url = nullif(trim(p_receipt_url), ''),
         status = 'pending', query_note = null, updated_at = now()
   where id = p_entry_id;
end;
$$;

create or replace function public.delete_ledger_entry(p_entry_id uuid)
returns void
language plpgsql security definer set search_path = public as $$
declare
  e ledger_entries%rowtype;
begin
  select * into e from ledger_entries where id = p_entry_id;
  if e.id is null or e.added_by is distinct from auth.uid() then
    raise exception 'Only the person who added this entry can delete it';
  end if;
  if e.status = 'confirmed' then
    raise exception 'Confirmed entries are locked — add a correcting entry instead';
  end if;
  delete from ledger_entries where id = p_entry_id;
end;
$$;

-- The OTHER party confirms. You can never confirm your own entry.
create or replace function public.confirm_ledger_entry(p_entry_id uuid)
returns void
language plpgsql security definer set search_path = public as $$
declare
  e ledger_entries%rowtype;
begin
  select * into e from ledger_entries where id = p_entry_id;
  if e.id is null or not is_partnership_party(e.partnership_id) then
    raise exception 'Not a party to this partnership';
  end if;
  if e.added_by = auth.uid() then
    raise exception 'The other party needs to confirm this entry';
  end if;
  if e.status = 'confirmed' then
    return;
  end if;
  update ledger_entries
     set status = 'confirmed', confirmed_by = auth.uid(), confirmed_at = now(),
         query_note = null, updated_at = now()
   where id = p_entry_id;
end;
$$;

create or replace function public.query_ledger_entry(p_entry_id uuid, p_note text)
returns void
language plpgsql security definer set search_path = public as $$
declare
  e ledger_entries%rowtype;
begin
  select * into e from ledger_entries where id = p_entry_id;
  if e.id is null or not is_partnership_party(e.partnership_id) then
    raise exception 'Not a party to this partnership';
  end if;
  if e.added_by = auth.uid() then
    raise exception 'You can edit your own entry instead of querying it';
  end if;
  if e.status = 'confirmed' then
    raise exception 'This entry is already confirmed';
  end if;
  update ledger_entries
     set status = 'queried', query_note = p_note, updated_at = now()
   where id = p_entry_id;
end;
$$;

-- Only signed-in users may call the functions above.
revoke execute on function public.save_plan(uuid, text, text, jsonb, jsonb)                          from public, anon;
revoke execute on function public.set_action_status(uuid, text)                                       from public, anon;
revoke execute on function public.agree_plan(uuid, integer)                                           from public, anon;
revoke execute on function public.add_ledger_entry(uuid, date, text, text, text, numeric, text)       from public, anon;
revoke execute on function public.edit_ledger_entry(uuid, date, text, text, text, numeric, text)      from public, anon;
revoke execute on function public.delete_ledger_entry(uuid)                                           from public, anon;
revoke execute on function public.confirm_ledger_entry(uuid)                                          from public, anon;
revoke execute on function public.query_ledger_entry(uuid, text)                                      from public, anon;
grant  execute on function public.save_plan(uuid, text, text, jsonb, jsonb)                          to authenticated;
grant  execute on function public.set_action_status(uuid, text)                                       to authenticated;
grant  execute on function public.agree_plan(uuid, integer)                                           to authenticated;
grant  execute on function public.add_ledger_entry(uuid, date, text, text, text, numeric, text)       to authenticated;
grant  execute on function public.edit_ledger_entry(uuid, date, text, text, text, numeric, text)      to authenticated;
grant  execute on function public.delete_ledger_entry(uuid)                                           to authenticated;
grant  execute on function public.confirm_ledger_entry(uuid)                                          to authenticated;
grant  execute on function public.query_ledger_entry(uuid, text)                                      to authenticated;


-- ---------- 6. RLS: read-only for the two parties ------------------
-- No insert/update/delete policies: all writes go through the functions above.

alter table cresco_plans   enable row level security;
alter table plan_actions   enable row level security;
alter table plan_measures  enable row level security;
alter table plan_signoffs  enable row level security;
alter table plan_versions  enable row level security;
alter table ledger_entries enable row level security;

drop policy if exists "Plan visible to both parties" on cresco_plans;
create policy "Plan visible to both parties"
  on cresco_plans for select using (is_partnership_party(partnership_id));

drop policy if exists "Plan actions visible to both parties" on plan_actions;
create policy "Plan actions visible to both parties"
  on plan_actions for select using (is_plan_party(plan_id));

drop policy if exists "Plan measures visible to both parties" on plan_measures;
create policy "Plan measures visible to both parties"
  on plan_measures for select using (is_plan_party(plan_id));

drop policy if exists "Plan sign-offs visible to both parties" on plan_signoffs;
create policy "Plan sign-offs visible to both parties"
  on plan_signoffs for select using (is_plan_party(plan_id));

drop policy if exists "Plan history visible to both parties" on plan_versions;
create policy "Plan history visible to both parties"
  on plan_versions for select using (is_plan_party(plan_id));

drop policy if exists "Ledger visible to both parties" on ledger_entries;
create policy "Ledger visible to both parties"
  on ledger_entries for select using (is_partnership_party(partnership_id));


-- ---------- 7. Auto-create a plan for each partnership + backfill ---

create or replace function public.create_plan_for_partnership()
returns trigger
language plpgsql security definer set search_path = public as $$
begin
  insert into cresco_plans (partnership_id) values (new.id)
  on conflict (partnership_id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_partnership_created on partnerships;
create trigger on_partnership_created
  after insert on partnerships
  for each row execute function public.create_plan_for_partnership();

insert into cresco_plans (partnership_id)
select id from partnerships
on conflict (partnership_id) do nothing;

-- Existing revenue reports become ledger revenue entries.
-- Verified (RevenueCat) reports arrive confirmed; manual ones arrive pending.
insert into ledger_entries (
  partnership_id, entry_date, kind, party, description, amount,
  source, status, added_by, confirmed_at, legacy_revenue_report_id, created_at
)
select r.partnership_id,
       r.period_end,
       'revenue',
       'builder',
       'Revenue ' || to_char(r.period_start, 'DD Mon YYYY') || ' – ' || to_char(r.period_end, 'DD Mon YYYY'),
       r.gross_amount,
       case when r.source = 'revenuecat' then 'revenuecat' else 'manual' end,
       case when r.verified then 'confirmed' else 'pending' end,
       r.reported_by,
       case when r.verified then r.created_at end,
       r.id,
       r.created_at
  from revenue_reports r
 where r.gross_amount > 0
on conflict (legacy_revenue_report_id) do nothing;
