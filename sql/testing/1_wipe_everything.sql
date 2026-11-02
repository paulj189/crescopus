-- =====================================================================
-- Crescopus TESTING: wipe every user and all their data
--
-- !! This deletes EVERY account (including your own) and everything
-- !! linked to them: cards, Crescos, plans, ledgers, disputes, messages.
-- !! It can't be undone. Only run it while Crescopus has no real users.
--
-- Kept: the tag list (Needs / Offers options) and the site's content pages
--       (mc_items, mc_versions, mc_nav_rules, mc_change_log).
-- Cleared from the content tools: who has access (mc_members) and who
--       viewed what (mc_view_log), as those point at accounts being deleted.
-- Run in the Supabase SQL editor. Safe to re-run.
--
-- Afterwards:
--   - Sign up again yourself (or run 2_load_test_scenarios.sql).
--   - Content-tools access is cleared, so after signing up again run
--     `flask mc-bootstrap <your new user id>` to make yourself approver.
--   - Uploaded images stay in Storage (harmless). To clear them too:
--     Storage -> listing-media -> select all -> Delete.
-- =====================================================================

begin;

do $$
declare
  -- Every table that holds user data. Tables that don't exist are skipped.
  wanted text[] := array[
    'tracking_events', 'tracking_snippets',
    'recovery_settlement_entries', 'recovery_settlements',
    'ledger_dispute_proposals', 'ledger_dispute_messages', 'ledger_dispute_entries', 'ledger_disputes',
    'ledger_entry_events', 'ledger_entries', 'plan_rates',
    'plan_versions', 'plan_signoffs', 'plan_actions', 'plan_measures', 'cresco_plans',
    'message_reads', 'messages',
    'revenue_reports', 'engagement_reports', 'gap_offers', 'reviews',
    'partnerships', 'connection_requests',
    'listing_images', 'revenue_streams', 'proposals', 'listings',
    'ai_usage', 'premium_interest', 'account_entitlements', 'profile_verifications',
    'profiles',
    -- Content tools: access and viewing history (the content itself is kept).
    'mc_members', 'mc_view_log'
  ];
  present text[] := '{}';
  t text;
begin
  foreach t in array wanted loop
    if to_regclass('public.' || t) is not null then
      present := present || t;
    end if;
  end loop;
  -- One TRUNCATE for all of them, so the links between them don't get in the way.
  execute 'truncate table ' ||
          (select string_agg(format('public.%I', x), ', ') from unnest(present) x);
end $$;

-- The accounts themselves (their sign-in identities go with them).
delete from auth.users;

commit;

-- Check: everything should be 0, except tags_kept (your Needs / Offers tag list, 14).
select (select count(*) from auth.users)    as users,
       (select count(*) from profiles)      as profiles,
       (select count(*) from listings)      as app_cards,
       (select count(*) from partnerships)  as crescos,
       (select count(*) from ledger_entries) as ledger_entries,
       (select count(*) from tag_options)   as tags_kept;
