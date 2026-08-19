-- ============================================================
-- Full reset + rebuild for Crescopus schema v2.
-- Safe to run regardless of how far a previous attempt got —
-- everything below is drop-if-exists, then create fresh.
-- ============================================================

drop table if exists reviews cascade;
drop table if exists messages cascade;
drop table if exists revenue_events cascade;
drop table if exists revenue_reports cascade;
drop table if exists partnerships cascade;
drop table if exists proposals cascade;
drop table if exists revenue_streams cascade;
drop table if exists listings cascade;
drop table if exists profiles cascade;
drop function if exists public.handle_new_user() cascade;
drop type if exists listing_status;
drop type if exists proposal_status;
drop type if exists partnership_status;
drop type if exists revenue_source;
drop type if exists stream_type;
drop type if exists stream_status;
drop type if exists report_source;

-- Crescopus schema v2
-- No money moves through Crescopus. Revenue is tracked and verified where
-- possible (RevenueCat), self-reported otherwise; Crescopus computes the
-- split and produces a settlement record. Settlement happens directly
-- between the two parties, off-platform.

create extension if not exists "uuid-ossp";

create type stream_type as enum ('store_iap', 'web_revenuecat', 'advertising', 'existing_processor', 'other');
create type stream_status as enum ('draft', 'open', 'matched', 'archived');
create type proposal_status as enum ('pending', 'withdrawn', 'accepted', 'declined');
create type partnership_status as enum ('active', 'ended', 'bought_out');
create type report_source as enum ('revenuecat', 'manual');

-- One row per auth.users id. A person can be a developer, a grower, or both.
create table profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text not null,
  headline text,
  bio text,
  is_developer boolean not null default false,
  is_grower boolean not null default false,
  avatar_url text,
  links jsonb default '{}'::jsonb,
  track_record jsonb default '{}'::jsonb,
  country text,
  created_at timestamptz not null default now()
);

