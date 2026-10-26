-- =====================================================================
-- Crescopus: test data for CrescoLedger disputes
-- Run in the Supabase SQL editor AFTER:
--   - sql/New design/seed_mockup_test_data.sql  (creates the test users)
--   - migration_ledger_time_goodwill.sql and migration_ledger_disputes.sql
--
-- Creates one partnership, Pocket Ledger (Ana Ruiz, Builder) x Harbour
-- Digital (Grower), with agreed hourly rates, a ledger, and a dispute in
-- each state, so you can try every part of the dispute flow:
--
--   A. Open, waiting for Harbour to give their side
--        log in as Harbour -> "Give your side", AI summary, propose
--   B. Open, Harbour has proposed a fix, waiting for Ana to agree
--        log in as Ana -> Agree applies it (hosting to £20, build to 6 hours)
--   C. Open, Harbour silent for 20 days
--        log in as Ana -> "Close without agreement" is available
--   D. Resolved: an entry voided by agreement (greyed out, out of totals)
--   E. Withdrawn by the person who raised it
--
-- Logins (shared password CrescoTest-2026!):
--   Builder: ana.ruiz+cresco-test@example.com
--   Grower:  harbour+cresco-test@example.com
--
-- Every step goes through the real database functions, acting as each
-- person in turn, so the rules, locks and entry history are all exercised.
-- Re-runnable: it removes its own partnership first. To remove it only:
--   delete from partnerships where id = 'c0de0000-0000-4000-8000-000000000301';
-- =====================================================================

begin;

do $$
begin
  if not exists (select 1 from profiles where id = 'c0de0000-0000-4000-8000-000000000002')
     or not exists (select 1 from profiles where id = 'c0de0000-0000-4000-8000-000000000012')
     or not exists (select 1 from listings where id = 'c0de0000-0000-4000-8000-000000000102') then
    raise exception 'Run sql/New design/seed_mockup_test_data.sql first: it creates the test users and apps.';
  end if;
end $$;

-- Clean up a previous run (takes its plan, ledger, rates and disputes with it).
delete from ai_usage where dispute_id in (select id from ledger_disputes where partnership_id = 'c0de0000-0000-4000-8000-000000000301');
delete from partnerships where id = 'c0de0000-0000-4000-8000-000000000301';

-- Acts as a test user for the calls that follow (what auth.uid() returns).
create or replace function pg_temp.act_as(p_id uuid) returns void language sql as $$
  select set_config('request.jwt.claims', json_build_object('sub', p_id, 'role', 'authenticated')::text, true),
         set_config('request.jwt.claim.sub', p_id::text, true);
$$;

-- Everything in one transaction gets the same now(), so this spreads each
-- step out in time (oldest first) to keep threads and histories in order.
create or replace function pg_temp.stamp(t timestamptz) returns void language sql as $$
  update ledger_entry_events      set created_at = t where created_at = now();
  update ledger_disputes          set created_at = t where created_at = now();
  update ledger_disputes          set last_activity_at = t where last_activity_at = now();
  update ledger_disputes          set closed_at = t where closed_at = now();
  update ledger_dispute_messages  set created_at = t where created_at = now();
  update ledger_dispute_proposals set created_at = t where created_at = now();
  update ledger_dispute_proposals set responded_at = t where responded_at = now();
  update ledger_entries           set confirmed_at = t where confirmed_at = now();
$$;

-- ---------- Partnership (its plan is created by the trigger) ----------
insert into partnerships (id, listing_id, developer_id, grower_id, status, started_at)
values ('c0de0000-0000-4000-8000-000000000301', 'c0de0000-0000-4000-8000-000000000102',
        'c0de0000-0000-4000-8000-000000000002', 'c0de0000-0000-4000-8000-000000000012',
        'trial', '2026-09-01 10:00+01');

update cresco_plans set
  agreed_needs_html  = '<ul><li><strong>Builder:</strong> app store optimisation and a paid ads test</li><li><strong>Grower:</strong> access to download and revenue figures</li></ul>',
  agreed_offers_html = '<ul><li><strong>Builder:</strong> 20% of net revenue from new users</li><li><strong>Grower:</strong> up to 10 hours a month, at the agreed rate</li></ul>'
where partnership_id = 'c0de0000-0000-4000-8000-000000000301';

do $$
declare
  pid  constant uuid := 'c0de0000-0000-4000-8000-000000000301';
  ana  constant uuid := 'c0de0000-0000-4000-8000-000000000002';
  har  constant uuid := 'c0de0000-0000-4000-8000-000000000012';
  r uuid;
  e_rev1 uuid; e_rev2 uuid; e_ads uuid; e_aso uuid; e_hosting uuid; e_ana_dev uuid; e_old_tool uuid; e_har_time2 uuid;
  d uuid; pr uuid;
  t timestamptz := now() - interval '12 days';
