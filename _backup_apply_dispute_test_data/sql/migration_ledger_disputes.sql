-- =====================================================================
-- Crescopus: CrescoLedger disputes, entry history, and the AI-summary
--            free trial
-- Run in the Supabase SQL editor after migration_ledger_time_goodwill.sql.
-- Safe to re-run.
--
--   1. ledger_entry_events   - a history of every change to every entry
--                              (who and when), written by a trigger
--   2. voided entries        - stay visible but leave the totals
--   3. ledger_disputes (+ entries, messages, proposals)
--   4. a lock: entries in an open dispute can't be changed, except by an
--      agreed resolution
--   5. functions for every dispute step
--   6. ai_usage / account_entitlements / premium_interest for the AI
--      summary: 3 free per account, then premium (premium_until)
--   7. RLS on every new table (read-only; writes go through functions,
--      or the server for AI summaries)
--
-- Rules:
--   - Either party raises a dispute about one or more entries of their
--     ledger (not voided, not already in an open dispute).
--   - Disputed entries keep counting in the totals, flagged "in dispute".
--   - Either party proposes a resolution; the other agrees it, and it's
--     applied there and then: keep, correct the amount/hours, void, or
--     change Recoverable / Goodwill.
--   - The raiser can withdraw it. Either party can close it as unresolved
--     once the other has said nothing for 14 days.
-- =====================================================================


-- ---------- 1. Entry history -------------------------------------------

create table if not exists ledger_entry_events (
  id              uuid primary key default gen_random_uuid(),
  partnership_id  uuid not null references partnerships(id) on delete cascade,
  entry_id        uuid not null,          -- no FK: history outlives a deleted draft
  event           text not null,
  detail          jsonb not null default '{}',
  actor           uuid references profiles(id) on delete set null,
  created_at      timestamptz not null default now()
);
create index if not exists ledger_entry_events_entry_idx on ledger_entry_events (entry_id, created_at);
create index if not exists ledger_entry_events_partnership_idx on ledger_entry_events (partnership_id, created_at);


-- ---------- 2. Voided entries ------------------------------------------

alter table ledger_entries
  add column if not exists voided_at timestamptz,
  add column if not exists voided_by uuid references profiles(id) on delete set null;


-- ---------- 3. Disputes -------------------------------------------------

create table if not exists ledger_disputes (
  id                uuid primary key default gen_random_uuid(),
  partnership_id    uuid not null references partnerships(id) on delete cascade,
  raised_by         uuid references profiles(id) on delete set null,
  reason            text not null,
  wanted            text,
  status            text not null default 'open'
                    check (status in ('open', 'resolved', 'unresolved', 'withdrawn')),
  closed_by         uuid references profiles(id) on delete set null,
  closed_at         timestamptz,
  close_note        text,
  created_at        timestamptz not null default now(),
  last_activity_at  timestamptz not null default now()
);
create index if not exists ledger_disputes_partnership_idx on ledger_disputes (partnership_id, status);

create table if not exists ledger_dispute_entries (
  dispute_id  uuid not null references ledger_disputes(id) on delete cascade,
  entry_id    uuid not null references ledger_entries(id) on delete cascade,
  primary key (dispute_id, entry_id)
);
create index if not exists ledger_dispute_entries_entry_idx on ledger_dispute_entries (entry_id);