-- The app itself. Monetisation detail (streams, terms, partners) lives
-- one level down in revenue_streams, since a single app can be split
-- across several independent channels.
create table listings (
  id uuid primary key default uuid_generate_v4(),
  developer_id uuid not null references profiles(id) on delete cascade,
  title text not null,
  tagline text,
  description text,
  category text,
  platform text,
  store_urls jsonb default '{}'::jsonb,
  metrics jsonb default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- One monetisation channel on a listing. A listing can have zero streams
-- (published bare, streams added later by the developer or proposed by a
-- grower) or several, each independently matched.
create table revenue_streams (
  id uuid primary key default uuid_generate_v4(),
  listing_id uuid not null references listings(id) on delete cascade,
  stream_type stream_type not null,
  status stream_status not null default 'draft',
  created_by uuid not null references profiles(id) on delete cascade,
  min_revenue_share numeric(5,2),
  looking_for text,
  control_boundaries text,
  revenuecat_project_key text,
  notes text,
  created_at timestamptz not null default now()
);

create table proposals (
  id uuid primary key default uuid_generate_v4(),
  revenue_stream_id uuid not null references revenue_streams(id) on delete cascade,
  grower_id uuid not null references profiles(id) on delete cascade,
  revenue_share_offered numeric(5,2) not null,
  growth_plan text not null,
  track_record_summary text,
  budget_commitment text,
  term_length_months int,
  status proposal_status not null default 'pending',
  created_at timestamptz not null default now()
);

-- One partnership = one (revenue_stream, grower) pairing. A single app can
-- have entirely different growers, terms, and outcomes on different
-- streams, running independently of each other.
create table partnerships (
  id uuid primary key default uuid_generate_v4(),
  revenue_stream_id uuid not null references revenue_streams(id) on delete cascade,
  proposal_id uuid references proposals(id) on delete set null,
  developer_id uuid not null references profiles(id) on delete cascade,
  grower_id uuid not null references profiles(id) on delete cascade,
  revenue_share numeric(5,2) not null,
  decision_rights text,
  term_length_months int,
  buyout_terms text,
  agreement_doc_url text,
  status partnership_status not null default 'active',
  started_at timestamptz not null default now(),
  ended_at timestamptz,
  ended_by uuid references profiles(id),
  end_reason text
);

-- Periodic settlement record. Crescopus computes the split and shows what's
-- owed — it never moves the money itself.
create table revenue_reports (
  id uuid primary key default uuid_generate_v4(),
  partnership_id uuid not null references partnerships(id) on delete cascade,
  period_start date not null,
  period_end date not null,
  gross_amount numeric(12,2) not null,
  developer_share numeric(12,2) not null,
  grower_share numeric(12,2) not null,
  currency text not null default 'usd',
  source report_source not null,
  verified boolean not null default false,
  reported_by uuid references profiles(id),
  settled boolean not null default false,
  settled_at timestamptz,
  created_at timestamptz not null default now()
);

create table messages (
  id uuid primary key default uuid_generate_v4(),
  revenue_stream_id uuid references revenue_streams(id) on delete cascade,
  proposal_id uuid references proposals(id) on delete cascade,
  partnership_id uuid references partnerships(id) on delete cascade,
  sender_id uuid not null references profiles(id) on delete cascade,
  body text not null,
  created_at timestamptz not null default now()
);

create table reviews (
  id uuid primary key default uuid_generate_v4(),
  partnership_id uuid not null references partnerships(id) on delete cascade,
  reviewer_id uuid not null references profiles(id) on delete cascade,
  reviewee_id uuid not null references profiles(id) on delete cascade,
  rating int not null check (rating between 1 and 5),
  comment text,
  created_at timestamptz not null default now()
);

-- ---------- Row level security ----------
alter table profiles enable row level security;
alter table listings enable row level security;
alter table revenue_streams enable row level security;
alter table proposals enable row level security;
alter table partnerships enable row level security;
alter table revenue_reports enable row level security;
alter table messages enable row level security;
alter table reviews enable row level security;

create policy "Profiles are viewable by everyone"
  on profiles for select using (true);

create policy "Users can insert their own profile"
  on profiles for insert with check (auth.uid() = id);

create policy "Users can update their own profile"
  on profiles for update using (auth.uid() = id);

create policy "Listings are public"
  on listings for select using (true);

create policy "Developers create their own listings"
  on listings for insert with check (developer_id = auth.uid());

create policy "Developers update their own listings"
  on listings for update using (developer_id = auth.uid());

create policy "Open streams are public, drafts are private to the developer"
  on revenue_streams for select using (
    status != 'draft'
    or listing_id in (select id from listings where developer_id = auth.uid())
  );

create policy "Developers create streams on their own listings"
  on revenue_streams for insert with check (
    listing_id in (select id from listings where developer_id = auth.uid())
    or created_by = auth.uid()
  );

create policy "Involved parties update a stream"
  on revenue_streams for update using (
    listing_id in (select id from listings where developer_id = auth.uid())
  );

create policy "Proposals visible to the grower and the stream's developer"
  on proposals for select using (
    grower_id = auth.uid()
    or revenue_stream_id in (
      select rs.id from revenue_streams rs
      join listings l on l.id = rs.listing_id
      where l.developer_id = auth.uid()
    )
  );

create policy "Growers submit their own proposals"
  on proposals for insert with check (grower_id = auth.uid());

create policy "Involved parties update a proposal"
  on proposals for update using (
    grower_id = auth.uid()
    or revenue_stream_id in (
      select rs.id from revenue_streams rs
      join listings l on l.id = rs.listing_id
      where l.developer_id = auth.uid()
    )
  );

create policy "Partnerships visible to both parties only"
  on partnerships for select using (developer_id = auth.uid() or grower_id = auth.uid());

create policy "Involved parties create a partnership"
  on partnerships for insert with check (developer_id = auth.uid() or grower_id = auth.uid());

create policy "Involved parties update a partnership"
  on partnerships for update using (developer_id = auth.uid() or grower_id = auth.uid());

create policy "Revenue reports visible to both parties"
  on revenue_reports for select using (
    partnership_id in (
      select id from partnerships where developer_id = auth.uid() or grower_id = auth.uid()
    )
  );

create policy "Involved parties file a revenue report"
  on revenue_reports for insert with check (
    partnership_id in (
      select id from partnerships where developer_id = auth.uid() or grower_id = auth.uid()
    )
  );

create policy "Involved parties update a revenue report"
  on revenue_reports for update using (
    partnership_id in (
      select id from partnerships where developer_id = auth.uid() or grower_id = auth.uid()
    )
  );

create policy "Messages visible to involved parties"
  on messages for select using (
    sender_id = auth.uid()
    or partnership_id in (select id from partnerships where developer_id = auth.uid() or grower_id = auth.uid())
    or revenue_stream_id in (
      select rs.id from revenue_streams rs
      join listings l on l.id = rs.listing_id
      where l.developer_id = auth.uid()
    )
    or proposal_id in (select id from proposals where grower_id = auth.uid())
  );

create policy "Users send their own messages"
  on messages for insert with check (sender_id = auth.uid());

create policy "Reviews are public"
  on reviews for select using (true);

create policy "Involved parties leave a review"
  on reviews for insert with check (reviewer_id = auth.uid());

-- ---------- Auto-create the profile row on signup ----------
create function public.handle_new_user()
returns trigger as $$
begin
  insert into public.profiles (id, full_name, is_developer, is_grower, country)
  values (
    new.id,
    coalesce(new.raw_user_meta_data->>'full_name', ''),
    coalesce((new.raw_user_meta_data->>'is_developer')::boolean, false),
    coalesce((new.raw_user_meta_data->>'is_grower')::boolean, false),
    new.raw_user_meta_data->>'country'
  );
  return new;
end;
$$ language plpgsql security definer set search_path = public;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();
