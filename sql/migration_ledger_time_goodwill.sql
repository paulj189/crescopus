-- =====================================================================
-- Crescopus: time entries, Goodwill / Recoverable, agreed hourly rates,
--            and recovery settlements in the CrescoLedger
-- Run in the Supabase SQL editor after migration_ledger_currency.sql.
-- Safe to re-run.
--
--   1. plan_rates               - hourly rates, proposed by the person whose
--                                 time it is and agreed by the other party
--   2. ledger_entries           - new kind 'time', a cost class
--                                 (recoverable / goodwill), hours and the
--                                 rate saved onto each time entry
--   3. recovery_settlements     - "X has been recovered", proposed by either
--                                 party and agreed by the other
--   4. Functions for every write (the rules live in the database)
--   5. RLS on every new table (read-only; writes go through the functions)
--
-- Rules:
--   - Time entries are always for your own time. With no agreed rate for
--     that date they're saved at zero and show as "rate pending".
--   - A rate starts on the day it's agreed. If the proposer chose "apply to
--     pending entries", it is also given to every rate-pending entry, and to
--     any earlier-dated time logged later that no other rate covers.
--   - Revenue has no class. Costs and time are Recoverable (the default) or
--     Goodwill. Goodwill counts towards contribution but never towards the
--     amount outstanding.
--   - Only the person whose cost/time it is can change its class. Moving to
--     Goodwill needs nobody's consent; moving to Recoverable needs the other
--     party's agreement (unless it's their own entry still awaiting
--     confirmation, which the other party has to confirm anyway).
--   - Nothing is ever recovered automatically. Outstanding = confirmed
--     recoverable costs + time for a party, minus agreed settlements.
-- =====================================================================


-- ---------- 1. Agreed hourly rates ------------------------------------

create table if not exists plan_rates (
  id                uuid primary key default gen_random_uuid(),
  partnership_id    uuid not null references partnerships(id) on delete cascade,
  party             text not null check (party in ('builder', 'grower')),
  hourly_rate       numeric(12,2) not null check (hourly_rate > 0),
  apply_to_pending  boolean not null default false,
  note              text,
  status            text not null default 'proposed'
                    check (status in ('proposed', 'agreed', 'declined', 'withdrawn')),
  effective_from    date,                     -- set to the day it's agreed
  entries_rated     integer,                  -- how many pending entries it priced
  proposed_by       uuid not null references profiles(id),
  responded_by      uuid references profiles(id),
  responded_at      timestamptz,
  created_at        timestamptz not null default now()
);
create unique index if not exists plan_rates_one_open_idx
  on plan_rates (partnership_id, party) where status = 'proposed';
create index if not exists plan_rates_partnership_idx on plan_rates (partnership_id, party, status);


-- ---------- 2. Ledger entries: time + cost class ----------------------

alter table ledger_entries
  add column if not exists cost_class       text,
  add column if not exists hours            numeric(8,2),
  add column if not exists hourly_rate      numeric(12,2),
  add column if not exists rate_id          uuid references plan_rates(id),
  add column if not exists class_change_to  text,
  add column if not exists class_change_by  uuid references profiles(id),
  add column if not exists class_change_at  timestamptz;

-- Existing costs were all treated as recoverable.
update ledger_entries set cost_class = 'recoverable' where kind = 'cost' and cost_class is null;

-- Replace the old kind / amount checks (kind gains 'time'; time can be zero).
do $$
declare c record;
begin
  for c in
    select conname from pg_constraint
     where conrelid = 'public.ledger_entries'::regclass and contype = 'c'
       and conname <> 'ledger_entries_fx_check'
       and (pg_get_constraintdef(oid) ~ '\mkind\M' or pg_get_constraintdef(oid) ~ '\mamount\M >')
  loop
    execute format('alter table ledger_entries drop constraint %I', c.conname);
  end loop;
end $$;

alter table ledger_entries add constraint ledger_entries_kind_v2_check
  check (kind in ('cost', 'revenue', 'time'));

alter table ledger_entries add constraint ledger_entries_amount_v2_check
  check (amount > 0 or (kind = 'time' and amount = 0));

