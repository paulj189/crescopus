-- =====================================================================
-- Crescopus TESTING: load a full set of test scenarios
--
-- Run in the Supabase SQL editor, usually straight after
-- 1_wipe_everything.sql. Re-runnable: it first removes its own test users
-- (anything @example.com ending in +cresco-test) and everything linked to them.
--
-- Every login:  <name>+cresco-test@example.com     Password: CrescoTest-2026!
--
-- BUILDERS                                   GROWERS
--   sam.patel   Sam Patel    TideTrack         growth.co  Growth Co.
--   ana.ruiz    Ana Ruiz     Pocket Ledger     harbour    Harbour Digital
--   j.okafor    J. Okafor    WordQuest         priya.shah Priya Shah
--   mia.hart    Mia Hart     RunSplit          nina.brooks Nina Brooks (card withdrawn)
--   tom.reid    Tom Reid     QuietNotes
--   lee.chan    Lee Chan     Grow Box (card withdrawn, no history: can be deleted)
--   kim.lowe    Kim Lowe     no app yet
-- NOT SET UP
--   alex.morgan Alex Morgan  signed up but hasn't chosen Builder/Grower
--
-- CRESCOS (what to test, and who to log in as)
--   1. TideTrack x Growth Co.  "Busy"
--        Sam: plan version 2 to agree; a ledger entry to confirm; his own
--             entry queried by Growth Co.; a new hourly rate to answer;
--             an unread message.
--        Growth Co.: waiting on Sam for all of the above.
--   2. Pocket Ledger x Harbour Digital  "Disputes"
--        A. open, waiting for Harbour to give their side
--        B. open, Harbour's proposed fix waiting for Ana
--        C. open, Harbour silent 20 days -> Ana can close without agreement
--        D. resolved (entry voided)      E. withdrawn
--        Harbour has used all 3 free CrescoGuide summaries (Premium prompt);
--        Ana has all 3 left.
--   3. WordQuest x Priya Shah  "Brand new"
--        Blank plan (first save becomes version 1), empty ledger,
--        J. Okafor chooses the currency, Priya just sees it.
--   4. RunSplit x Growth Co.  "Agreed, money in"
--        Plan agreed by both. Recoverable and Goodwill costs and time.
--        Growth Co. proposed a recovery settlement -> Mia to answer.
--        Mia asked to make a Goodwill entry Recoverable -> Growth Co. to answer.
--   5. QuietNotes x Harbour Digital  "Ended" (read-only plan and ledger)
--
-- CONNECTION REQUESTS
--   Priya -> Pocket Ledger: waiting for Ana        (Ana: "Connection request")
--   Tom (QuietNotes) -> Priya: waiting for Priya   (Priya: "Connection request")
--   J. Okafor (WordQuest) -> Growth Co.: waiting   (J. Okafor: request sent)
--   Harbour -> RunSplit: declined, with a reason   (Harbour: request declined)
--
-- Everyone sees the CrescoLedger notice the first time they open a ledger.
-- =====================================================================

begin;

do $$
begin
  if not exists (select 1 from tag_options where slug = 'app_store_growth') then
    raise exception 'The tag list is missing. Run sql/migration_tag_options.sql first.';
  end if;
end $$;

-- ---------- Remove a previous run (all +cresco-test users and their data) ----------
delete from ai_usage where profile_id in (select id from auth.users where email like '%+cresco-test@example.com');
delete from partnerships
 where developer_id in (select id from auth.users where email like '%+cresco-test@example.com')
    or grower_id    in (select id from auth.users where email like '%+cresco-test@example.com');
delete from connection_requests
 where grower_id    in (select id from auth.users where email like '%+cresco-test@example.com')
    or initiated_by in (select id from auth.users where email like '%+cresco-test@example.com');
delete from listings where developer_id in (select id from auth.users where email like '%+cresco-test@example.com');
delete from auth.users where email like '%+cresco-test@example.com';


