-- =====================================================================
-- Crescopus: editable Needs / Offers tags
-- Run in the Supabase SQL editor. Safe to re-run (it never overwrites
-- labels you've already changed).
--
-- After this, edit the tags in Supabase > Table Editor > tag_options:
--   label      what people see on cards and filters — rename freely
--   tag_group  'growth'  = growth help (Builders need it, Growers offer it)
--              'support' = support/terms (Builders offer it, Growers need it)
--   position   order within its list (lower first)
--   active     untick to hide from filters and edit forms; cards that
--              already have it keep it
--   slug       the fixed code stored on cards. To add a tag, insert a row
--              with a new slug (lower case, numbers and _ only, e.g.
--              "email_marketing"). Don't change the slug of an existing
--              row — cards that use it would lose their label.
-- Changes show on the site within 5 minutes.
-- =====================================================================

create table if not exists tag_options (
  slug       text primary key check (slug ~ '^[a-z0-9_]{2,40}$'),
  label      text not null check (length(trim(label)) between 1 and 40),
  tag_group  text not null check (tag_group in ('growth', 'support')),
  position   integer not null default 100,
  active     boolean not null default true,
  created_at timestamptz not null default now()
);

alter table tag_options enable row level security;

drop policy if exists "Tag options are public" on tag_options;
create policy "Tag options are public"
  on tag_options for select using (true);
-- No insert/update/delete policies: edited in the Supabase dashboard only.

insert into tag_options (slug, label, tag_group, position) values
  ('app_store_growth', 'App Store growth', 'growth', 10),
  ('social',           'Social',           'growth', 20),
  ('paid_ads',         'Paid ads',         'growth', 30),
  ('influencers',      'Influencers',      'growth', 40),
  ('partnerships',     'Partnerships',     'growth', 50),
  ('content',          'Content',          'growth', 60),
  ('seo',              'SEO',              'growth', 70),
  ('revenue_share',    'Revenue share',    'support', 10),
  ('equity',           'Equity',           'support', 20),
  ('roadmap_input',    'Roadmap input',    'support', 30),
  ('analytics_access', 'Analytics access', 'support', 40),
  ('product_access',   'Product access',   'support', 50),
  ('ad_budget',        'Ad budget',        'support', 60),
  ('creative_assets',  'Creative assets',  'support', 70)
on conflict (slug) do nothing;