alter table ledger_entries add constraint ledger_entries_class_check check (
  ((kind = 'revenue' and cost_class is null)
   or (kind in ('cost', 'time') and cost_class in ('recoverable', 'goodwill')))
  and (class_change_to is null
       or (class_change_to in ('recoverable', 'goodwill') and class_change_to <> cost_class))
);

alter table ledger_entries add constraint ledger_entries_time_check check (
  (kind = 'time' and hours > 0 and original_currency is null
     and ((hourly_rate is null and rate_id is null and amount = 0)
          or (hourly_rate > 0 and rate_id is not null and amount = round(hours * hourly_rate, 2))))
  or (kind <> 'time' and hours is null and hourly_rate is null and rate_id is null)
);


-- ---------- 3. Recovery settlements -----------------------------------

create table if not exists recovery_settlements (
  id              uuid primary key default gen_random_uuid(),
  partnership_id  uuid not null references partnerships(id) on delete cascade,
  party           text not null check (party in ('builder', 'grower')),  -- whose costs were recovered
  amount          numeric(12,2) not null check (amount > 0),
  settled_on      date not null,
  note            text,
  status          text not null default 'proposed'
                  check (status in ('proposed', 'agreed', 'declined', 'withdrawn')),
  proposed_by     uuid not null references profiles(id),
  responded_by    uuid references profiles(id),
  responded_at    timestamptz,
  created_at      timestamptz not null default now()
);
create index if not exists recovery_settlements_partnership_idx
  on recovery_settlements (partnership_id, party, status);

-- Optional: which entries a settlement covers.
create table if not exists recovery_settlement_entries (
  settlement_id  uuid not null references recovery_settlements(id) on delete cascade,
  entry_id       uuid not null references ledger_entries(id) on delete cascade,
  primary key (settlement_id, entry_id)
);


-- ---------- 4. Functions -----------------------------------------------

-- The caller's role in a partnership ('builder' / 'grower'), or null.
create or replace function public._my_role(p_partnership_id uuid)
returns text
language sql stable security definer set search_path = public as $$
  select case when developer_id = auth.uid() then 'builder'
              when grower_id    = auth.uid() then 'grower' end
    from partnerships where id = p_partnership_id;
$$;

-- The agreed rate for a party's time on a date: the latest rate already in
-- force on that date; failing that, the most recent "apply to pending" rate
-- (which also covers earlier dates). Null = rate pending.
create or replace function public._rate_for(p_partnership_id uuid, p_party text, p_date date)
returns plan_rates
language plpgsql stable security definer set search_path = public as $$
declare r plan_rates;
begin
  select * into r from plan_rates
   where partnership_id = p_partnership_id and party = p_party
     and status = 'agreed' and effective_from <= p_date
   order by effective_from desc, responded_at desc limit 1;
  if r.id is null then
    select * into r from plan_rates
     where partnership_id = p_partnership_id and party = p_party
       and status = 'agreed' and apply_to_pending
     order by responded_at desc limit 1;
  end if;
  return r;
end;
$$;

create or replace function public._check_class(p_class text)
returns text
language plpgsql immutable as $$
begin
  if coalesce(p_class, 'recoverable') not in ('recoverable', 'goodwill') then
    raise exception 'Choose Recoverable or Goodwill';
  end if;
  return coalesce(p_class, 'recoverable');
end;
$$;

-- Builds the stored values for a time entry: (hours, rate, rate_id, amount).
create or replace function public._time_values(
  p_partnership_id uuid, p_party text, p_date date, p_hours numeric,
  out o_hours numeric, out o_rate numeric, out o_rate_id uuid, out o_amount numeric
)
language plpgsql stable security definer set search_path = public as $$
declare r plan_rates;
begin
  if p_hours is null or p_hours <= 0 or p_hours > 10000 then
    raise exception 'Enter the hours, like 3 or 7.5';
  end if;
  o_hours := round(p_hours, 2);
  r := _rate_for(p_partnership_id, p_party, p_date);
  if r.id is null then
    o_rate := null; o_rate_id := null; o_amount := 0;
  else
    o_rate := r.hourly_rate; o_rate_id := r.id; o_amount := round(o_hours * r.hourly_rate, 2);
  end if;