-- ---------- Users (the signup trigger creates their profiles) ----------
with u(id, email, full_name, is_developer, is_grower) as (values
  ('c0de0000-0000-4000-8000-000000000001'::uuid, 'sam.patel+cresco-test@example.com',   'Sam Patel',       true,  false),
  ('c0de0000-0000-4000-8000-000000000002'::uuid, 'ana.ruiz+cresco-test@example.com',    'Ana Ruiz',        true,  false),
  ('c0de0000-0000-4000-8000-000000000003'::uuid, 'j.okafor+cresco-test@example.com',    'J. Okafor',       true,  false),
  ('c0de0000-0000-4000-8000-000000000004'::uuid, 'lee.chan+cresco-test@example.com',    'Lee Chan',        true,  false),
  ('c0de0000-0000-4000-8000-000000000005'::uuid, 'mia.hart+cresco-test@example.com',    'Mia Hart',        true,  false),
  ('c0de0000-0000-4000-8000-000000000006'::uuid, 'tom.reid+cresco-test@example.com',    'Tom Reid',        true,  false),
  ('c0de0000-0000-4000-8000-000000000007'::uuid, 'kim.lowe+cresco-test@example.com',    'Kim Lowe',        true,  false),
  ('c0de0000-0000-4000-8000-000000000011'::uuid, 'growth.co+cresco-test@example.com',   'Growth Co.',      false, true),
  ('c0de0000-0000-4000-8000-000000000012'::uuid, 'harbour+cresco-test@example.com',     'Harbour Digital', false, true),
  ('c0de0000-0000-4000-8000-000000000013'::uuid, 'priya.shah+cresco-test@example.com',  'Priya Shah',      false, true),
  ('c0de0000-0000-4000-8000-000000000014'::uuid, 'nina.brooks+cresco-test@example.com', 'Nina Brooks',     false, true),
  ('c0de0000-0000-4000-8000-000000000020'::uuid, 'alex.morgan+cresco-test@example.com', 'Alex Morgan',     false, false)
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
         now() - interval '60 days', now(), '', '', '', ''
    from u
  returning id, email
)
insert into auth.identities (id, user_id, provider_id, identity_data, provider, last_sign_in_at, created_at, updated_at)
select gen_random_uuid(), ins.id, ins.id::text,
       jsonb_build_object('sub', ins.id::text, 'email', ins.email, 'email_verified', true),
       'email', now(), now(), now()
  from ins;


-- ---------- Profiles: summaries, About, Needs / Offers ----------
update profiles p set
  bio = v.bio, pitch_html = '<p>' || v.bio || '</p>',
  needs_html = v.needs_html, offers_html = v.offers_html,
  needs_tags = v.needs_tags, offers_tags = v.offers_tags
from (values
  ('c0de0000-0000-4000-8000-000000000001'::uuid, 'Independent developer building small, useful apps for outdoor people.', null::text, null::text, '{}'::text[], '{}'::text[]),
  ('c0de0000-0000-4000-8000-000000000002'::uuid, 'Developer of simple money tools for everyday life.', null, null, '{}', '{}'),
  ('c0de0000-0000-4000-8000-000000000003'::uuid, 'Puzzle-game maker with a love of words.', null, null, '{}', '{}'),
  ('c0de0000-0000-4000-8000-000000000004'::uuid, 'Weekend gardener and full-time developer.', null, null, '{}', '{}'),
  ('c0de0000-0000-4000-8000-000000000005'::uuid, 'Runner and app builder.', null, null, '{}', '{}'),
  ('c0de0000-0000-4000-8000-000000000006'::uuid, 'Builds privacy-first productivity tools.', null, null, '{}', '{}'),
  ('c0de0000-0000-4000-8000-000000000007'::uuid, 'New to Crescopus; first app on the way.', null, null, '{}', '{}'),
  ('c0de0000-0000-4000-8000-000000000011'::uuid, 'Small growth studio helping indie apps find their first ten thousand users.',
   '<ul><li>Early access to premium features</li><li>Monthly sales data</li></ul>',
   '<ul><li>Two campaigns a month</li><li>App Store optimisation review</li><li>Social content</li></ul>',
   '{analytics_access,product_access}', '{app_store_growth,social,paid_ads}'),
  ('c0de0000-0000-4000-8000-000000000012'::uuid, 'Paid-ads specialists for subscription apps.',
   '<ul><li>Ad budget agreed up front</li><li>Access to store analytics</li></ul>',
   '<ul><li>Meta and Google ads management</li><li>Weekly reporting</li></ul>',
   '{ad_budget,analytics_access}', '{paid_ads}'),
  ('c0de0000-0000-4000-8000-000000000013'::uuid, 'Creator partnerships and influencer campaigns.',
   '<ul><li>Product access for creators</li></ul>',
   '<ul><li>Creator network in fitness and outdoors</li><li>Campaign planning</li></ul>',
   '{product_access,creative_assets}', '{influencers,social,content}'),
  ('c0de0000-0000-4000-8000-000000000014'::uuid, 'SEO and content for web apps.',
   '<ul><li>Revenue share</li></ul>', '<ul><li>SEO audits</li><li>Blog content</li></ul>',
   '{revenue_share}', '{seo,content}')
) as v(id, bio, needs_html, offers_html, needs_tags, offers_tags)
where p.id = v.id;

-- Nina has withdrawn her Grower card.
update profiles set grower_withdrawn_at = now() - interval '5 days'
 where id = 'c0de0000-0000-4000-8000-000000000014';

-- Trust badges.
insert into profile_verifications (profile_id, kind) values
  ('c0de0000-0000-4000-8000-000000000001', 'id'),
  ('c0de0000-0000-4000-8000-000000000001', 'github'),
  ('c0de0000-0000-4000-8000-000000000003', 'id'),
  ('c0de0000-0000-4000-8000-000000000005', 'id'),
  ('c0de0000-0000-4000-8000-000000000011', 'id'),
  ('c0de0000-0000-4000-8000-000000000011', 'linkedin'),
  ('c0de0000-0000-4000-8000-000000000013', 'linkedin');


