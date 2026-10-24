-- =====================================================================
-- Crescopus: ledger currency + entries in other currencies
-- Run in the Supabase SQL editor after migration_plan_ledger.sql.
-- Safe to re-run.
--
--   - Each partnership's ledger has one currency (cresco_plans.ledger_currency,
--     GBP by default). Either party can change it while the ledger is empty;
--     once it has entries it's fixed.
--   - An entry can be made in another currency. It then stores the original
--     amount and currency plus the exchange rate, and its "amount" is the
--     converted figure in the ledger currency (worked out here, so the two
--     can never disagree). Totals only ever use the converted amount, and a
--     confirmed entry's rate never changes.
-- =====================================================================

alter table ledger_entries
  add column if not exists original_amount   numeric(14,2),
  add column if not exists original_currency text,
  add column if not exists fx_rate           numeric(18,8);

alter table ledger_entries drop constraint if exists ledger_entries_fx_check;
alter table ledger_entries add constraint ledger_entries_fx_check check (
  (original_currency is null and original_amount is null and fx_rate is null)
  or (original_currency ~ '^[A-Z]{3}$' and original_amount > 0 and fx_rate > 0)
);

alter table cresco_plans drop constraint if exists cresco_plans_currency_check;
alter table cresco_plans add constraint cresco_plans_currency_check check (ledger_currency ~ '^[A-Z]{3}$');


-- ---------- change the ledger currency (only while empty) ----------

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
  update cresco_plans set ledger_currency = p_currency where partnership_id = p_partnership_id;
end;
$$;


-- ---------- add / edit entries, now with an optional conversion ----------
-- Replaces the versions from migration_plan_ledger.sql (same rules, plus the
-- three conversion fields).

drop function if exists public.add_ledger_entry(uuid, date, text, text, text, numeric, text);
drop function if exists public.edit_ledger_entry(uuid, date, text, text, text, numeric, text);

-- Works out the stored amount: the plain amount, or the original amount
-- converted at the given rate. Raises if the conversion details don't add up.
create or replace function public._ledger_amount(
  p_ledger_currency text, p_amount numeric,
  p_original_amount numeric, p_original_currency text, p_fx_rate numeric
) returns numeric
language plpgsql immutable as $$
begin
  if p_original_currency is null or p_original_currency = p_ledger_currency then
    -- Same currency as the ledger: no conversion.
    if coalesce(p_amount, p_original_amount) is null or coalesce(p_amount, p_original_amount) <= 0 then
      raise exception 'Enter an amount above zero';
    end if;
    return round(coalesce(p_amount, p_original_amount), 2);
  end if;
  if p_original_currency !~ '^[A-Z]{3}$' then
    raise exception 'Choose a currency from the list';
  end if;
  if p_original_amount is null or p_original_amount <= 0 then
    raise exception 'Enter an amount above zero';
  end if;
  if p_fx_rate is null or p_fx_rate <= 0 then
    raise exception 'Enter the exchange rate';
  end if;
  if round(p_original_amount * p_fx_rate, 2) <= 0 then
    raise exception 'That converts to less than one penny';
  end if;
  return round(p_original_amount * p_fx_rate, 2);
end;
$$;

create or replace function public.add_ledger_entry(
  p_partnership_id uuid, p_entry_date date, p_kind text, p_party text,
  p_description text, p_amount numeric, p_receipt_url text,
  p_original_amount numeric default null, p_original_currency text default null, p_fx_rate numeric default null
) returns uuid
language plpgsql security definer set search_path = public as $$
declare
  v_id uuid;
  v_currency text;
  v_converted boolean;
begin
  if not is_partnership_party(p_partnership_id) then
    raise exception 'Not a party to this partnership';
  end if;
  select ledger_currency into v_currency from cresco_plans where partnership_id = p_partnership_id;
  v_converted := p_original_currency is not null and p_original_currency <> v_currency;
  insert into ledger_entries (partnership_id, entry_date, kind, party, description, amount, receipt_url, added_by,
                              original_amount, original_currency, fx_rate)
  values (p_partnership_id, p_entry_date, p_kind, p_party, p_description,
          _ledger_amount(v_currency, p_amount, p_original_amount, p_original_currency, p_fx_rate),
          nullif(trim(p_receipt_url), ''), auth.uid(),
          case when v_converted then round(p_original_amount, 2) end,
          case when v_converted then p_original_currency end,
          case when v_converted then p_fx_rate end)
  returning id into v_id;
  return v_id;
end;
$$;

create or replace function public.edit_ledger_entry(
  p_entry_id uuid, p_entry_date date, p_kind text, p_party text,
  p_description text, p_amount numeric, p_receipt_url text,
  p_original_amount numeric default null, p_original_currency text default null, p_fx_rate numeric default null
) returns void
language plpgsql security definer set search_path = public as $$
declare
  e ledger_entries%rowtype;
  v_currency text;
  v_converted boolean;
begin
  select * into e from ledger_entries where id = p_entry_id;
  if e.id is null or e.added_by is distinct from auth.uid() then
    raise exception 'Only the person who added this entry can edit it';
  end if;
  if e.status = 'confirmed' then
    raise exception 'Confirmed entries are locked — add a correcting entry instead';
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
         receipt_url = nullif(trim(p_receipt_url), ''),
         status = 'pending', query_note = null, updated_at = now()
   where id = p_entry_id;
end;
$$;

revoke execute on function public.set_ledger_currency(uuid, text) from public, anon;
revoke execute on function public.add_ledger_entry(uuid, date, text, text, text, numeric, text, numeric, text, numeric) from public, anon;
revoke execute on function public.edit_ledger_entry(uuid, date, text, text, text, numeric, text, numeric, text, numeric) from public, anon;
grant  execute on function public.set_ledger_currency(uuid, text) to authenticated;
grant  execute on function public.add_ledger_entry(uuid, date, text, text, text, numeric, text, numeric, text, numeric) to authenticated;
grant  execute on function public.edit_ledger_entry(uuid, date, text, text, text, numeric, text, numeric, text, numeric) to authenticated;
