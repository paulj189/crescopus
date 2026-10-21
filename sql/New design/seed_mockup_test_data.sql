-- =====================================================================
-- Crescopus: mockup test data (for look-and-feel testing)
-- Run in the Supabase SQL editor AFTER migration_plan_ledger.sql.
--
-- Creates 9 confirmed test users who can log in, their listings,
-- Needs/Offers, trust badges, and one partnership (TideTrack × Growth Co.)
-- with the CrescoPlan and CrescoLedger shown in the mockups.
--
-- Every test login:   <name>+cresco-test@example.com
-- Shared password:    CrescoTest-2026!
--   Builder in the plan/ledger:  sam.patel+cresco-test@example.com
--   Grower in the plan/ledger:   growth.co+cresco-test@example.com
--
-- Re-runnable: it deletes the previous test data first.
-- To remove the test data only, run the CLEANUP statement on its own.
-- =====================================================================

begin;

-- ---------- CLEANUP (removes all test users and everything linked) ----
-- Partnerships first (takes their plans and ledgers with them), then the users.
delete from partnerships
 where developer_id in (select id from auth.users where email like '%+cresco-test@example.com')
    or grower_id    in (select id from auth.users where email like '%+cresco-test@example.com');
delete from auth.users where email like '%+cresco-test@example.com';


-- ---------- Users (the signup trigger creates their profiles) ---------
with u(id, email, full_name, is_developer, is_grower) as (values
  ('c0de0000-0000-4000-8000-000000000001'::uuid, 'sam.patel+cresco-test@example.com',  'Sam Patel',       true,  false),
  ('c0de0000-0000-4000-8000-000000000002'::uuid, 'ana.ruiz+cresco-test@example.com',   'Ana Ruiz',        true,  false),
  ('c0de0000-0000-4000-8000-000000000003'::uuid, 'j.okafor+cresco-test@example.com',   'J. Okafor',       true,  false),
  ('c0de0000-0000-4000-8000-000000000004'::uuid, 'lee.chan+cresco-test@example.com',   'Lee Chan',        true,  false),
  ('c0de0000-0000-4000-8000-000000000005'::uuid, 'mia.hart+cresco-test@example.com',   'Mia Hart',        true,  false),
  ('c0de0000-0000-4000-8000-000000000006'::uuid, 'tom.reid+cresco-test@example.com',   'Tom Reid',        true,  false),
  ('c0de0000-0000-4000-8000-000000000011'::uuid, 'growth.co+cresco-test@example.com',  'Growth Co.',      false, true),
  ('c0de0000-0000-4000-8000-000000000012'::uuid, 'harbour+cresco-test@example.com',    'Harbour Digital', false, true),
  ('c0de0000-0000-4000-8000-000000000013'::uuid, 'priya.shah+cresco-test@example.com', 'Priya Shah',      false, true)
),
ins as (
  insert into auth.users (
    instance_id, id, aud, role, email, encrypted_password, email_confirmed_at,
    raw_app_meta_data, raw_user_meta_data, created_at, updated_at,
    confirmation_token, recovery_token, email_change, email_change_token_new
  )
  select '00000000-0000-0000-0000-000000000000', u.id, 'authenticated', 'authenticated', u.email,
         extensions.crypt('CrescoTest-2026!', extensions.gen_salt('bf')), now(),
         '{"provider":"email","providers":["email"]}'::jsonb,
         jsonb_build_object('full_name', u.full_name, 'is_developer', u.is_developer,
                            'is_grower', u.is_grower, 'country', 'GB'),
         now(), now(), '', '', '', ''
    from u
  returning id, email
)
insert into auth.identities (id, user_id, provider_id, identity_data, provider, last_sign_in_at, created_at, updated_at)
select gen_random_uuid(), ins.id, ins.id::text,
       jsonb_build_object('sub', ins.id::text, 'email', ins.email, 'email_verified', true),
       'email', now(), now(), now()
  from ins;