-- ---------- App cards ----------
insert into listings (id, developer_id, title, tagline, description, pitch_html, category, platform,
                      needs_html, offers_html, needs_tags, offers_tags)
values
  ('c0de0000-0000-4000-8000-000000000101', 'c0de0000-0000-4000-8000-000000000001',
   'TideTrack', 'Tide times and swell alerts for UK surfers and sea swimmers.',
   'Live on iOS and Android, with an optional premium tier for multi-beach alerts.',
   '<p>Live on iOS and Android, with an optional premium tier for multi-beach alerts.</p>',
   'Sports & outdoors', 'iOS, Android',
   '<ul><li>App Store optimisation and a launch push</li><li>Social content for surf and swim communities</li></ul>',
   '<ul><li>Share of net revenue</li><li>Input on the roadmap</li></ul>',
   '{app_store_growth,social}', '{revenue_share,roadmap_input,analytics_access}'),
  ('c0de0000-0000-4000-8000-000000000102', 'c0de0000-0000-4000-8000-000000000002',
   'Pocket Ledger', 'Simple expense splitting for house-shares and trips.',
   'Split bills, track who owes what, settle up.', '<p>Split bills, track who owes what, settle up.</p>',
   'Finance', 'iOS, Android',
   '<ul><li>Paid ads</li><li>Partnerships with student and travel brands</li></ul>', '<ul><li>Revenue share</li><li>Ad budget</li></ul>',
   '{paid_ads,partnerships}', '{revenue_share,ad_budget}'),
  ('c0de0000-0000-4000-8000-000000000103', 'c0de0000-0000-4000-8000-000000000003',
   'WordQuest', 'A daily word puzzle with weekly leagues.',
   'One puzzle a day, with leagues to play against friends.', '<p>One puzzle a day, with leagues to play against friends.</p>',
   'Games', 'Web, iOS',
   '<ul><li>Influencer campaigns</li><li>Social content</li></ul>', '<ul><li>Revenue share</li><li>Product access</li></ul>',
   '{influencers,social}', '{revenue_share,product_access}'),
  ('c0de0000-0000-4000-8000-000000000104', 'c0de0000-0000-4000-8000-000000000004',
   'Grow Box', 'Planting reminders and a seasonal guide for allotment growers.',
   'Know what to sow and when.', '<p>Know what to sow and when.</p>',
   'Lifestyle', 'iOS, Android',
   '<ul><li>App Store growth</li></ul>', '<ul><li>Revenue share</li></ul>',
   '{app_store_growth}', '{revenue_share}'),
  ('c0de0000-0000-4000-8000-000000000105', 'c0de0000-0000-4000-8000-000000000005',
   'RunSplit', 'Pace planning for parkrun and 10k training.',
   'Plan your splits and pace your race.', '<p>Plan your splits and pace your race.</p>',
   'Health & fitness', 'iOS',
   '<ul><li>Partnerships with running clubs</li><li>Social content</li></ul>', '<ul><li>Revenue share</li><li>Analytics access</li></ul>',
   '{partnerships,social}', '{revenue_share,analytics_access}'),
  ('c0de0000-0000-4000-8000-000000000106', 'c0de0000-0000-4000-8000-000000000006',
   'QuietNotes', 'Private, offline-first notes with simple sync.',
   'Notes that stay on your device.', '<p>Notes that stay on your device.</p>',
   'Productivity', 'iOS, Android, Web',
   '<ul><li>Paid ads</li><li>Content</li></ul>', '<ul><li>Equity</li></ul>',
   '{paid_ads,content}', '{equity}');

-- Lee's Grow Box card is withdrawn (it has no history, so it can also be deleted).
update listings set withdrawn_at = now() - interval '3 days'
 where id = 'c0de0000-0000-4000-8000-000000000104';


-- ---------- Connection requests ----------
insert into connection_requests (listing_id, grower_id, initiated_by, message, status, reject_reason, created_at, responded_at)
values
  ('c0de0000-0000-4000-8000-000000000102', 'c0de0000-0000-4000-8000-000000000013', 'c0de0000-0000-4000-8000-000000000013',
   'Hi Ana, my creator network loves money-saving apps for students. Fancy a chat?', 'pending', null, now() - interval '1 day', null),
  ('c0de0000-0000-4000-8000-000000000106', 'c0de0000-0000-4000-8000-000000000013', 'c0de0000-0000-4000-8000-000000000006',
   'Hi Priya, QuietNotes could use some creator content. Interested?', 'pending', null, now() - interval '2 days', null),
  ('c0de0000-0000-4000-8000-000000000103', 'c0de0000-0000-4000-8000-000000000011', 'c0de0000-0000-4000-8000-000000000003',
   'Hello Growth Co., WordQuest is ready for a proper launch push.', 'pending', null, now() - interval '3 hours', null),
  ('c0de0000-0000-4000-8000-000000000105', 'c0de0000-0000-4000-8000-000000000012', 'c0de0000-0000-4000-8000-000000000012',
   'We run ads for fitness apps and would love to help RunSplit.', 'rejected',
   'Thanks, but I already have a growth partner for RunSplit.', now() - interval '6 days', now() - interval '5 days');


