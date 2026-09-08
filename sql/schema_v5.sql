-- Crescopus schema v5 — CrescoGap, proving mechanics, tracking snippet.
-- Draft for review. Assumes a clean/empty database (post-reset).
-- Does NOT yet include revenue_streams/proposals — pending your decision
-- on whether to drop that legacy feature (see chat).

create extension if not exists "uuid-ossp";
create extension if not exists "pgcrypto"; -- for gen_random_uuid()

-- ---------- Core ----------

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

-- The app itself.
create table listings (
  id uuid primary key default gen_random_uuid(),
  developer_id uuid not null references profiles(id) on delete cascade,
  title text not null,
  tagline text,
  description text,
  category text,
  platform text,
  store_urls jsonb default '{}'::jsonb,
  metrics jsonb default '{}'::jsonb,
  revenuecat_project_key text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Ice-breaker connection between a grower and a listing. Direction-agnostic.
create table connection_requests (
  id uuid primary key default gen_random_uuid(),
  listing_id uuid not null references listings(id) on delete cascade,
  grower_id uuid not null references profiles(id) on delete cascade,
  initiated_by uuid not null references profiles(id) on delete cascade,
  message text not null,
  status text not null default 'pending', -- pending | accepted | rejected
  reject_reason text,
  created_at timestamptz not null default now(),
  responded_at timestamptz
);

-- ---------- CrescoPact ----------

-- One CrescoPact = one (listing, grower) pairing, from Trial through to
-- Formalised/Disconnected/Ended. Deal terms (Sections 4-6 of the master
-- spec) live here.
create table partnerships (
  id uuid primary key default gen_random_uuid(),
  listing_id uuid not null references listings(id) on delete cascade,
  connection_request_id uuid references connection_requests(id) on delete set null,
  developer_id uuid not null references profiles(id) on delete cascade,
  grower_id uuid not null references profiles(id) on delete cascade,

  status text not null default 'trial', -- trial | formalised | disconnected | ended

  -- Deal type. Defaults to revenue_share; can be changed later by mutual
  -- agreement while the CrescoPact is still a Trial or Formalised (not once
  -- ended). CrescoGap, proving, and revenue_reports only apply when this is
  -- 'revenue_share' — Crescopus takes no role in equity_share terms.
  deal_type text not null default 'revenue_share', -- revenue_share | equity_share

  -- CrescoGap (revenue_share only). Current state of the negotiation; full
  -- history of proposals lives in gap_offers.
  builder_position numeric(5,2), -- % of revenue the builder is willing to release
  grower_position numeric(5,2),  -- % of revenue the grower requires
  agreed_share numeric(5,2),     -- % locked in once both sides agree — feeds revenue_reports

  -- Proving (revenue_share only, optional — single metric per CrescoPact).
  proving_metric text,     -- unique_visitors | registrations | subscriptions | interactions
  proving_threshold integer,
  proving_page_url text,
  proving_verified boolean not null default false,
  proving_verified_at timestamptz,

  -- Formalise propose/accept flow.
  formalise_status text not null default 'none', -- none | proposed | declined
  formalise_proposed_by uuid references profiles(id),
  formalise_declined_reason text,

  -- Disconnect (Trial only).
  disconnected_at timestamptz,
  disconnected_by uuid references profiles(id),
  disconnect_reason text,

  -- End (Formalised only).
  started_at timestamptz not null default now(),
  ended_at timestamptz,
  ended_by uuid references profiles(id),
  end_reason text
);

-- Only one Formalised CrescoPact per listing at a time (existing app-level
-- rule in formalise_accept — enforced here too as a safety net).
create unique index one_formalised_partnership_per_listing
  on partnerships (listing_id)
  where status = 'formalised';

-- CrescoGap negotiation history. Append-only log — every proposed position
-- from either party, timestamped, visible to both (spec Section 5).
create table gap_offers (
  id uuid primary key default gen_random_uuid(),
  partnership_id uuid not null references partnerships(id) on delete cascade,
  proposed_by uuid not null references profiles(id) on delete cascade,
  builder_position numeric(5,2) not null,
  grower_position numeric(5,2) not null,
  note text,
  created_at timestamptz not null default now()
);

-- ---------- Growth verification / RUM (spec Sections 6-7) ----------

-- One snippet per CrescoPact. snippet_key is the public token embedded in
-- the builder's page — never expose partnership_id itself client-side.
create table tracking_snippets (
  id uuid primary key default gen_random_uuid(),
  partnership_id uuid not null unique references partnerships(id) on delete cascade,
  snippet_key text not null unique default encode(gen_random_bytes(12), 'hex'),
  created_at timestamptz not null default now()
);

-- Raw pings from the tracking snippet. Kept granular (not pre-aggregated)
-- so unique-visitor counts can be computed accurately and the anti-gaming
-- checks (rate limiting, visitor_id/IP pattern review) have real data to
-- work with. Aggregate on read.
create table tracking_events (
  id uuid primary key default gen_random_uuid(),
  snippet_key text not null references tracking_snippets(snippet_key) on delete cascade,
  event_type text not null default 'pageview', -- pageview | (future: registration, subscription, interaction)
  visitor_id text not null,   -- random id set by the snippet in the builder's page (first-party, localStorage)
  page_url text,
  ip_hash text,                -- hashed, not raw IP — for basic anti-gaming pattern checks only
  created_at timestamptz not null default now()
);
create index tracking_events_snippet_created_idx on tracking_events (snippet_key, created_at);

-- Self-reported engagement (views/clicks/downloads) — kept as a lighter,
-- non-verified supplement. NOT used to satisfy proving_threshold; only the
-- tracking_events pixel counts toward proving verification.
create table engagement_reports (
  id uuid primary key default gen_random_uuid(),
  partnership_id uuid not null references partnerships(id) on delete cascade,
  period_start date not null,
  period_end date not null,
  views integer,
  clicks integer,
  downloads integer,
  notes text,
  reported_by uuid not null references profiles(id) on delete cascade,
  created_at timestamptz not null default now()
);

-- ---------- Settlement, messaging, reviews ----------

-- Periodic settlement record. Crescopus computes the split and shows what's
-- owed — it never moves the money itself. Uses partnerships.agreed_share.
create table revenue_reports (
  id uuid primary key default gen_random_uuid(),
  partnership_id uuid not null references partnerships(id) on delete cascade,
  period_start date not null,
  period_end date not null,
  gross_amount numeric(12,2) not null,
  developer_share numeric(12,2) not null,
  grower_share numeric(12,2) not null,
  currency text not null default 'usd',
  source text not null, -- revenuecat | manual
  verified boolean not null default false,
  reported_by uuid references profiles(id),
  settled boolean not null default false,
  settled_at timestamptz,
  created_at timestamptz not null default now()
);

create table messages (
  id uuid primary key default gen_random_uuid(),
  partnership_id uuid not null references partnerships(id) on delete cascade,
  sender_id uuid not null references profiles(id) on delete cascade,
  body text not null,
  created_at timestamptz not null default now()
);

create table reviews (
  id uuid primary key default gen_random_uuid(),
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
alter table connection_requests enable row level security;
alter table partnerships enable row level security;
alter table gap_offers enable row level security;
alter table tracking_snippets enable row level security;
alter table tracking_events enable row level security;
alter table engagement_reports enable row level security;
alter table revenue_reports enable row level security;
alter table messages enable row level security;
alter table reviews enable row level security;

create policy "Profiles are viewable by everyone" on profiles for select using (true);
create policy "Users can insert their own profile" on profiles for insert with check (auth.uid() = id);
create policy "Users can update their own profile" on profiles for update using (auth.uid() = id);

create policy "Listings are public" on listings for select using (true);
create policy "Developers create their own listings" on listings for insert with check (developer_id = auth.uid());
create policy "Developers update their own listings" on listings for update using (developer_id = auth.uid());

create policy "Connection requests visible to grower and listing owner"
  on connection_requests for select using (
    grower_id = auth.uid()
    or listing_id in (select id from listings where developer_id = auth.uid())
  );
create policy "Either side can initiate a connection request"
  on connection_requests for insert with check (initiated_by = auth.uid());
create policy "Involved parties respond to a connection request"
  on connection_requests for update using (
    grower_id = auth.uid()
    or listing_id in (select id from listings where developer_id = auth.uid())
  );

create policy "Partnerships visible to both parties only"
  on partnerships for select using (developer_id = auth.uid() or grower_id = auth.uid());
create policy "Involved parties create a partnership"
  on partnerships for insert with check (developer_id = auth.uid() or grower_id = auth.uid());
create policy "Involved parties update a partnership"
  on partnerships for update using (developer_id = auth.uid() or grower_id = auth.uid());

create policy "Gap offers visible to both parties"
  on gap_offers for select using (
    partnership_id in (select id from partnerships where developer_id = auth.uid() or grower_id = auth.uid())
  );
create policy "Involved parties propose a gap offer"
  on gap_offers for insert with check (
    proposed_by = auth.uid()
    and partnership_id in (select id from partnerships where developer_id = auth.uid() or grower_id = auth.uid())
  );

create policy "Tracking snippet visible to both parties"
  on tracking_snippets for select using (
    partnership_id in (select id from partnerships where developer_id = auth.uid() or grower_id = auth.uid())
  );
create policy "Involved parties create their tracking snippet"
  on tracking_snippets for insert with check (
    partnership_id in (select id from partnerships where developer_id = auth.uid() or grower_id = auth.uid())
  );

-- tracking_events is written by the public ping endpoint using the service
-- role (bypasses RLS), not by logged-in users directly — so only a select
-- policy is needed here, for the dashboard to read its own counts.
create policy "Tracking events visible to both parties on that CrescoPact"
  on tracking_events for select using (
    snippet_key in (
      select ts.snippet_key from tracking_snippets ts
      join partnerships p on p.id = ts.partnership_id
      where p.developer_id = auth.uid() or p.grower_id = auth.uid()
    )
  );

create policy "Engagement reports visible to both parties"
  on engagement_reports for select using (
    partnership_id in (select id from partnerships where developer_id = auth.uid() or grower_id = auth.uid())
  );
create policy "Involved parties file an engagement report"
  on engagement_reports for insert with check (
    partnership_id in (select id from partnerships where developer_id = auth.uid() or grower_id = auth.uid())
  );

create policy "Revenue reports visible to both parties"
  on revenue_reports for select using (
    partnership_id in (select id from partnerships where developer_id = auth.uid() or grower_id = auth.uid())
  );
create policy "Involved parties file a revenue report"
  on revenue_reports for insert with check (
    partnership_id in (select id from partnerships where developer_id = auth.uid() or grower_id = auth.uid())
  );
create policy "Involved parties update a revenue report"
  on revenue_reports for update using (
    partnership_id in (select id from partnerships where developer_id = auth.uid() or grower_id = auth.uid())
  );

create policy "Messages visible to involved parties"
  on messages for select using (
    partnership_id in (select id from partnerships where developer_id = auth.uid() or grower_id = auth.uid())
  );
create policy "Users send their own messages"
  on messages for insert with check (sender_id = auth.uid());

create policy "Reviews are public" on reviews for select using (true);
create policy "Involved parties leave a review" on reviews for insert with check (reviewer_id = auth.uid());

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