-- kind: statement (each person's first account), reply, ai_summary, system
create table if not exists ledger_dispute_messages (
  id            uuid primary key default gen_random_uuid(),
  dispute_id    uuid not null references ledger_disputes(id) on delete cascade,
  author        uuid references profiles(id) on delete set null,   -- null = AI or system
  kind          text not null check (kind in ('statement', 'reply', 'ai_summary', 'system')),
  body          text not null,
  evidence_url  text,
  created_at    timestamptz not null default now()
);
create index if not exists ledger_dispute_messages_idx on ledger_dispute_messages (dispute_id, created_at);

-- actions: [{"entry_id": ..., "action": "keep"|"correct"|"void"|"class",
--            "amount": n (costs/revenue) | "hours": n (time), "cost_class": ...}]
create table if not exists ledger_dispute_proposals (
  id            uuid primary key default gen_random_uuid(),
  dispute_id    uuid not null references ledger_disputes(id) on delete cascade,
  proposed_by   uuid references profiles(id) on delete set null,
  actions       jsonb not null,
  note          text,
  status        text not null default 'proposed'
                check (status in ('proposed', 'agreed', 'declined', 'withdrawn')),
  responded_by  uuid references profiles(id) on delete set null,
  responded_at  timestamptz,
  created_at    timestamptz not null default now()
);
create index if not exists ledger_dispute_proposals_idx on ledger_dispute_proposals (dispute_id, status);


-- ---------- 6. AI summary trial ----------------------------------------
-- Kept out of profiles, which people can update themselves.

create table if not exists ai_usage (
  id          uuid primary key default gen_random_uuid(),
  profile_id  uuid not null references profiles(id) on delete cascade,
  feature     text not null,
  dispute_id  uuid references ledger_disputes(id) on delete set null,
  created_at  timestamptz not null default now()
);
create index if not exists ai_usage_profile_idx on ai_usage (profile_id, feature);

create table if not exists account_entitlements (
  profile_id     uuid primary key references profiles(id) on delete cascade,
  premium_until  timestamptz,
  updated_at     timestamptz not null default now()
);

create table if not exists premium_interest (
  profile_id  uuid not null references profiles(id) on delete cascade,
  feature     text not null,
  created_at  timestamptz not null default now(),
  primary key (profile_id, feature)
);


-- ---------- helpers -----------------------------------------------------

create or replace function public._open_dispute_for(p_entry_id uuid)
returns uuid
language sql stable security definer set search_path = public as $$
  select d.id from ledger_dispute_entries de
    join ledger_disputes d on d.id = de.dispute_id
   where de.entry_id = p_entry_id and d.status = 'open'
   limit 1;
$$;

create or replace function public._dispute_party(p_dispute_id uuid)
returns ledger_disputes
language plpgsql stable security definer set search_path = public as $$
declare d ledger_disputes;
begin
  select * into d from ledger_disputes where id = p_dispute_id;
  if d.id is null or not is_partnership_party(d.partnership_id) then
    raise exception 'Not a party to this dispute';
  end if;
  return d;
end;
$$;


-- ---------- 4. The lock, and the history trigger ------------------------

create or replace function public.ledger_entry_guard()
returns trigger
language plpgsql security definer set search_path = public as $$
begin
  if current_setting('cresco.resolving', true) = 'on' then
    return coalesce(new, old);
  end if;
  if tg_op = 'UPDATE' then
    -- An agreed hourly rate pricing a rate-pending entry is always allowed.
    if old.hourly_rate is null and new.hourly_rate is not null
       and (to_jsonb(new) - array['hourly_rate', 'rate_id', 'amount', 'updated_at'])
         = (to_jsonb(old) - array['hourly_rate', 'rate_id', 'amount', 'updated_at']) then
      return new;
    end if;
  end if;
  if old.voided_at is not null then
    raise exception 'This entry has been voided, so it can''t be changed';
  end if;
  if _open_dispute_for(old.id) is not null then
    raise exception 'This entry is in an open dispute, so it can''t be changed until the dispute is settled';
  end if;
  return coalesce(new, old);
end;
$$;

drop trigger if exists ledger_entries_guard on ledger_entries;
create trigger ledger_entries_guard
  before update or delete on ledger_entries
  for each row execute function public.ledger_entry_guard();

-- Disputed or voided entries can't be put into a recovery settlement.
create or replace function public.settlement_entry_guard()
returns trigger
language plpgsql security definer set search_path = public as $$
begin
  if exists (select 1 from ledger_entries where id = new.entry_id and voided_at is not null) then
    raise exception 'A voided entry can''t be part of a recovery settlement';
  end if;
  if _open_dispute_for(new.entry_id) is not null then
    raise exception 'An entry in an open dispute can''t be part of a recovery settlement';
  end if;
  return new;
end;
$$;

drop trigger if exists recovery_settlement_entries_guard on recovery_settlement_entries;
create trigger recovery_settlement_entries_guard
  before insert on recovery_settlement_entries
  for each row execute function public.settlement_entry_guard();

create or replace function public.ledger_entry_history()
returns trigger
language plpgsql security definer set search_path = public as $$
declare
  v_event text;
  v_detail jsonb := '{}';
  v_entry ledger_entries;
begin
  if tg_op = 'INSERT' then
    v_entry := new;
    v_event := 'added';
    v_detail := jsonb_build_object('amount', new.amount, 'hours', new.hours, 'cost_class', new.cost_class,
                                   'status', new.status);
  elsif tg_op = 'DELETE' then
    v_entry := old;
    v_event := 'deleted';
    v_detail := jsonb_build_object('amount', old.amount, 'description', old.description);
  else
    v_entry := new;
    if new.voided_at is not null and old.voided_at is null then
      v_event := 'voided';
    elsif current_setting('cresco.resolving', true) = 'on' then
      v_event := 'corrected';
    elsif old.hourly_rate is null and new.hourly_rate is not null and old.hours = new.hours then
      v_event := 'priced';
    elsif new.status = 'confirmed' and old.status <> 'confirmed' then
      v_event := 'confirmed';
    elsif new.status = 'queried' and old.status <> 'queried' then
      v_event := 'queried';
      v_detail := jsonb_build_object('note', new.query_note);
    elsif new.cost_class is distinct from old.cost_class
          and new.amount = old.amount and new.description = old.description then
      v_event := 'reclassified';
    elsif new.class_change_to is not null and old.class_change_to is null then
      v_event := 'class_change_asked';
    elsif new.class_change_to is null and old.class_change_to is not null
          and new.cost_class is not distinct from old.cost_class then
      v_event := 'class_change_cleared';
    elsif (new.amount, new.description, new.entry_date, new.kind, new.party)
          is distinct from (old.amount, old.description, old.entry_date, old.kind, old.party)
          or new.hours is distinct from old.hours or new.receipt_url is distinct from old.receipt_url then
      v_event := 'edited';
    else
      return null;   -- nothing worth recording
    end if;
    if v_event not in ('queried') then
      v_detail := v_detail || jsonb_strip_nulls(jsonb_build_object(
        'amount_from', case when new.amount is distinct from old.amount then old.amount end,
        'amount_to',   case when new.amount is distinct from old.amount then new.amount end,
        'hours_from',  case when new.hours is distinct from old.hours then old.hours end,
        'hours_to',    case when new.hours is distinct from old.hours then new.hours end,
        'class_from',  case when new.cost_class is distinct from old.cost_class then old.cost_class end,
        'class_to',    case when new.cost_class is distinct from old.cost_class then new.cost_class end,
        'rate',        case when new.hourly_rate is distinct from old.hourly_rate then new.hourly_rate end,
        'description', case when new.description is distinct from old.description then new.description end));
    end if;
  end if;
  insert into ledger_entry_events (partnership_id, entry_id, event, detail, actor)
  values (v_entry.partnership_id, v_entry.id, v_event, v_detail, auth.uid());
  return null;
end;
$$;

drop trigger if exists ledger_entries_history on ledger_entries;
create trigger ledger_entries_history
  after insert or update or delete on ledger_entries
  for each row execute function public.ledger_entry_history();

-- Backfill history for entries that existed before this migration.
insert into ledger_entry_events (partnership_id, entry_id, event, detail, actor, created_at)
select e.partnership_id, e.id, 'added',
       jsonb_build_object('amount', e.amount, 'hours', e.hours, 'cost_class', e.cost_class, 'status', 'pending'),
       e.added_by, e.created_at
  from ledger_entries e
 where not exists (select 1 from ledger_entry_events v where v.entry_id = e.id);
insert into ledger_entry_events (partnership_id, entry_id, event, actor, created_at)
select e.partnership_id, e.id, 'confirmed', e.confirmed_by, e.confirmed_at
  from ledger_entries e
 where e.status = 'confirmed' and e.confirmed_at is not null
   and not exists (select 1 from ledger_entry_events v where v.entry_id = e.id and v.event = 'confirmed');


-- Voided entries never count as outstanding.
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
                      and status = 'confirmed' and voided_at is null), 0)
       - coalesce((select sum(amount) from recovery_settlements
                    where partnership_id = p_partnership_id and party = p_party
                      and status = 'agreed'), 0);