-- ---------- Crescos (each one's blank plan is created automatically) ----------
insert into partnerships (id, listing_id, developer_id, grower_id, status, started_at, ended_at, ended_by, end_reason)
values
  ('c0de0000-0000-4000-8000-000000000201', 'c0de0000-0000-4000-8000-000000000101',
   'c0de0000-0000-4000-8000-000000000001', 'c0de0000-0000-4000-8000-000000000011', 'trial', now() - interval '40 days', null, null, null),
  ('c0de0000-0000-4000-8000-000000000202', 'c0de0000-0000-4000-8000-000000000102',
   'c0de0000-0000-4000-8000-000000000002', 'c0de0000-0000-4000-8000-000000000012', 'trial', now() - interval '60 days', null, null, null),
  ('c0de0000-0000-4000-8000-000000000203', 'c0de0000-0000-4000-8000-000000000103',
   'c0de0000-0000-4000-8000-000000000003', 'c0de0000-0000-4000-8000-000000000013', 'trial', now() - interval '1 day', null, null, null),
  ('c0de0000-0000-4000-8000-000000000204', 'c0de0000-0000-4000-8000-000000000105',
   'c0de0000-0000-4000-8000-000000000005', 'c0de0000-0000-4000-8000-000000000011', 'trial', now() - interval '50 days', null, null, null),
  ('c0de0000-0000-4000-8000-000000000205', 'c0de0000-0000-4000-8000-000000000106',
   'c0de0000-0000-4000-8000-000000000006', 'c0de0000-0000-4000-8000-000000000012', 'trial', now() - interval '90 days',
   now() - interval '10 days', 'c0de0000-0000-4000-8000-000000000006', 'We''ve decided to pause marketing for now. Thanks for your help.');


-- Acts as a test user for the calls that follow (what auth.uid() returns).
create or replace function pg_temp.act_as(p_id uuid) returns void language sql as $$
  select set_config('request.jwt.claims', json_build_object('sub', p_id, 'role', 'authenticated')::text, true),
         set_config('request.jwt.claim.sub', p_id::text, true);
$$;

-- Everything in one transaction shares the same now(), so this moves the rows
-- just created back to time t, to keep threads and histories in a sensible order.
create or replace function pg_temp.stamp(t timestamptz) returns void language sql as $$
  update plan_versions            set created_at = t where created_at = now();
  update plan_signoffs            set signed_at = t where signed_at = now();
  update cresco_plans             set updated_at = t where updated_at = now();
  update plan_rates               set created_at = t where created_at = now();
  update plan_rates               set responded_at = t where responded_at = now();
  update ledger_entries           set created_at = t where created_at = now();
  update ledger_entries           set confirmed_at = t where confirmed_at = now();
  update ledger_entry_events      set created_at = t where created_at = now();
  update recovery_settlements     set created_at = t where created_at = now();
  update ledger_disputes          set created_at = t where created_at = now();
  update ledger_disputes          set last_activity_at = t where last_activity_at = now();
  update ledger_disputes          set closed_at = t where closed_at = now();
  update ledger_dispute_messages  set created_at = t where created_at = now();
  update ledger_dispute_proposals set created_at = t where created_at = now();
  update ledger_dispute_proposals set responded_at = t where responded_at = now();
$$;


do $$
declare
  sam  constant uuid := 'c0de0000-0000-4000-8000-000000000001';
  ana  constant uuid := 'c0de0000-0000-4000-8000-000000000002';
  mia  constant uuid := 'c0de0000-0000-4000-8000-000000000005';
  tom  constant uuid := 'c0de0000-0000-4000-8000-000000000006';
  gro  constant uuid := 'c0de0000-0000-4000-8000-000000000011';
  har  constant uuid := 'c0de0000-0000-4000-8000-000000000012';
  c1   constant uuid := 'c0de0000-0000-4000-8000-000000000201';
  c2   constant uuid := 'c0de0000-0000-4000-8000-000000000202';
  c4   constant uuid := 'c0de0000-0000-4000-8000-000000000204';
  c5   constant uuid := 'c0de0000-0000-4000-8000-000000000205';
  plan uuid;
  r uuid; d uuid; pr uuid;
  e1 uuid; e2 uuid; e3 uuid; e4 uuid; e5 uuid; e6 uuid; e7 uuid; e8 uuid;
  t timestamptz;
begin
  -- =================================================================
  -- 1. TideTrack x Growth Co.  "Busy"
  -- =================================================================
  t := now() - interval '38 days';
  select id into plan from cresco_plans where partnership_id = c1;

  perform pg_temp.act_as(sam);
  perform save_plan(plan,
    '<ul><li>Sam Patel: App Store optimisation and a launch push</li><li>Growth Co.: monthly sales data</li></ul>',
    '<ul><li>Sam Patel: share of net revenue, reviewed quarterly</li><li>Growth Co.: two campaigns a month</li></ul>',
    '[{"title":"Share App Store analytics access","owner_role":"builder","due_date":null,"status":"done"},
      {"title":"Launch social campaign for surf clubs","owner_role":"grower","due_date":null,"status":"in_progress"}]'::jsonb,
    '[{"measure":"Monthly downloads","target":"2,000","evidence":"App Store","review_date":null,"owner_role":"grower"}]'::jsonb);
  perform pg_temp.stamp(t); t := t + interval '1 day';
  perform agree_plan(plan, 1);
  perform pg_temp.act_as(gro);
  perform agree_plan(plan, 1);
  perform pg_temp.stamp(t); t := t + interval '10 days';

  -- Growth Co. edits it (version 2) and agrees; Sam hasn't yet.
  perform save_plan(plan,
    '<ul><li>Sam Patel: App Store optimisation and a launch push</li><li>Growth Co.: monthly sales data and premium early access</li></ul>',
    '<ul><li>Sam Patel: share of net revenue, reviewed quarterly</li><li>Growth Co.: two campaigns a month and an ASO review</li></ul>',
    '[{"title":"Share App Store analytics access","owner_role":"builder","due_date":null,"status":"done"},
      {"title":"Launch social campaign for surf clubs","owner_role":"grower","due_date":null,"status":"in_progress"},
      {"title":"Rewrite store listing and screenshots","owner_role":"grower","due_date":null,"status":"not_started"}]'::jsonb,
    '[{"measure":"Monthly downloads","target":"2,000","evidence":"App Store","review_date":null,"owner_role":"grower"},
      {"measure":"Premium subscribers","target":"150","evidence":"RevenueCat","review_date":null,"owner_role":"builder"}]'::jsonb);
  perform agree_plan(plan, 2);
  perform pg_temp.stamp(t); t := t + interval '1 day';

  -- Hourly rates: both agreed, then Growth Co. proposes a rise (Sam to answer).
  perform pg_temp.act_as(sam);
  r := propose_rate(c1, 40, true, 'My usual rate');
  perform pg_temp.act_as(gro);
  perform respond_rate(r, true);
  r := propose_rate(c1, 50, true, 'Studio rate');
  perform pg_temp.act_as(sam);
  perform respond_rate(r, true);
  update plan_rates set effective_from = (now() - interval '40 days')::date where partnership_id = c1;
  perform pg_temp.stamp(t); t := t + interval '1 day';

  -- Ledger.
  perform pg_temp.act_as(sam);
  e1 := add_ledger_entry(c1, (now() - interval '30 days')::date, 'revenue', 'builder', 'App Store sales, last month', 1240.00, null);
  e2 := add_ledger_entry(c1, (now() - interval '4 days')::date,  'revenue', 'builder', 'In-app subscriptions, this month so far', 610.00, null);
  perform pg_temp.act_as(gro);
  e3 := add_ledger_entry(c1, (now() - interval '25 days')::date, 'cost', 'grower', 'Social ads, launch campaign', 320.00,
                         'https://example.com/receipts/social-ads', p_cost_class => 'recoverable');
  e4 := add_ledger_entry(c1, (now() - interval '20 days')::date, 'time', 'grower', 'Campaign planning workshop', null, null,
                         p_hours => 4, p_cost_class => 'recoverable');
  perform pg_temp.stamp(t); t := t + interval '1 day';
  perform confirm_ledger_entry(e1);                       -- Growth Co. confirms Sam's sales
  perform pg_temp.act_as(sam);
  perform confirm_ledger_entry(e3);
  perform confirm_ledger_entry(e4);
  perform pg_temp.stamp(t);

  t := now() - interval '2 days';
  perform pg_temp.act_as(gro);
  perform query_ledger_entry(e2, 'Is this before or after Apple''s commission?');  -- Sam to answer
  e5 := add_ledger_entry(c1, (now() - interval '2 days')::date, 'cost', 'grower', 'Landing page design', 150.00,
                         'https://example.com/receipts/landing-page', p_cost_class => 'recoverable');  -- Sam to confirm
  r := propose_rate(c1, 55, false, 'New rate from next month');    -- Sam to answer
  perform pg_temp.stamp(t);

  -- =================================================================
  -- 2. Pocket Ledger x Harbour Digital  "Disputes"
  -- =================================================================
  t := now() - interval '58 days';
  select id into plan from cresco_plans where partnership_id = c2;
  perform pg_temp.act_as(ana);
  perform save_plan(plan,
    '<ul><li>Ana Ruiz: App Store optimisation and a paid ads test</li><li>Harbour Digital: access to download and revenue figures</li></ul>',
    '<ul><li>Ana Ruiz: 20% of net revenue from new users</li><li>Harbour Digital: up to 10 hours a month, at the agreed rate</li></ul>',
    '[]'::jsonb, '[]'::jsonb);
  perform agree_plan(plan, 1);
  perform pg_temp.act_as(har);
  perform agree_plan(plan, 1);
  perform pg_temp.stamp(t); t := t + interval '1 day';

  perform pg_temp.act_as(ana);
  r := propose_rate(c2, 45, true, 'My usual freelance rate');
  perform pg_temp.act_as(har);
  perform respond_rate(r, true);
  r := propose_rate(c2, 35, true, 'Agency rate for small clients');
  perform pg_temp.act_as(ana);
  perform respond_rate(r, true);
  update plan_rates set effective_from = (now() - interval '60 days')::date where partnership_id = c2;
  perform pg_temp.stamp(t); t := t + interval '1 day';

  perform pg_temp.act_as(ana);
  e1 := add_ledger_entry(c2, (now() - interval '35 days')::date, 'revenue', 'builder', 'Subscriptions, last month (App Store)', 612.40, null);
  e2 := add_ledger_entry(c2, (now() - interval '8 days')::date,  'revenue', 'builder', 'Subscriptions, this month to date', 488.15, null);
  e3 := add_ledger_entry(c2, (now() - interval '50 days')::date, 'cost', 'builder', 'Hosting', 24.00, 'INV-20931', p_cost_class => 'recoverable');
  e4 := add_ledger_entry(c2, (now() - interval '45 days')::date, 'time', 'builder', 'Built the referral screen the ads point to', null, null,
                         p_hours => 9, p_cost_class => 'recoverable');
  e5 := add_ledger_entry(c2, (now() - interval '55 days')::date, 'cost', 'builder', 'Analytics tool (annual)', 96.00, null, p_cost_class => 'recoverable');
  perform pg_temp.act_as(har);
  e6 := add_ledger_entry(c2, (now() - interval '30 days')::date, 'cost', 'grower', 'Paid ads test, week 1', 150.00,
                         'https://example.com/receipts/ads-week-1', p_cost_class => 'recoverable');
  e7 := add_ledger_entry(c2, (now() - interval '40 days')::date, 'time', 'grower', 'App Store listing rewrite and keywords', null, null,
                         p_hours => 14, p_cost_class => 'recoverable');
  e8 := add_ledger_entry(c2, (now() - interval '25 days')::date, 'time', 'grower', 'Ads report and next-step plan', null, null,
                         p_hours => 3, p_cost_class => 'recoverable');
  perform pg_temp.stamp(t); t := t + interval '1 hour';
  perform confirm_ledger_entry(x) from unnest(array[e1, e2, e3, e4, e5]) x;
  perform pg_temp.act_as(ana);
  perform confirm_ledger_entry(x) from unnest(array[e6, e7, e8]) x;
  perform pg_temp.stamp(t);

  t := now() - interval '24 days';
  -- C. Open, Harbour silent for 20+ days: Ana can close it without agreement.
  d := raise_dispute(c2, array[e8],
       'The ads report took about an hour to read; 3 hours seems high for a one-page summary.', 'Correct it to 1 hour');
  perform pg_temp.stamp(now() - interval '21 days');

  -- D. Resolved: the analytics tool voided by agreement.
  t := now() - interval '15 days';
  perform pg_temp.act_as(har);
  d := raise_dispute(c2, array[e5],
       'The analytics tool was bought before we started working together, so it shouldn''t be in this ledger.', 'Void it');
  perform pg_temp.stamp(t); t := t + interval '3 hours';
  perform pg_temp.act_as(ana);
  perform add_dispute_message(d, 'You''re right, I renewed it for my own use. Happy to void it.', null);
  perform pg_temp.stamp(t); t := t + interval '3 hours';
  pr := propose_dispute_resolution(d, jsonb_build_array(jsonb_build_object('entry_id', e5, 'action', 'void')), 'Bought before the partnership');
  perform pg_temp.stamp(t); t := t + interval '3 hours';
  perform pg_temp.act_as(har);
  perform respond_dispute_resolution(pr, true);
  perform pg_temp.stamp(t); t := t + interval '1 day';

  -- E. Withdrawn by the person who raised it.
  d := raise_dispute(c2, array[e2], 'Is this figure before or after Apple''s commission?', null);
  perform pg_temp.stamp(t); t := t + interval '3 hours';
  perform pg_temp.act_as(ana);
  perform add_dispute_message(d, 'After commission: it''s what was paid out to me.', null);
  perform pg_temp.stamp(t); t := t + interval '3 hours';
  perform pg_temp.act_as(har);
  perform withdraw_dispute(d);
  perform pg_temp.stamp(t); t := t + interval '1 day';

  -- B. Open, Harbour's proposed fix waiting for Ana.
  t := now() - interval '3 days';
  d := raise_dispute(c2, array[e3, e4],
       'The referral screen was going to be built anyway, so I don''t think it should be recoverable. And the hosting invoice says £20, not £24.',
       'Make the build Goodwill and correct hosting to £20');
  perform pg_temp.stamp(t); t := t + interval '3 hours';
  perform pg_temp.act_as(ana);
  perform add_dispute_message(d,
       'Fair point on hosting: VAT is reclaimed, so £20 is right. The referral screen was only built because the ads needed somewhere to land, so I think it is recoverable.',
       'https://example.com/receipts/INV-20931');
  perform pg_temp.stamp(t); t := t + interval '3 hours';
  perform pg_temp.act_as(har);
  perform add_dispute_message(d, 'Thanks. How about hosting to £20 and the build stays recoverable, but at 6 hours rather than 9?', null);
  perform pg_temp.stamp(t); t := t + interval '3 hours';
  pr := propose_dispute_resolution(d, jsonb_build_array(
          jsonb_build_object('entry_id', e3, 'action', 'correct', 'amount', 20),
          jsonb_build_object('entry_id', e4, 'action', 'correct', 'hours', 6)),
        'Hosting net of VAT; build time trimmed to the screen itself');
  perform pg_temp.stamp(t);

  -- A. Open, waiting for Harbour to give their side.
  t := now() - interval '5 hours';
  perform pg_temp.act_as(ana);
  d := raise_dispute(c2, array[e7],
       'The listing rewrite was logged as 14 hours, but our plan says up to 10 hours a month.', 'Correct it to 10 hours');
  perform pg_temp.stamp(t);

  -- Harbour has used all 3 free CrescoGuide summaries (on other disputes).
  insert into ai_usage (profile_id, feature, created_at)
  select har, 'dispute_summary', now() - (n || ' days')::interval from generate_series(10, 12) n;

  -- =================================================================
  -- 4. RunSplit x Growth Co.  "Agreed, money in"
  -- =================================================================
  t := now() - interval '48 days';
  select id into plan from cresco_plans where partnership_id = c4;
  perform pg_temp.act_as(gro);
  perform save_plan(plan,
    '<ul><li>Mia Hart: partnerships with running clubs</li><li>Growth Co.: monthly sales data</li></ul>',
    '<ul><li>Mia Hart: 15% of net revenue for a year</li><li>Growth Co.: club outreach and social content</li></ul>',
    '[{"title":"Contact 20 parkrun clubs","owner_role":"grower","due_date":null,"status":"done"},
      {"title":"Add club discount codes","owner_role":"builder","due_date":null,"status":"in_progress"}]'::jsonb,
    '[{"measure":"Club sign-ups","target":"500","evidence":"Discount code report","review_date":null,"owner_role":"both"}]'::jsonb);
  perform agree_plan(plan, 1);
  perform pg_temp.act_as(mia);
  perform agree_plan(plan, 1);
  perform pg_temp.stamp(t); t := t + interval '1 day';

  perform pg_temp.act_as(mia);
  r := propose_rate(c4, 40, true, null);
  perform pg_temp.act_as(gro);
  perform respond_rate(r, true);
  r := propose_rate(c4, 50, true, null);
  perform pg_temp.act_as(mia);
  perform respond_rate(r, true);
  update plan_rates set effective_from = (now() - interval '50 days')::date where partnership_id = c4;
  perform pg_temp.stamp(t); t := t + interval '1 day';

  perform pg_temp.act_as(mia);
  e1 := add_ledger_entry(c4, (now() - interval '20 days')::date, 'revenue', 'builder', 'Subscriptions, last month', 980.00, null);
  e2 := add_ledger_entry(c4, (now() - interval '40 days')::date, 'time', 'builder', 'Built club discount codes', null, null,
                         p_hours => 6, p_cost_class => 'goodwill');
  perform pg_temp.act_as(gro);
  e3 := add_ledger_entry(c4, (now() - interval '35 days')::date, 'cost', 'grower', 'Printed flyers for club nights', 180.00,
                         'https://example.com/receipts/flyers', p_cost_class => 'recoverable');
  e4 := add_ledger_entry(c4, (now() - interval '30 days')::date, 'time', 'grower', 'Club outreach calls', null, null,
                         p_hours => 8, p_cost_class => 'recoverable');
  e5 := add_ledger_entry(c4, (now() - interval '45 days')::date, 'time', 'grower', 'Early research before we teamed up', null, null,
                         p_hours => 5, p_cost_class => 'goodwill');
  perform pg_temp.stamp(t); t := t + interval '1 day';
  perform confirm_ledger_entry(e1);
  perform confirm_ledger_entry(e2);
  perform pg_temp.act_as(mia);
  perform confirm_ledger_entry(x) from unnest(array[e3, e4, e5]) x;
  perform pg_temp.stamp(t);

  t := now() - interval '1 day';
  -- Growth Co. records that Mia repaid the flyers: Mia to agree.
  perform pg_temp.act_as(gro);
  perform propose_recovery(c4, 'grower', 180.00, (now() - interval '1 day')::date, 'Paid by bank transfer', array[e3]);
  -- Mia asks to make her Goodwill build time Recoverable: Growth Co. to answer.
  perform pg_temp.act_as(mia);
  perform set_cost_class(e2, 'recoverable');
  perform pg_temp.stamp(t);

  -- =================================================================
  -- 5. QuietNotes x Harbour Digital  "Ended"
  -- =================================================================
  select id into plan from cresco_plans where partnership_id = c5;
  perform pg_temp.act_as(tom);
  perform save_plan(plan, '<ul><li>Tom Reid: paid ads</li></ul>', '<ul><li>Tom Reid: equity, to be discussed</li></ul>', '[]'::jsonb, '[]'::jsonb);
  perform add_ledger_entry(c5, (now() - interval '60 days')::date, 'cost', 'builder', 'Ad spend, test campaign', 75.00, null);
  perform pg_temp.stamp(now() - interval '80 days');
