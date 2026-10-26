-- =====================================================================
-- Crescopus: withdraw a card instead of deleting it
-- Run in the Supabase SQL editor. Safe to re-run.
--
-- Deleting an app card cascades to its partnerships, plans and ledgers,
-- which the other person relies on. So a card with any history is
-- withdrawn instead:
--   - it disappears from browsing straight away
--   - pending connection requests are declined, with a note to the other person
--   - the person chooses which active partnerships to end (one reason for all);
--     ended ones become read-only, the rest carry on
--   - plans and ledgers stay available to both people
--   - the card can be restored later
-- Builders withdraw an app card (listings.withdrawn_at). Growers withdraw
-- their own card (profiles.grower_withdrawn_at). An app card with no history
-- at all can still be deleted outright, through delete_listing() below.
-- (There was no delete policy on listings, so the old Delete button quietly
-- did nothing.)
-- =====================================================================

alter table listings add column if not exists withdrawn_at timestamptz;
alter table profiles add column if not exists grower_withdrawn_at timestamptz;

create index if not exists listings_live_idx on listings (created_at desc) where withdrawn_at is null;


-- p_listing_id: the app card to withdraw, or null for the caller's own grower card.
-- p_end_ids:    the active partnerships the person ticked to end.
-- p_reason:     one short reason, shown to each partner whose partnership ends.
-- Returns {"declined": n, "ended": n}.
create or replace function public.withdraw_card(
  p_listing_id uuid, p_end_ids uuid[] default '{}', p_reason text default null
) returns jsonb
language plpgsql security definer set search_path = public as $$
declare
  v_me uuid := auth.uid();
  v_ids uuid[] := coalesce(p_end_ids, '{}');
  v_note text;
  v_declined integer;
  v_ended integer;
begin
  if v_me is null then
    raise exception 'Please log in again';
  end if;

  if p_listing_id is not null then
    if not exists (select 1 from listings where id = p_listing_id and developer_id = v_me) then
      raise exception 'Only the app''s builder can withdraw its card';
    end if;
    v_note := 'The builder has withdrawn this app from Crescopus.';
  else
    if not exists (select 1 from profiles where id = v_me and is_grower) then
      raise exception 'Only growers have a card to withdraw';
    end if;
    v_note := 'The grower has withdrawn their card from Crescopus.';
  end if;

  -- Every partnership to end must be one of this card's active partnerships.
  if exists (
    select 1 from unnest(v_ids) as x(pid)
     where not exists (
       select 1 from partnerships p
        where p.id = x.pid and p.status in ('trial', 'formalised')
          and ((p_listing_id is not null and p.listing_id = p_listing_id)
               or (p_listing_id is null and p.grower_id = v_me))
     )
  ) then
    raise exception 'One of those partnerships can''t be ended from here — it may already have ended';
  end if;
  if cardinality(v_ids) > 0 and coalesce(trim(p_reason), '') = '' then
    raise exception 'Please give a short reason. Your partners will see it.';
  end if;

  if p_listing_id is not null then
    update listings set withdrawn_at = coalesce(withdrawn_at, now()) where id = p_listing_id;
  else
    update profiles set grower_withdrawn_at = coalesce(grower_withdrawn_at, now()) where id = v_me;
  end if;

  update connection_requests
     set status = 'rejected', reject_reason = v_note
   where status = 'pending'
     and ((p_listing_id is not null and listing_id = p_listing_id)
          or (p_listing_id is null and grower_id = v_me));
  get diagnostics v_declined = row_count;

  update partnerships
     set status = 'ended', ended_at = now(), ended_by = v_me, end_reason = left(trim(p_reason), 1000)
   where id = any(v_ids) and status in ('trial', 'formalised');
  get diagnostics v_ended = row_count;

  return jsonb_build_object('declined', v_declined, 'ended', v_ended);
end;
$$;

create or replace function public.restore_card(p_listing_id uuid)
returns void
language plpgsql security definer set search_path = public as $$
begin
  if p_listing_id is not null then
    update listings set withdrawn_at = null where id = p_listing_id and developer_id = auth.uid();
  else
    update profiles set grower_withdrawn_at = null where id = auth.uid() and is_grower;
  end if;
  if not found then
    raise exception 'That card isn''t yours to restore';
  end if;
end;
$$;

-- Delete an app card outright: only its builder, and only with no history.
create or replace function public.delete_listing(p_listing_id uuid)
returns void
language plpgsql security definer set search_path = public as $$
begin
  if not exists (select 1 from listings where id = p_listing_id and developer_id = auth.uid()) then
    raise exception 'Only the app''s builder can delete its card';
  end if;
  if exists (select 1 from connection_requests where listing_id = p_listing_id)
     or exists (select 1 from partnerships where listing_id = p_listing_id) then
    raise exception 'This card has connection requests or partnerships on record, so it can only be withdrawn';
  end if;
  delete from listings where id = p_listing_id;
end;
$$;

revoke execute on function public.delete_listing(uuid)              from public, anon;
grant  execute on function public.delete_listing(uuid)              to authenticated;
revoke execute on function public.withdraw_card(uuid, uuid[], text) from public, anon;
revoke execute on function public.restore_card(uuid)              from public, anon;
grant  execute on function public.withdraw_card(uuid, uuid[], text) to authenticated;
grant  execute on function public.restore_card(uuid)              to authenticated;

-- Stop new connection requests to or from a withdrawn card, even outside
-- the website.
create or replace function public.block_requests_to_withdrawn()
returns trigger
language plpgsql security definer set search_path = public as $$
begin
  if exists (select 1 from listings where id = new.listing_id and withdrawn_at is not null) then
    raise exception 'This app has been withdrawn from Crescopus';
  end if;
  if exists (select 1 from profiles where id = new.grower_id and grower_withdrawn_at is not null) then
    raise exception 'This grower has withdrawn their card from Crescopus';
  end if;
  return new;
end;
$$;

drop trigger if exists connection_requests_not_withdrawn on connection_requests;
create trigger connection_requests_not_withdrawn
  before insert on connection_requests
  for each row execute function public.block_requests_to_withdrawn();