end;
$$;


-- ---------- 5. Dispute functions ----------------------------------------

create or replace function public.raise_dispute(
  p_partnership_id uuid, p_entry_ids uuid[], p_reason text, p_wanted text default null
) returns uuid
language plpgsql security definer set search_path = public as $$
declare v_id uuid;
begin
  if not is_partnership_party(p_partnership_id) then
    raise exception 'Not a party to this partnership';
  end if;
  if coalesce(cardinality(p_entry_ids), 0) = 0 then
    raise exception 'Choose the entries the dispute is about';
  end if;
  if coalesce(trim(p_reason), '') = '' then
    raise exception 'Say what you think is wrong';
  end if;
  if exists (select 1 from unnest(p_entry_ids) x(eid)
              where not exists (select 1 from ledger_entries e
                                 where e.id = x.eid and e.partnership_id = p_partnership_id
                                   and e.voided_at is null)) then
    raise exception 'Those entries aren''t all in this ledger';
  end if;
  if exists (select 1 from unnest(p_entry_ids) x(eid) where _open_dispute_for(x.eid) is not null) then
    raise exception 'One of those entries is already in an open dispute';
  end if;

  insert into ledger_disputes (partnership_id, raised_by, reason, wanted)
  values (p_partnership_id, auth.uid(), left(trim(p_reason), 2000), nullif(left(trim(coalesce(p_wanted, '')), 1000), ''))
  returning id into v_id;
  insert into ledger_dispute_entries (dispute_id, entry_id)
  select distinct v_id, eid from unnest(p_entry_ids) x(eid);
  insert into ledger_dispute_messages (dispute_id, author, kind, body)
  values (v_id, auth.uid(), 'statement',
          left(trim(p_reason), 2000) || coalesce(E'\n\nWhat I''d like: ' || nullif(trim(coalesce(p_wanted, '')), ''), ''));
  return v_id;