end $$;

-- Close the ended Cresco only now, so the setup above was allowed.
update partnerships set status = 'ended' where id = 'c0de0000-0000-4000-8000-000000000205';


-- ---------- Messages ----------
insert into messages (partnership_id, sender_id, body, created_at) values
  -- 1. TideTrack: last one from Growth Co., unread by Sam.
  ('c0de0000-0000-4000-8000-000000000201', 'c0de0000-0000-4000-8000-000000000001', 'Welcome aboard! Analytics access is shared.', now() - interval '37 days'),
  ('c0de0000-0000-4000-8000-000000000201', 'c0de0000-0000-4000-8000-000000000011', 'Thanks Sam. First campaign goes out on Friday.', now() - interval '36 days'),
  ('c0de0000-0000-4000-8000-000000000201', 'c0de0000-0000-4000-8000-000000000011', 'I''ve updated the plan with the store listing work. Can you take a look and agree when you get a minute?', now() - interval '3 hours'),
  -- 2. Pocket Ledger: all read.
  ('c0de0000-0000-4000-8000-000000000202', 'c0de0000-0000-4000-8000-000000000012', 'Ads test is live.', now() - interval '30 days'),
  ('c0de0000-0000-4000-8000-000000000202', 'c0de0000-0000-4000-8000-000000000002', 'Great, thanks.', now() - interval '29 days'),
  -- 4. RunSplit: last one from Mia, unread by Growth Co.
  ('c0de0000-0000-4000-8000-000000000204', 'c0de0000-0000-4000-8000-000000000011', 'Club nights went well. Flyers receipt is in the ledger.', now() - interval '30 days'),
  ('c0de0000-0000-4000-8000-000000000204', 'c0de0000-0000-4000-8000-000000000005', 'Paid you back for the flyers yesterday. I''ve also asked to make my build time Recoverable.', now() - interval '20 hours'),
  -- 5. QuietNotes (ended).
  ('c0de0000-0000-4000-8000-000000000205', 'c0de0000-0000-4000-8000-000000000006', 'Thanks for everything, Harbour.', now() - interval '10 days');