end;
$$;


-- ----- add / edit entries (replace the versions from migration_ledger_currency.sql)

drop function if exists public.add_ledger_entry(uuid, date, text, text, text, numeric, text, numeric, text, numeric);
drop function if exists public.edit_ledger_entry(uuid, date, text, text, text, numeric, text, numeric, text, numeric);

create or replace function public.add_ledger_entry(
  p_partnership_id uuid, p_entry_date date, p_kind text, p_party text,
  p_description text, p_amount numeric, p_receipt_url text,
  p_original_amount numeric default null, p_original_currency text default null, p_fx_rate numeric default null,
  p_cost_class text default null, p_hours numeric default null
) returns uuid
language plpgsql security definer set search_path = public as $$
declare
  v_id uuid;
  v_currency text;
  v_converted boolean;
  v_role text := _my_role(p_partnership_id);
  t record;
begin
  if v_role is null then
    raise exception 'Not a party to this partnership';
  end if;
  if p_kind not in ('cost', 'revenue', 'time') then
    raise exception 'Choose revenue, a cost or time';
  end if;

  if p_kind = 'time' then
    if p_party is distinct from v_role then
      raise exception 'You can only log your own time';
    end if;
    select * into t from _time_values(p_partnership_id, v_role, p_entry_date, p_hours);
    insert into ledger_entries (partnership_id, entry_date, kind, party, description, amount,
                                receipt_url, added_by, cost_class, hours, hourly_rate, rate_id)
    values (p_partnership_id, p_entry_date, 'time', v_role, p_description, t.o_amount,
            nullif(trim(p_receipt_url), ''), auth.uid(), _check_class(p_cost_class),
            t.o_hours, t.o_rate, t.o_rate_id)
    returning id into v_id;
    return v_id;
  end if;

  select ledger_currency into v_currency from cresco_plans where partnership_id = p_partnership_id;
  v_converted := p_original_currency is not null and p_original_currency <> v_currency;
  insert into ledger_entries (partnership_id, entry_date, kind, party, description, amount, receipt_url, added_by,
                              original_amount, original_currency, fx_rate, cost_class)
  values (p_partnership_id, p_entry_date, p_kind, p_party, p_description,
          _ledger_amount(v_currency, p_amount, p_original_amount, p_original_currency, p_fx_rate),
          nullif(trim(p_receipt_url), ''), auth.uid(),
          case when v_converted then round(p_original_amount, 2) end,
          case when v_converted then p_original_currency end,
          case when v_converted then p_fx_rate end,
          case when p_kind = 'cost' then _check_class(p_cost_class) end)
  returning id into v_id;
  return v_id;
end;
$$;

create or replace function public.edit_ledger_entry(
  p_entry_id uuid, p_entry_date date, p_kind text, p_party text,
  p_description text, p_amount numeric, p_receipt_url text,
  p_original_amount numeric default null, p_original_currency text default null, p_fx_rate numeric default null,
  p_cost_class text default null, p_hours numeric default null
) returns void
language plpgsql security definer set search_path = public as $$
declare
  e ledger_entries%rowtype;
  v_currency text;
  v_converted boolean;
  v_role text;
  t record;