-- ---------- Profiles: about text, Needs / Offers ---------------------
update profiles p set
  bio        = v.bio,
  pitch_html = '<p>' || v.bio || '</p>',
  needs_html = v.needs_html, offers_html = v.offers_html,
  needs_tags = v.needs_tags, offers_tags = v.offers_tags
from (values
  ('c0de0000-0000-4000-8000-000000000001'::uuid,
   'Independent developer building small, useful apps for outdoor people. Ten years in mobile, happy to iterate quickly with a growth partner.',
   null::text, null::text, '{}'::text[], '{}'::text[]),
  ('c0de0000-0000-4000-8000-000000000002'::uuid, 'Developer of simple money tools for everyday life.', null, null, '{}', '{}'),
  ('c0de0000-0000-4000-8000-000000000003'::uuid, 'Puzzle-game maker with a love of words.', null, null, '{}', '{}'),
  ('c0de0000-0000-4000-8000-000000000004'::uuid, 'Weekend gardener and full-time developer.', null, null, '{}', '{}'),
  ('c0de0000-0000-4000-8000-000000000005'::uuid, 'Runner and app builder.', null, null, '{}', '{}'),
  ('c0de0000-0000-4000-8000-000000000006'::uuid, 'Builds privacy-first productivity tools.', null, null, '{}', '{}'),
  ('c0de0000-0000-4000-8000-000000000011'::uuid,
   'Small growth studio helping indie apps find their first ten thousand users.',
   '<ul><li>Early access to premium features</li><li>Monthly sales data</li></ul>',
   '<ul><li>Two campaigns a month</li><li>App Store optimisation review</li><li>Social content</li></ul>',
   '{analytics_access,product_access}', '{app_store_growth,social,paid_ads}'),
  ('c0de0000-0000-4000-8000-000000000012'::uuid,
   'Paid-ads specialists for subscription apps.',
   '<ul><li>Ad budget agreed up front</li><li>Access to store analytics</li></ul>',
   '<ul><li>Meta and Google ads management</li><li>Weekly reporting</li></ul>',
   '{ad_budget,analytics_access}', '{paid_ads}'),
  ('c0de0000-0000-4000-8000-000000000013'::uuid,
   'Creator partnerships and influencer campaigns.',
   '<ul><li>Product access for creators</li></ul>',
   '<ul><li>Creator network in fitness and outdoors</li><li>Campaign planning</li></ul>',
   '{product_access}', '{influencers,social}')
) as v(id, bio, needs_html, offers_html, needs_tags, offers_tags)
where p.id = v.id;


-- ---------- Trust badges --------------------------------------------
insert into profile_verifications (profile_id, kind) values
  ('c0de0000-0000-4000-8000-000000000001', 'id'),
  ('c0de0000-0000-4000-8000-000000000001', 'github'),
  ('c0de0000-0000-4000-8000-000000000003', 'id'),
  ('c0de0000-0000-4000-8000-000000000004', 'id'),
  ('c0de0000-0000-4000-8000-000000000006', 'id'),
  ('c0de0000-0000-4000-8000-000000000011', 'id'),
  ('c0de0000-0000-4000-8000-000000000011', 'linkedin');


-- ---------- Listings (apps) -----------------------------------------
insert into listings (id, developer_id, title, tagline, description, pitch_html, category, platform,
                      needs_html, offers_html, needs_tags, offers_tags)