end;
$$;

create or replace function public.add_dispute_message(p_dispute_id uuid, p_body text, p_evidence_url text default null)
returns uuid
language plpgsql security definer set search_path = public as $$
declare
  d ledger_disputes;
  v_id uuid;
begin
  d := _dispute_party(p_dispute_id);
  if d.status <> 'open' then
    raise exception 'This dispute is closed';
  end if;
  if coalesce(trim(p_body), '') = '' then
    raise exception 'Write your message first';
  end if;
  insert into ledger_dispute_messages (dispute_id, author, kind, body, evidence_url)
  values (p_dispute_id, auth.uid(),
          case when exists (select 1 from ledger_dispute_messages
                             where dispute_id = p_dispute_id and author = auth.uid() and kind = 'statement')
               then 'reply' else 'statement' end,
          left(trim(p_body), 4000), nullif(left(trim(coalesce(p_evidence_url, '')), 500), ''))
  returning id into v_id;
  update ledger_disputes set last_activity_at = now() where id = p_dispute_id;
  return v_id;
end;
$$;

-- Checks a proposal's actions; raises with a readable message if anything's off.
create or replace function public._check_dispute_actions(p_dispute_id uuid, p_actions jsonb)
returns void
language plpgsql stable security definer set search_path = public as $$
declare
  a jsonb;
  e ledger_entries;
begin
  if jsonb_typeof(p_actions) <> 'array' or jsonb_array_length(p_actions) = 0 then
    raise exception 'Choose what should happen to each entry';
  end if;
  for a in select * from jsonb_array_elements(p_actions) loop
    select le.* into e from ledger_entries le
      join ledger_dispute_entries de on de.entry_id = le.id and de.dispute_id = p_dispute_id
     where le.id = (a->>'entry_id')::uuid;
    if e.id is null then
      raise exception 'A proposal can only cover the entries in this dispute';
    end if;
    case a->>'action'
      when 'keep', 'void' then null;
      when 'correct' then
        if e.kind = 'time' then
          if coalesce((a->>'hours')::numeric, 0) <= 0 or (a->>'hours')::numeric > 10000 then
            raise exception 'Enter the corrected hours for "%"', e.description;
          end if;
        elsif coalesce((a->>'amount')::numeric, 0) <= 0 or (a->>'amount')::numeric > 10000000 then
          raise exception 'Enter the corrected amount for "%"', e.description;
        end if;
      when 'class' then
        if e.kind not in ('cost', 'time') or coalesce(a->>'cost_class', '') not in ('recoverable', 'goodwill')
           or a->>'cost_class' = e.cost_class then
          raise exception 'Choose the new class for "%"', e.description;
        end if;
      else
        raise exception 'Choose what should happen to each entry';
    end case;
  end loop;