begin
  -- ---------- Agreed hourly rates ----------
  perform pg_temp.act_as(ana);
  r := propose_rate(pid, 45, true, 'My usual freelance rate');
  perform pg_temp.act_as(har);
  perform respond_rate(r, true);
  r := propose_rate(pid, 35, true, 'Agency rate for small clients');
  perform pg_temp.act_as(ana);
  perform respond_rate(r, true);
  update plan_rates set effective_from = '2026-09-01' where partnership_id = pid;

  -- ---------- Ledger entries ----------
  perform pg_temp.act_as(ana);
  e_rev1    := add_ledger_entry(pid, '2026-09-30', 'revenue', 'builder', 'September subscriptions (App Store)', 612.40, null);
  e_rev2    := add_ledger_entry(pid, '2026-10-20', 'revenue', 'builder', 'October subscriptions to date', 488.15, null);
  e_hosting := add_ledger_entry(pid, '2026-09-05', 'cost', 'builder', 'Hosting, September', 24.00, 'INV-20931', p_cost_class => 'recoverable');
  e_ana_dev := add_ledger_entry(pid, '2026-09-12', 'time', 'builder', 'Built the referral screen the ads point to', null, null, p_hours => 9, p_cost_class => 'recoverable');
  e_old_tool := add_ledger_entry(pid, '2026-09-03', 'cost', 'builder', 'Analytics tool (annual)', 96.00, null, p_cost_class => 'recoverable');

  perform pg_temp.act_as(har);
  e_ads      := add_ledger_entry(pid, '2026-10-02', 'cost', 'grower', 'Paid ads test, week 1', 150.00, 'https://example.com/receipts/ads-week-1', p_cost_class => 'recoverable');
  e_aso      := add_ledger_entry(pid, '2026-09-18', 'time', 'grower', 'App Store listing rewrite and keywords', null, null, p_hours => 14, p_cost_class => 'recoverable');
  e_har_time2 := add_ledger_entry(pid, '2026-10-09', 'time', 'grower', 'Ads report and next-step plan', null, null, p_hours => 3, p_cost_class => 'recoverable');
  perform pg_temp.stamp(t); t := t + interval '1 hour';

  -- Each confirms the other's entries.
  perform confirm_ledger_entry(x) from unnest(array[e_rev1, e_rev2, e_hosting, e_ana_dev, e_old_tool]) x;
  perform pg_temp.act_as(ana);
  perform confirm_ledger_entry(x) from unnest(array[e_ads, e_aso, e_har_time2]) x;
  perform pg_temp.stamp(t); t := t + interval '1 day';

  -- ---------- A. Open, waiting for Harbour ----------
  d := raise_dispute(pid, array[e_aso],
       'The listing rewrite was logged as 14 hours, but our plan says up to 10 hours a month, and the work was all in September.',
       'Correct it to 10 hours');
  perform pg_temp.stamp(t); t := t + interval '3 hours';

  -- ---------- B. Open, Harbour's proposal waiting for Ana ----------
  perform pg_temp.act_as(har);
  d := raise_dispute(pid, array[e_hosting, e_ana_dev],
       'The referral screen was going to be built anyway, so I don''t think it should be recoverable from the partnership. And the hosting invoice says £20, not £24.',
       'Make the build Goodwill and correct hosting to £20');
  perform pg_temp.stamp(t); t := t + interval '3 hours';
  perform pg_temp.act_as(ana);
  perform add_dispute_message(d,
       'Fair point on hosting: £20 plus VAT is £24, but VAT is reclaimed, so £20 is right. The referral screen was only built because the ads needed somewhere to land, so I think it is recoverable.',
       'https://example.com/receipts/INV-20931');
  perform pg_temp.stamp(t); t := t + interval '3 hours';
  perform pg_temp.act_as(har);
  perform add_dispute_message(d, 'Thanks. How about hosting to £20 and the build stays recoverable, but at 6 hours rather than 9?', null);
  perform pg_temp.stamp(t); t := t + interval '3 hours';
  pr := propose_dispute_resolution(d, jsonb_build_array(
          jsonb_build_object('entry_id', e_hosting, 'action', 'correct', 'amount', 20),
          jsonb_build_object('entry_id', e_ana_dev, 'action', 'correct', 'hours', 6)),
        'Hosting net of VAT; build time trimmed to the screen itself');
  perform pg_temp.stamp(t); t := t + interval '3 hours';

  -- ---------- C. Open, Harbour silent for 20 days ----------
  perform pg_temp.act_as(ana);
  d := raise_dispute(pid, array[e_har_time2],
       'The ads report took about an hour to read; 3 hours seems high for a one-page summary.', 'Correct it to 1 hour');
  update ledger_disputes set created_at = now() - interval '20 days', last_activity_at = now() - interval '20 days' where id = d;
  update ledger_dispute_messages set created_at = now() - interval '20 days' where dispute_id = d;

  -- ---------- D. Resolved: the analytics tool voided ----------
  perform pg_temp.act_as(har);
  d := raise_dispute(pid, array[e_old_tool],
       'The analytics tool was bought before we started working together, so it shouldn''t be in this ledger.', 'Void it');
  perform pg_temp.stamp(t); t := t + interval '3 hours';
  perform pg_temp.act_as(ana);
  perform add_dispute_message(d, 'You''re right, I renewed it for my own use. Happy to void it.', null);
  perform pg_temp.stamp(t); t := t + interval '3 hours';
  pr := propose_dispute_resolution(d, jsonb_build_array(jsonb_build_object('entry_id', e_old_tool, 'action', 'void')), 'Bought before the partnership');
  perform pg_temp.stamp(t); t := t + interval '3 hours';
  perform pg_temp.act_as(har);
  perform respond_dispute_resolution(pr, true);
  perform pg_temp.stamp(t); t := t + interval '3 hours';

  -- ---------- E. Withdrawn ----------
  d := raise_dispute(pid, array[e_rev2], 'Is this October figure before or after Apple''s commission?', null);
  perform pg_temp.stamp(t); t := t + interval '3 hours';
  perform pg_temp.act_as(ana);
  perform add_dispute_message(d, 'After commission: it''s what was paid out to me.', null);
  perform pg_temp.stamp(t); t := t + interval '3 hours';
  perform pg_temp.act_as(har);
  perform withdraw_dispute(d);
  perform pg_temp.stamp(t); t := t + interval '3 hours';
end $$;

commit;

-- What was created:
select d.reason, d.status, count(de.entry_id) as entries
  from ledger_disputes d join ledger_dispute_entries de on de.dispute_id = d.id
 where d.partnership_id = 'c0de0000-0000-4000-8000-000000000301'
 group by d.id order by d.created_at;
