-- Run this in the Supabase SQL editor before deploying the app code changes.
-- It lets pitches and CrescoPacts target a whole listing instead of a specific
-- revenue stream, while keeping the old revenue_stream_id columns around
-- (now optional) for any existing data and for future per-stream reporting detail.

alter table proposals add column if not exists listing_id uuid references listings(id);
alter table proposals alter column revenue_stream_id drop not null;

alter table partnerships add column if not exists listing_id uuid references listings(id);
alter table partnerships alter column revenue_stream_id drop not null;

-- RevenueCat represents one project per app, not per revenue stream, so the
-- integration key belongs on the listing, not on an individual stream.
alter table listings add column if not exists revenuecat_project_key text;

-- Engagement metrics (views/clicks/downloads) let both sides see traction on
-- a CrescoPact before there's any revenue to report — self-reported only,
-- RevenueCat doesn't track this kind of data.
create table if not exists engagement_reports (
    id uuid primary key default gen_random_uuid(),
    partnership_id uuid not null references partnerships(id),
    period_start date not null,
    period_end date not null,
    views integer,
    clicks integer,
    downloads integer,
    notes text,
    reported_by uuid not null references profiles(id),
    created_at timestamptz not null default now()
);