begin
  select * into e from ledger_entries where id = p_entry_id;
  if e.id is null or e.added_by is distinct from auth.uid() then
    raise exception 'Only the person who added this entry can edit it';
  end if;
  if e.status = 'confirmed' then
    raise exception 'Confirmed entries are locked — add a correcting entry instead';
  end if;
  if p_kind not in ('cost', 'revenue', 'time') then
    raise exception 'Choose revenue, a cost or time';
  end if;
  v_role := _my_role(e.partnership_id);

  if p_kind = 'time' then
    if p_party is distinct from v_role then
      raise exception 'You can only log your own time';
    end if;
    select * into t from _time_values(e.partnership_id, v_role, p_entry_date, p_hours);
    update ledger_entries
       set entry_date = p_entry_date, kind = 'time', party = v_role, description = p_description,
           amount = t.o_amount, hours = t.o_hours, hourly_rate = t.o_rate, rate_id = t.o_rate_id,
           original_amount = null, original_currency = null, fx_rate = null,
           cost_class = _check_class(p_cost_class),
           class_change_to = null, class_change_by = null, class_change_at = null,
           receipt_url = nullif(trim(p_receipt_url), ''),
           status = 'pending', query_note = null, updated_at = now()
     where id = p_entry_id;
    return;
  end if;

  select ledger_currency into v_currency from cresco_plans where partnership_id = e.partnership_id;
  v_converted := p_original_currency is not null and p_original_currency <> v_currency;
  update ledger_entries
     set entry_date = p_entry_date, kind = p_kind, party = p_party,
         description = p_description,
         amount = _ledger_amount(v_currency, p_amount, p_original_amount, p_original_currency, p_fx_rate),
         original_amount   = case when v_converted then round(p_original_amount, 2) end,
         original_currency = case when v_converted then p_original_currency end,
         fx_rate           = case when v_converted then p_fx_rate end,
         hours = null, hourly_rate = null, rate_id = null,
         cost_class = case when p_kind = 'cost' then _check_class(p_cost_class) end,
         class_change_to = null, class_change_by = null, class_change_at = null,
         receipt_url = nullif(trim(p_receipt_url), ''),
         status = 'pending', query_note = null, updated_at = now()
   where id = p_entry_id;
end;
$$;


-- ----- currency: also fixed once a rate has been proposed or agreed

create or replace function public.set_ledger_currency(p_partnership_id uuid, p_currency text)
returns void
language plpgsql security definer set search_path = public as $$
begin
  if not is_partnership_party(p_partnership_id) then
    raise exception 'Not a party to this partnership';
  end if;
  if p_currency !~ '^[A-Z]{3}$' then
    raise exception 'Choose a currency from the list';
  end if;
  if exists (select 1 from ledger_entries where partnership_id = p_partnership_id) then
    raise exception 'The currency can''t be changed once the ledger has entries';
  end if;
  if exists (select 1 from plan_rates where partnership_id = p_partnership_id
                                        and status in ('proposed', 'agreed')) then
    raise exception 'The currency can''t be changed once an hourly rate has been proposed';
  end if;
  update cresco_plans set ledger_currency = p_currency where partnership_id = p_partnership_id;
end;
$$;


-- ----- hourly rates

-- Propose a rate for your own time. Replaces any rate of yours still waiting.
create or replace function public.propose_rate(
  p_partnership_id uuid, p_hourly_rate numeric, p_apply_to_pending boolean, p_note text default null
) returns uuid
language plpgsql security definer set search_path = public as $$
declare
  v_role text := _my_role(p_partnership_id);
  v_id uuid;
begin
  if v_role is null then
    raise exception 'Not a party to this partnership';
  end if;
  if not exists (select 1 from partnerships where id = p_partnership_id and status in ('trial', 'formalised')) then
    raise exception 'This partnership has ended';
  end if;
  if p_hourly_rate is null or p_hourly_rate <= 0 or p_hourly_rate > 100000 then
    raise exception 'Enter an hourly rate above zero';
  end if;
  update plan_rates set status = 'withdrawn', responded_by = auth.uid(), responded_at = now()
   where partnership_id = p_partnership_id and party = v_role and status = 'proposed';
  insert into plan_rates (partnership_id, party, hourly_rate, apply_to_pending, note, proposed_by)
  values (p_partnership_id, v_role, round(p_hourly_rate, 2), coalesce(p_apply_to_pending, false),
          nullif(trim(p_note), ''), auth.uid())
  returning id into v_id;
  return v_id;
end;
$$;

-- The other party agrees or declines. Agreeing starts the rate today and,
-- if chosen, prices every rate-pending entry. Returns how many it priced.
create or replace function public.respond_rate(p_rate_id uuid, p_agree boolean)
returns integer
language plpgsql security definer set search_path = public as $$
declare
  r plan_rates%rowtype;
  v_count integer := 0;
