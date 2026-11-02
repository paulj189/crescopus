-- ===========================================================================
-- Crescopus: November fixes
-- Run in the Supabase SQL editor. Safe to re-run.
--
--   1. Records when each person has read the CrescoLedger notice.
--   2. Only the Builder sets the ledger currency (still only while empty).
--   3. A plan's first save is version 1 (the blank starter plan isn't counted).
-- ===========================================================================

-- ---------- 1. CrescoLedger notice ----------
alter table profiles add column if not exists ledger_notice_at timestamptz;


-- ---------- 2. Builder sets the ledger currency ----------
create or replace function public.set_ledger_currency(p_partnership_id uuid, p_currency text)
returns void
language plpgsql security definer set search_path = public as $$
begin
  if not exists (select 1 from partnerships
                  where id = p_partnership_id and developer_id = auth.uid()) then
    raise exception 'Only the Builder can choose the ledger currency';
  end if;
  if p_currency !~ '^[A-Z]{3}$' then
    raise exception 'Choose a currency from the list';
  end if;
  if exists (select 1 from ledger_entries where partnership_id = p_partnership_id) then
    raise exception 'The currency can''t be changed once the ledger has entries';
  end if;
  update cresco_plans set ledger_currency = p_currency where partnership_id = p_partnership_id;
end;
$$;

revoke execute on function public.set_ledger_currency(uuid, text) from public, anon;
grant  execute on function public.set_ledger_currency(uuid, text) to authenticated;


-- ---------- 3. First save of a plan is version 1 ----------
-- Every plan starts as a blank version 1. Before, the first save bumped it to
-- version 2, so the first real plan anyone saw was "version 2". Now the first
-- save stays at version 1. (The blank plan can't be agreed to, but any stray
-- sign-off is cleared anyway so nobody "agrees" to content they haven't seen.)
create or replace function public.save_plan(
  p_plan_id uuid, p_needs_html text, p_offers_html text, p_actions jsonb, p_measures jsonb
) returns integer
language plpgsql security definer set search_path = public as $$
declare
  v_version integer;
  v_first   boolean;
begin
  if not is_plan_party(p_plan_id) then
    raise exception 'Not a party to this plan';
  end if;

  v_first := not exists (select 1 from plan_versions where plan_id = p_plan_id);
  if v_first then
    delete from plan_signoffs where plan_id = p_plan_id;
  end if;

  update cresco_plans
     set agreed_needs_html  = p_needs_html,
         agreed_offers_html = p_offers_html,
         version            = case when v_first then version else version + 1 end,
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
