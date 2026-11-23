-- =====================================================================
-- Revenue agreement: how a Builder and Grower share the app's revenue.
--
-- Crescopus never holds or moves money. This only records the terms
-- both people agree; the Builder pays the Grower directly.
--
-- Same rules as the CrescoPlan:
--   - only the two parties can read or change it
--   - every save is a new version with a history snapshot
--   - saving counts as the saver agreeing to that version
--   - it's agreed when both people have agreed the current version
--
-- Run once in the Supabase SQL editor. Safe to re-run.
-- =====================================================================

create table if not exists revenue_agreements (
  id             uuid primary key default gen_random_uuid(),
  partnership_id uuid not null unique references partnerships(id) on delete cascade,
  terms          jsonb not null,
  version        integer not null default 1,
  updated_by     uuid references profiles(id),
  updated_at     timestamptz not null default now(),
  created_at     timestamptz not null default now()
);

create table if not exists revenue_signoffs (
  agreement_id uuid not null references revenue_agreements(id) on delete cascade,
  profile_id   uuid not null references profiles(id) on delete cascade,
  version      integer not null,
  signed_at    timestamptz not null default now(),
  primary key (agreement_id, profile_id)
);

create table if not exists revenue_versions (
  id           uuid primary key default gen_random_uuid(),
  agreement_id uuid not null references revenue_agreements(id) on delete cascade,
  version      integer not null,
  terms        jsonb not null,
  created_by   uuid references profiles(id),
  created_at   timestamptz not null default now(),
  unique (agreement_id, version)
);


create or replace function public.is_revenue_party(p_agreement_id uuid)
returns boolean
language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from revenue_agreements ra
    join partnerships p on p.id = ra.partnership_id
    where ra.id = p_agreement_id and (p.developer_id = auth.uid() or p.grower_id = auth.uid())
  );
$$;


-- Save new terms. p_base_version is the version the person was editing
-- (0 when there's no agreement yet), so a partner's newer save is never
-- overwritten by accident. Returns the new version number.
create or replace function public.save_revenue_agreement(
  p_partnership_id uuid, p_terms jsonb, p_base_version integer
) returns integer
language plpgsql security definer set search_path = public as $$
declare
  v_status  text;
  v_id      uuid;
  v_current integer;
  v_version integer;
  v_share   numeric;
begin
  if not is_partnership_party(p_partnership_id) then
    raise exception 'Not a party to this partnership';
  end if;
  select status into v_status from partnerships where id = p_partnership_id;
  if v_status not in ('trial', 'formalised') then
    raise exception 'This partnership has ended, so its revenue terms can''t be changed';
  end if;

  if coalesce(p_terms->>'basis', '') not in ('gross', 'net', 'profit') then
    raise exception 'Choose what the share is taken from';
  end if;
  v_share := (p_terms->>'share')::numeric;
  if v_share is null or v_share <= 0 or v_share > 100 then
    raise exception 'The share must be between 1%% and 100%%';
  end if;

  select id, version into v_id, v_current
    from revenue_agreements where partnership_id = p_partnership_id for update;

  if v_id is null then
    if p_base_version <> 0 then
      raise exception 'The revenue terms have changed since you opened them. Please check the latest version';
    end if;
    insert into revenue_agreements (partnership_id, terms, version, updated_by)
    values (p_partnership_id, p_terms, 1, auth.uid())
    returning id, version into v_id, v_version;
  else
    if v_current <> p_base_version then
      raise exception 'The revenue terms have changed since you opened them. Please check the latest version';
    end if;
    update revenue_agreements
       set terms = p_terms, version = version + 1, updated_by = auth.uid(), updated_at = now()
     where id = v_id
    returning version into v_version;
  end if;

  insert into revenue_versions (agreement_id, version, terms, created_by)
  values (v_id, v_version, p_terms, auth.uid());

  insert into revenue_signoffs (agreement_id, profile_id, version, signed_at)
  values (v_id, auth.uid(), v_version, now())
  on conflict (agreement_id, profile_id) do update set version = excluded.version, signed_at = excluded.signed_at;

  return v_version;
end;
$$;


-- Agree to a specific version; refuses if it changed in the meantime.
create or replace function public.agree_revenue_agreement(p_agreement_id uuid, p_version integer)
returns void
language plpgsql security definer set search_path = public as $$
declare
  v_current integer;
begin
  if not is_revenue_party(p_agreement_id) then
    raise exception 'Not a party to this agreement';
  end if;
  select version into v_current from revenue_agreements where id = p_agreement_id;
  if v_current <> p_version then
    raise exception 'The revenue terms have changed since you opened them. Please check the latest version';
  end if;
  insert into revenue_signoffs (agreement_id, profile_id, version, signed_at)
  values (p_agreement_id, auth.uid(), p_version, now())
  on conflict (agreement_id, profile_id) do update set version = excluded.version, signed_at = excluded.signed_at;
end;
$$;


revoke execute on function public.save_revenue_agreement(uuid, jsonb, integer) from public, anon;
revoke execute on function public.agree_revenue_agreement(uuid, integer)        from public, anon;
grant  execute on function public.save_revenue_agreement(uuid, jsonb, integer) to authenticated;
grant  execute on function public.agree_revenue_agreement(uuid, integer)        to authenticated;


-- Read-only for the two parties; all writes go through the functions above.
alter table revenue_agreements enable row level security;
alter table revenue_signoffs   enable row level security;
alter table revenue_versions   enable row level security;

drop policy if exists "Revenue agreement visible to both parties" on revenue_agreements;
create policy "Revenue agreement visible to both parties"
  on revenue_agreements for select using (is_partnership_party(partnership_id));

drop policy if exists "Revenue sign-offs visible to both parties" on revenue_signoffs;
create policy "Revenue sign-offs visible to both parties"
  on revenue_signoffs for select using (is_revenue_party(agreement_id));

drop policy if exists "Revenue history visible to both parties" on revenue_versions;
create policy "Revenue history visible to both parties"
  on revenue_versions for select using (is_revenue_party(agreement_id));