begin
  select * into r from plan_rates where id = p_rate_id;
  if r.id is null or not is_partnership_party(r.partnership_id) then
    raise exception 'Not a party to this partnership';
  end if;
  if r.proposed_by = auth.uid() then
    raise exception 'The other party needs to agree this rate';
  end if;
  if r.status <> 'proposed' then
    raise exception 'This rate is no longer waiting for an answer';
  end if;

  if not coalesce(p_agree, false) then
    update plan_rates set status = 'declined', responded_by = auth.uid(), responded_at = now()
     where id = p_rate_id;
    return 0;
  end if;

  update plan_rates set status = 'agreed', effective_from = current_date,
                        responded_by = auth.uid(), responded_at = now()
   where id = p_rate_id;

  if r.apply_to_pending then
    update ledger_entries
       set hourly_rate = r.hourly_rate, rate_id = r.id,
           amount = round(hours * r.hourly_rate, 2), updated_at = now()
     where partnership_id = r.partnership_id and party = r.party
       and kind = 'time' and hourly_rate is null;
    get diagnostics v_count = row_count;
  end if;
  update plan_rates set entries_rated = v_count where id = p_rate_id;
  return v_count;
end;
$$;

create or replace function public.withdraw_rate(p_rate_id uuid)
returns void
language plpgsql security definer set search_path = public as $$
begin
  update plan_rates set status = 'withdrawn', responded_by = auth.uid(), responded_at = now()
   where id = p_rate_id and proposed_by = auth.uid() and status = 'proposed';
  if not found then
    raise exception 'Only a rate you proposed that''s still waiting can be withdrawn';
  end if;
end;
$$;


-- ----- Goodwill / Recoverable

-- Only the person whose cost or time it is. Choosing the current class
-- cancels a change waiting for agreement.
create or replace function public.set_cost_class(p_entry_id uuid, p_class text)
returns text   -- 'changed' or 'requested'
language plpgsql security definer set search_path = public as $$
declare
  e ledger_entries%rowtype;
begin
  select * into e from ledger_entries where id = p_entry_id;
  if e.id is null or not is_partnership_party(e.partnership_id) then
    raise exception 'Not a party to this partnership';
  end if;
  if e.kind not in ('cost', 'time') then
    raise exception 'Only costs and time can be Goodwill or Recoverable';
  end if;
  if _my_role(e.partnership_id) is distinct from e.party then
    raise exception 'Only the person whose cost or time this is can change it';
  end if;
  perform _check_class(p_class);

  if p_class = e.cost_class then
    update ledger_entries set class_change_to = null, class_change_by = null, class_change_at = null
     where id = p_entry_id;
    return 'changed';
  end if;

  if p_class = 'goodwill' then
    if exists (select 1 from recovery_settlement_entries se
                 join recovery_settlements s on s.id = se.settlement_id
                where se.entry_id = p_entry_id and s.status in ('proposed', 'agreed')) then
      raise exception 'This entry is part of a recovery settlement, so it stays Recoverable';
    end if;
    update ledger_entries set cost_class = 'goodwill', class_change_to = null,
                              class_change_by = null, class_change_at = null, updated_at = now()
     where id = p_entry_id;
    return 'changed';
  end if;

  -- Goodwill -> Recoverable
  if e.status <> 'confirmed' and e.added_by = auth.uid() then
    update ledger_entries set cost_class = 'recoverable', status = 'pending', query_note = null,
                              class_change_to = null, class_change_by = null, class_change_at = null,
                              updated_at = now()
     where id = p_entry_id;
    return 'changed';
  end if;
  update ledger_entries set class_change_to = 'recoverable', class_change_by = auth.uid(),
                            class_change_at = now()
   where id = p_entry_id;
  return 'requested';
end;
$$;

create or replace function public.respond_class_change(p_entry_id uuid, p_agree boolean)
returns void
language plpgsql security definer set search_path = public as $$
declare
  e ledger_entries%rowtype;