end;
$$;

create or replace function public.propose_dispute_resolution(p_dispute_id uuid, p_actions jsonb, p_note text default null)
returns uuid
language plpgsql security definer set search_path = public as $$
declare
  d ledger_disputes;
  v_id uuid;
begin
  d := _dispute_party(p_dispute_id);
  if d.status <> 'open' then
    raise exception 'This dispute is closed';
  end if;
  perform _check_dispute_actions(p_dispute_id, p_actions);
  update ledger_dispute_proposals set status = 'withdrawn', responded_by = auth.uid(), responded_at = now()
   where dispute_id = p_dispute_id and proposed_by = auth.uid() and status = 'proposed';
  insert into ledger_dispute_proposals (dispute_id, proposed_by, actions, note)
  values (p_dispute_id, auth.uid(), p_actions, nullif(left(trim(coalesce(p_note, '')), 2000), ''))
  returning id into v_id;
  update ledger_disputes set last_activity_at = now() where id = p_dispute_id;
  return v_id;
end;
$$;

create or replace function public.respond_dispute_resolution(p_proposal_id uuid, p_agree boolean)
returns void
language plpgsql security definer set search_path = public as $$
declare
  pr ledger_dispute_proposals;
  d ledger_disputes;
  a jsonb;
  e ledger_entries;
  v_hours numeric;
  v_amount numeric;
begin
  select * into pr from ledger_dispute_proposals where id = p_proposal_id;
  if pr.id is null then
    raise exception 'That proposal no longer exists';
  end if;
  d := _dispute_party(pr.dispute_id);
  if pr.proposed_by = auth.uid() then
    raise exception 'The other party needs to agree this proposal';
  end if;
  if pr.status <> 'proposed' or d.status <> 'open' then
    raise exception 'This proposal is no longer waiting for an answer';
  end if;

  if not coalesce(p_agree, false) then
    update ledger_dispute_proposals set status = 'declined', responded_by = auth.uid(), responded_at = now()
     where id = p_proposal_id;
    update ledger_disputes set last_activity_at = now() where id = d.id;
    return;
  end if;

  perform _check_dispute_actions(d.id, pr.actions);
  perform set_config('cresco.resolving', 'on', true);
  for a in select * from jsonb_array_elements(pr.actions) loop
    select * into e from ledger_entries where id = (a->>'entry_id')::uuid;
    if a->>'action' = 'void' then
      update ledger_entries set voided_at = now(), voided_by = auth.uid(), updated_at = now() where id = e.id;
    elsif a->>'action' = 'correct' then
      if e.kind = 'time' then
        v_hours := round((a->>'hours')::numeric, 2);
        update ledger_entries
           set hours = v_hours,
               amount = case when hourly_rate is null then 0 else round(v_hours * hourly_rate, 2) end,
               status = 'confirmed', confirmed_by = auth.uid(), confirmed_at = now(), query_note = null,
               updated_at = now()
         where id = e.id;
      else
        v_amount := round((a->>'amount')::numeric, 2);
        update ledger_entries
           set amount = v_amount, original_amount = null, original_currency = null, fx_rate = null,
               status = 'confirmed', confirmed_by = auth.uid(), confirmed_at = now(), query_note = null,
               updated_at = now()
         where id = e.id;
      end if;
    elsif a->>'action' = 'class' then
      update ledger_entries
         set cost_class = a->>'cost_class', class_change_to = null, class_change_by = null, class_change_at = null,
             updated_at = now()
       where id = e.id;
    end if;
    -- 'keep' leaves the entry exactly as it is
  end loop;
  perform set_config('cresco.resolving', 'off', true);

  update ledger_dispute_proposals set status = 'agreed', responded_by = auth.uid(), responded_at = now()
   where id = p_proposal_id;
  update ledger_dispute_proposals set status = 'withdrawn', responded_at = now()
   where dispute_id = d.id and status = 'proposed';
  update ledger_disputes set status = 'resolved', closed_by = auth.uid(), closed_at = now(), last_activity_at = now()
   where id = d.id;
  insert into ledger_dispute_messages (dispute_id, author, kind, body)
  values (d.id, null, 'system', 'Resolved: both people agreed the proposal, and it has been applied to the ledger.');