-- Read markers: everyone has read everything up to the times below.
insert into message_reads (partnership_id, profile_id, last_read_at) values
  ('c0de0000-0000-4000-8000-000000000201', 'c0de0000-0000-4000-8000-000000000001', now() - interval '30 days'),
  ('c0de0000-0000-4000-8000-000000000201', 'c0de0000-0000-4000-8000-000000000011', now() - interval '3 hours'),
  ('c0de0000-0000-4000-8000-000000000202', 'c0de0000-0000-4000-8000-000000000002', now() - interval '1 day'),
  ('c0de0000-0000-4000-8000-000000000202', 'c0de0000-0000-4000-8000-000000000012', now() - interval '1 day'),
  ('c0de0000-0000-4000-8000-000000000204', 'c0de0000-0000-4000-8000-000000000005', now() - interval '20 hours'),
  ('c0de0000-0000-4000-8000-000000000204', 'c0de0000-0000-4000-8000-000000000011', now() - interval '25 days'),
  ('c0de0000-0000-4000-8000-000000000205', 'c0de0000-0000-4000-8000-000000000006', now() - interval '10 days'),
  ('c0de0000-0000-4000-8000-000000000205', 'c0de0000-0000-4000-8000-000000000012', now() - interval '9 days');

commit;


-- ---------- What was loaded ----------
select l.title || ' x ' || g.full_name as cresco, p.status, cp.version as plan_version, cp.ledger_currency as currency,
       (select count(*) from ledger_entries e where e.partnership_id = p.id) as entries,
       (select count(*) from ledger_disputes d where d.partnership_id = p.id and d.status = 'open') as open_disputes
  from partnerships p
  join listings l on l.id = p.listing_id
  join profiles g on g.id = p.grower_id
  join cresco_plans cp on cp.partnership_id = p.id
 where p.id::text like 'c0de0000-0000-4000-8000-0000000002%'
 order by p.id;