begin
  select * into e from ledger_entries where id = p_entry_id;
  if e.id is null or not is_partnership_party(e.partnership_id) then
    raise exception 'Not a party to this partnership';
  end if;
  if e.class_change_to is null then
    raise exception 'There''s no change waiting on this entry';
  end if;
  if e.class_change_by = auth.uid() then
    raise exception 'The other party needs to agree this change';
  end if;
  update ledger_entries
     set cost_class = case when coalesce(p_agree, false) then e.class_change_to else cost_class end,
         class_change_to = null, class_change_by = null, class_change_at = null,
         updated_at = case when coalesce(p_agree, false) then now() else updated_at end
   where id = p_entry_id;
end;
$$;


-- ----- recovery

-- Confirmed recoverable costs + time for a party, minus agreed settlements.
create or replace function public.recoverable_outstanding(p_partnership_id uuid, p_party text)
returns numeric
language plpgsql stable security definer set search_path = public as $$
begin
  if not is_partnership_party(p_partnership_id) then
    raise exception 'Not a party to this partnership';
  end if;
  return coalesce((select sum(amount) from ledger_entries
                    where partnership_id = p_partnership_id and party = p_party
                      and kind in ('cost', 'time') and cost_class = 'recoverable'
                      and status = 'confirmed'), 0)
       - coalesce((select sum(amount) from recovery_settlements
                    where partnership_id = p_partnership_id and party = p_party
                      and status = 'agreed'), 0);
end;
$$;

-- Either party can propose. p_entry_ids is optional.
create or replace function public.propose_recovery(
  p_partnership_id uuid, p_party text, p_amount numeric, p_settled_on date,
  p_note text default null, p_entry_ids uuid[] default '{}'
) returns uuid
language plpgsql security definer set search_path = public as $$
declare
  v_id uuid;
begin
  if not is_partnership_party(p_partnership_id) then
    raise exception 'Not a party to this partnership';
  end if;
  if p_party not in ('builder', 'grower') then
    raise exception 'Choose whose costs were recovered';
  end if;
  if p_amount is null or p_amount <= 0 then
    raise exception 'Enter an amount above zero';
  end if;
  if p_settled_on is null then
    raise exception 'Add the date it was settled';
  end if;
  if round(p_amount, 2) > recoverable_outstanding(p_partnership_id, p_party) then
    raise exception 'That''s more than the confirmed recoverable amount outstanding';
  end if;
  if exists (select 1 from unnest(coalesce(p_entry_ids, '{}')) as x(eid)
              where not exists (select 1 from ledger_entries le
                                 where le.id = x.eid and le.partnership_id = p_partnership_id
                                   and le.party = p_party and le.kind in ('cost', 'time')
                                   and le.cost_class = 'recoverable' and le.status = 'confirmed')) then
    raise exception 'Only confirmed recoverable entries for that person can be included';
  end if;

  insert into recovery_settlements (partnership_id, party, amount, settled_on, note, proposed_by)
  values (p_partnership_id, p_party, round(p_amount, 2), p_settled_on, nullif(trim(p_note), ''), auth.uid())
  returning id into v_id;
  insert into recovery_settlement_entries (settlement_id, entry_id)
  select distinct v_id, eid from unnest(coalesce(p_entry_ids, '{}')) as x(eid);
  return v_id;
end;
$$;

create or replace function public.respond_recovery(p_settlement_id uuid, p_agree boolean)
returns void
language plpgsql security definer set search_path = public as $$
declare
  s recovery_settlements%rowtype;
begin
  select * into s from recovery_settlements where id = p_settlement_id;
  if s.id is null or not is_partnership_party(s.partnership_id) then
    raise exception 'Not a party to this partnership';
  end if;
  if s.proposed_by = auth.uid() then
    raise exception 'The other party needs to agree this settlement';
  end if;
  if s.status <> 'proposed' then
    raise exception 'This settlement is no longer waiting for an answer';
  end if;
  if coalesce(p_agree, false)
     and s.amount > recoverable_outstanding(s.partnership_id, s.party) then
    raise exception 'That''s now more than the confirmed recoverable amount outstanding';
  end if;
  update recovery_settlements
     set status = case when coalesce(p_agree, false) then 'agreed' else 'declined' end,
         responded_by = auth.uid(), responded_at = now()
   where id = p_settlement_id;