values
  ('c0de0000-0000-4000-8000-000000000101', 'c0de0000-0000-4000-8000-000000000001',
   'TideTrack', 'Tide times and swell alerts for UK surfers and sea swimmers.',
   'Live on iOS and Android. Clean, ad-free experience with an optional premium tier for multi-beach alerts.',
   '<p>Live on iOS and Android. Clean, ad-free experience with an optional premium tier for multi-beach alerts.</p>',
   'Sports & outdoors', 'iOS, Android',
   '<ul><li>App Store optimisation and launch push</li><li>Social content for surf and swim communities</li><li>Help shaping the premium offer</li></ul>',
   '<ul><li>Share of net revenue, agreed in the CrescoPlan</li><li>Input on the roadmap</li><li>Fast turnaround on feature requests</li></ul>',
   '{app_store_growth,social}', '{revenue_share,roadmap_input}'),
  ('c0de0000-0000-4000-8000-000000000102', 'c0de0000-0000-4000-8000-000000000002',
   'Pocket Ledger', 'Simple expense splitting for house-shares and trips.',
   'Split bills, track who owes what, settle up.', '<p>Split bills, track who owes what, settle up.</p>',
   'Finance', 'iOS, Android',
   '<ul><li>Paid ads</li><li>Partnerships with student and travel brands</li></ul>',
   '<ul><li>Revenue share</li></ul>',
   '{paid_ads,partnerships}', '{revenue_share}'),
  ('c0de0000-0000-4000-8000-000000000103', 'c0de0000-0000-4000-8000-000000000003',
   'WordQuest', 'A daily word puzzle with weekly leagues.',
   'One puzzle a day, with leagues to play against friends.', '<p>One puzzle a day, with leagues to play against friends.</p>',
   'Games', 'Web, iOS',
   '<ul><li>Influencer campaigns</li></ul>',
   '<ul><li>Revenue share</li><li>Equity for the right partner</li></ul>',
   '{influencers}', '{revenue_share,equity}'),
  ('c0de0000-0000-4000-8000-000000000104', 'c0de0000-0000-4000-8000-000000000004',
   'Grow Box', 'Planting reminders and a seasonal guide for allotment growers.',
   'Know what to sow and when, with reminders for your plot.', '<p>Know what to sow and when, with reminders for your plot.</p>',
   'Lifestyle', 'iOS, Android',
   '<ul><li>App Store growth</li></ul>', '<ul><li>Revenue share</li></ul>',
   '{app_store_growth}', '{revenue_share}'),
  ('c0de0000-0000-4000-8000-000000000105', 'c0de0000-0000-4000-8000-000000000005',
   'RunSplit', 'Pace planning for parkrun and 10k training.',
   'Plan your splits and pace your race.', '<p>Plan your splits and pace your race.</p>',
   'Health & fitness', 'iOS',
   '<ul><li>Partnerships with running clubs</li><li>Social content</li></ul>', '<ul><li>Revenue share</li></ul>',
   '{partnerships,social}', '{revenue_share}'),
  ('c0de0000-0000-4000-8000-000000000106', 'c0de0000-0000-4000-8000-000000000006',
   'QuietNotes', 'Private, offline-first notes with simple sync.',
   'Notes that stay on your device, with optional sync.', '<p>Notes that stay on your device, with optional sync.</p>',
   'Productivity', 'iOS, Android, Web',
   '<ul><li>Paid ads</li></ul>', '<ul><li>Equity</li></ul>',
   '{paid_ads}', '{equity}');


-- ---------- Partnership: TideTrack × Growth Co. ----------------------
-- (the plan row is created automatically by the on_partnership_created trigger)
insert into partnerships (id, listing_id, developer_id, grower_id, status, started_at)
values ('c0de0000-0000-4000-8000-000000000201', 'c0de0000-0000-4000-8000-000000000101',
        'c0de0000-0000-4000-8000-000000000001', 'c0de0000-0000-4000-8000-000000000011',
        'trial', '2026-10-01');


-- ---------- CrescoPlan: version 3, Grower agreed, Builder to review --
update cresco_plans set
  agreed_needs_html  = '<ul><li><strong>Builder:</strong> launch push and social content</li><li><strong>Grower:</strong> early access to premium features and monthly sales data</li></ul>',
  agreed_offers_html = '<ul><li><strong>Builder:</strong> [X]% of net revenue, reviewed quarterly</li><li><strong>Grower:</strong> two campaigns a month and an ASO review</li></ul>',
  version    = 3,
  updated_by = 'c0de0000-0000-4000-8000-000000000011',
  updated_at = '2026-10-20 14:00+01'
where partnership_id = 'c0de0000-0000-4000-8000-000000000201';