end;
$$;

create or replace function public.withdraw_dispute_proposal(p_proposal_id uuid)
returns void
language plpgsql security definer set search_path = public as $$
begin
  update ledger_dispute_proposals set status = 'withdrawn', responded_by = auth.uid(), responded_at = now()
   where id = p_proposal_id and proposed_by = auth.uid() and status = 'proposed';
  if not found then
    raise exception 'Only a proposal you made that''s still waiting can be withdrawn';
  end if;
end;
$$;

create or replace function public.withdraw_dispute(p_dispute_id uuid)
returns void
language plpgsql security definer set search_path = public as $$
declare d ledger_disputes;
begin
  d := _dispute_party(p_dispute_id);
  if d.raised_by is distinct from auth.uid() then
    raise exception 'Only the person who raised the dispute can withdraw it';
  end if;
  if d.status <> 'open' then
    raise exception 'This dispute is already closed';
  end if;
  update ledger_dispute_proposals set status = 'withdrawn', responded_at = now()
   where dispute_id = d.id and status = 'proposed';
  update ledger_disputes set status = 'withdrawn', closed_by = auth.uid(), closed_at = now(), last_activity_at = now()
   where id = d.id;
  insert into ledger_dispute_messages (dispute_id, author, kind, body)
  values (d.id, null, 'system', 'Withdrawn by the person who raised it. The entries are unlocked.');
end;
$$;

-- When the other person last did anything in this dispute (or when it was raised).
create or replace function public._other_last_active(p_dispute_id uuid)
returns timestamptz
language sql stable security definer set search_path = public as $$
  select greatest(
    (select created_at from ledger_disputes where id = p_dispute_id),
    (select max(created_at) from ledger_dispute_messages
      where dispute_id = p_dispute_id and author is not null and author <> auth.uid()),
    (select max(created_at) from ledger_dispute_proposals
      where dispute_id = p_dispute_id and proposed_by is not null and proposed_by <> auth.uid()),
    (select max(responded_at) from ledger_dispute_proposals
      where dispute_id = p_dispute_id and responded_by is not null and responded_by <> auth.uid())
  );
$$;

create or replace function public.close_dispute_unresolved(p_dispute_id uuid, p_note text default null)
returns void
language plpgsql security definer set search_path = public as $$
declare d ledger_disputes;
begin
  d := _dispute_party(p_dispute_id);
  if d.status <> 'open' then
    raise exception 'This dispute is already closed';
  end if;
  if _other_last_active(p_dispute_id) > now() - interval '14 days' then
    raise exception 'A dispute can be closed as unresolved once the other person hasn''t responded for 14 days';
  end if;
  update ledger_dispute_proposals set status = 'withdrawn', responded_at = now()
   where dispute_id = d.id and status = 'proposed';
  update ledger_disputes
     set status = 'unresolved', closed_by = auth.uid(), closed_at = now(), last_activity_at = now(),
         close_note = nullif(left(trim(coalesce(p_note, '')), 1000), '')
   where id = d.id;
  insert into ledger_dispute_messages (dispute_id, author, kind, body)
  values (d.id, null, 'system',
          'Closed without agreement after 14 days with no response. The record stays here; the entries are unlocked. '
          || 'If you still need to settle it, an independent mediator can help.');
end;
$$;