end;
$$;

create or replace function public.withdraw_recovery(p_settlement_id uuid)
returns void
language plpgsql security definer set search_path = public as $$
begin
  update recovery_settlements set status = 'withdrawn', responded_by = auth.uid(), responded_at = now()
   where id = p_settlement_id and proposed_by = auth.uid() and status = 'proposed';
  if not found then
    raise exception 'Only a settlement you proposed that''s still waiting can be withdrawn';
  end if;
end;
$$;


-- ----- who may call what

revoke execute on function public._my_role(uuid)                         from public, anon, authenticated;
revoke execute on function public._rate_for(uuid, text, date)            from public, anon, authenticated;
revoke execute on function public._time_values(uuid, text, date, numeric) from public, anon, authenticated;

revoke execute on function public.add_ledger_entry(uuid, date, text, text, text, numeric, text, numeric, text, numeric, text, numeric)  from public, anon;
revoke execute on function public.edit_ledger_entry(uuid, date, text, text, text, numeric, text, numeric, text, numeric, text, numeric) from public, anon;
revoke execute on function public.set_ledger_currency(uuid, text)                     from public, anon;
revoke execute on function public.propose_rate(uuid, numeric, boolean, text)          from public, anon;
revoke execute on function public.respond_rate(uuid, boolean)                         from public, anon;
revoke execute on function public.withdraw_rate(uuid)                                 from public, anon;
revoke execute on function public.set_cost_class(uuid, text)                          from public, anon;
revoke execute on function public.respond_class_change(uuid, boolean)                 from public, anon;
revoke execute on function public.recoverable_outstanding(uuid, text)                 from public, anon;
revoke execute on function public.propose_recovery(uuid, text, numeric, date, text, uuid[]) from public, anon;
revoke execute on function public.respond_recovery(uuid, boolean)                     from public, anon;
revoke execute on function public.withdraw_recovery(uuid)                             from public, anon;

grant execute on function public.add_ledger_entry(uuid, date, text, text, text, numeric, text, numeric, text, numeric, text, numeric)  to authenticated;
grant execute on function public.edit_ledger_entry(uuid, date, text, text, text, numeric, text, numeric, text, numeric, text, numeric) to authenticated;
grant execute on function public.set_ledger_currency(uuid, text)                     to authenticated;
grant execute on function public.propose_rate(uuid, numeric, boolean, text)          to authenticated;
grant execute on function public.respond_rate(uuid, boolean)                         to authenticated;
grant execute on function public.withdraw_rate(uuid)                                 to authenticated;
grant execute on function public.set_cost_class(uuid, text)                          to authenticated;
grant execute on function public.respond_class_change(uuid, boolean)                 to authenticated;
grant execute on function public.recoverable_outstanding(uuid, text)                 to authenticated;
grant execute on function public.propose_recovery(uuid, text, numeric, date, text, uuid[]) to authenticated;
grant execute on function public.respond_recovery(uuid, boolean)                     to authenticated;
grant execute on function public.withdraw_recovery(uuid)                             to authenticated;


-- ---------- 5. RLS: read-only for the two parties ----------------------

alter table plan_rates                  enable row level security;
alter table recovery_settlements        enable row level security;
alter table recovery_settlement_entries enable row level security;

drop policy if exists "Rates visible to both parties" on plan_rates;
create policy "Rates visible to both parties"
  on plan_rates for select using (is_partnership_party(partnership_id));

drop policy if exists "Settlements visible to both parties" on recovery_settlements;
create policy "Settlements visible to both parties"
  on recovery_settlements for select using (is_partnership_party(partnership_id));

drop policy if exists "Settlement entries visible to both parties" on recovery_settlement_entries;
create policy "Settlement entries visible to both parties"
  on recovery_settlement_entries for select using (
    exists (select 1 from recovery_settlements s
             where s.id = settlement_id and is_partnership_party(s.partnership_id)));