insert into plan_actions (plan_id, position, title, owner_role, due_date, status)
select id, x.pos, x.title, x.owner_role, x.due::date, x.status
  from cresco_plans,
       (values (1, 'Share App Store analytics access',      'builder', '2026-10-10', 'done'),
               (2, 'Launch social campaign for surf clubs', 'grower',  '2026-10-31', 'in_progress'),
               (3, 'Rewrite store listing and screenshots', 'grower',  '2026-11-15', 'not_started'))
       as x(pos, title, owner_role, due, status)
 where partnership_id = 'c0de0000-0000-4000-8000-000000000201';

insert into plan_measures (plan_id, position, measure, target, evidence, review_date, owner_role)
select id, x.pos, x.measure, x.target, x.evidence, x.review::date, x.owner_role
  from cresco_plans,
       (values (1, 'Monthly downloads',   '[TARGET]', 'App Store',  '2026-11-30', 'grower'),
               (2, 'Premium subscribers', '[TARGET]', 'RevenueCat', '2026-12-31', 'builder'))
       as x(pos, measure, target, evidence, review, owner_role)
 where partnership_id = 'c0de0000-0000-4000-8000-000000000201';

insert into plan_versions (plan_id, version, snapshot, created_by, created_at)
select cp.id, 3,
       jsonb_build_object(
         'agreed_needs_html',  cp.agreed_needs_html,
         'agreed_offers_html', cp.agreed_offers_html,
         'actions',  (select jsonb_agg(to_jsonb(a) order by a.position) from plan_actions a where a.plan_id = cp.id),
         'measures', (select jsonb_agg(to_jsonb(m) order by m.position) from plan_measures m where m.plan_id = cp.id)),
       'c0de0000-0000-4000-8000-000000000011', '2026-10-20 14:00+01'
  from cresco_plans cp
 where cp.partnership_id = 'c0de0000-0000-4000-8000-000000000201';

insert into plan_signoffs (plan_id, profile_id, version, signed_at)
select id, 'c0de0000-0000-4000-8000-000000000011', 3, '2026-10-20 14:05+01'
  from cresco_plans
 where partnership_id = 'c0de0000-0000-4000-8000-000000000201';


-- ---------- CrescoLedger: 3 confirmed, 1 awaiting the Builder --------
insert into ledger_entries (partnership_id, entry_date, kind, party, description, amount, receipt_url,
                            status, added_by, confirmed_by, confirmed_at, created_at)
values
  ('c0de0000-0000-4000-8000-000000000201', '2026-10-02', 'revenue', 'builder', 'App Store sales, September', 1240.00,
   'https://example.com/receipts/app-store-sept', 'confirmed',
   'c0de0000-0000-4000-8000-000000000001', 'c0de0000-0000-4000-8000-000000000011', '2026-10-03 09:00+01', '2026-10-02 18:00+01'),
  ('c0de0000-0000-4000-8000-000000000201', '2026-10-05', 'cost', 'grower', 'Social ads, launch campaign', 320.00,
   'https://example.com/receipts/social-ads', 'confirmed',
   'c0de0000-0000-4000-8000-000000000011', 'c0de0000-0000-4000-8000-000000000001', '2026-10-06 10:00+01', '2026-10-05 17:00+01'),
  ('c0de0000-0000-4000-8000-000000000201', '2026-10-12', 'cost', 'grower', 'Landing page design', 150.00,
   'https://example.com/receipts/landing-page', 'pending',
   'c0de0000-0000-4000-8000-000000000011', null, null, '2026-10-12 16:00+01'),
  ('c0de0000-0000-4000-8000-000000000201', '2026-10-15', 'revenue', 'builder', 'In-app subscriptions, first half of October', 610.00,
   'https://example.com/receipts/subs-oct-1', 'confirmed',
   'c0de0000-0000-4000-8000-000000000001', 'c0de0000-0000-4000-8000-000000000011', '2026-10-16 11:00+01', '2026-10-15 19:00+01');

commit;

-- Expected ledger totals (confirmed only): revenue £1,850.00, costs £320.00, net £1,530.00,
-- with £150.00 awaiting the Builder's confirmation.