create or replace function public.register_premium_interest(p_feature text)
returns void
language sql security definer set search_path = public as $$
  insert into premium_interest (profile_id, feature) values (auth.uid(), left(p_feature, 60))
  on conflict do nothing;
$$;


-- ----- who may call what

revoke execute on function public._open_dispute_for(uuid)        from public, anon, authenticated;
revoke execute on function public._dispute_party(uuid)           from public, anon, authenticated;
revoke execute on function public._check_dispute_actions(uuid, jsonb) from public, anon, authenticated;

revoke execute on function public.raise_dispute(uuid, uuid[], text, text)          from public, anon;
revoke execute on function public.add_dispute_message(uuid, text, text)            from public, anon;
revoke execute on function public.propose_dispute_resolution(uuid, jsonb, text)    from public, anon;
revoke execute on function public.respond_dispute_resolution(uuid, boolean)        from public, anon;
revoke execute on function public.withdraw_dispute_proposal(uuid)                  from public, anon;
revoke execute on function public.withdraw_dispute(uuid)                           from public, anon;
revoke execute on function public._other_last_active(uuid)                         from public, anon;
revoke execute on function public.close_dispute_unresolved(uuid, text)             from public, anon;
revoke execute on function public.register_premium_interest(text)                  from public, anon;
grant  execute on function public.raise_dispute(uuid, uuid[], text, text)          to authenticated;
grant  execute on function public.add_dispute_message(uuid, text, text)            to authenticated;
grant  execute on function public.propose_dispute_resolution(uuid, jsonb, text)    to authenticated;
grant  execute on function public.respond_dispute_resolution(uuid, boolean)        to authenticated;
grant  execute on function public.withdraw_dispute_proposal(uuid)                  to authenticated;
grant  execute on function public.withdraw_dispute(uuid)                           to authenticated;
grant  execute on function public._other_last_active(uuid)                         to authenticated;
grant  execute on function public.close_dispute_unresolved(uuid, text)             to authenticated;
grant  execute on function public.register_premium_interest(text)                  to authenticated;


-- ---------- 7. RLS: read-only for the people involved -------------------

alter table ledger_entry_events      enable row level security;
alter table ledger_disputes          enable row level security;
alter table ledger_dispute_entries   enable row level security;
alter table ledger_dispute_messages  enable row level security;
alter table ledger_dispute_proposals enable row level security;
alter table ai_usage                 enable row level security;
alter table account_entitlements     enable row level security;
alter table premium_interest         enable row level security;

drop policy if exists "Entry history visible to both parties" on ledger_entry_events;
create policy "Entry history visible to both parties"
  on ledger_entry_events for select using (is_partnership_party(partnership_id));

drop policy if exists "Disputes visible to both parties" on ledger_disputes;
create policy "Disputes visible to both parties"
  on ledger_disputes for select using (is_partnership_party(partnership_id));

drop policy if exists "Disputed entries visible to both parties" on ledger_dispute_entries;
create policy "Disputed entries visible to both parties"
  on ledger_dispute_entries for select using (
    exists (select 1 from ledger_disputes d where d.id = dispute_id and is_partnership_party(d.partnership_id)));

drop policy if exists "Dispute messages visible to both parties" on ledger_dispute_messages;
create policy "Dispute messages visible to both parties"
  on ledger_dispute_messages for select using (
    exists (select 1 from ledger_disputes d where d.id = dispute_id and is_partnership_party(d.partnership_id)));

drop policy if exists "Dispute proposals visible to both parties" on ledger_dispute_proposals;
create policy "Dispute proposals visible to both parties"
  on ledger_dispute_proposals for select using (
    exists (select 1 from ledger_disputes d where d.id = dispute_id and is_partnership_party(d.partnership_id)));

drop policy if exists "Own AI usage visible" on ai_usage;
create policy "Own AI usage visible" on ai_usage for select using (profile_id = auth.uid());

drop policy if exists "Own entitlements visible" on account_entitlements;
create policy "Own entitlements visible" on account_entitlements for select using (profile_id = auth.uid());

drop policy if exists "Own premium interest visible" on premium_interest;
create policy "Own premium interest visible" on premium_interest for select using (profile_id = auth.uid());
