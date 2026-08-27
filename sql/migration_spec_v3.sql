-- Spec v3: ice-breaker first. Run this in the Supabase SQL editor.
-- Fully self-contained — safe to run regardless of which earlier migrations
-- (if any) you already applied, since every step here is idempotent
-- (IF NOT EXISTS / guarded conditional alters throughout).

-- Public self-description, for both builders and growers.
alter table profiles add column if not exists bio text;

-- RevenueCat represents one project per app, not per revenue stream, so the
-- integration key belongs on the listing.
alter table listings add column if not exists revenuecat_project_key text;

-- Connection requests replace the old "proposals" concept entirely.
-- Direction-agnostic: works whether a grower reaches out to a listing, or a
-- builder reaches out to a grower for one of their own listings.
create table if not exists connection_requests (
    id uuid primary key default gen_random_uuid(),
    listing_id uuid not null references listings(id),
    grower_id uuid not null references profiles(id),
    initiated_by uuid not null references profiles(id),
    message text not null,
    status text not null default 'pending', -- pending | accepted | rejected
    reject_reason text,
    created_at timestamptz not null default now(),
    responded_at timestamptz
);

-- Ensure partnerships has listing_id (from the earlier per-listing-pitch
-- migration) — added here too in case that migration was never run.
alter table partnerships add column if not exists listing_id uuid references listings(id);

-- Ensure revenue_stream_id exists (older schema) then make it optional —
-- CrescoPacts are no longer tied to a specific stream.
alter table partnerships add column if not exists revenue_stream_id uuid references revenue_streams(id);
alter table partnerships alter column revenue_stream_id drop not null;

-- Partnerships become CrescoPacts with a trial/formalised lifecycle.
-- status: trial | formalised | disconnected | ended
alter table partnerships add column if not exists connection_request_id uuid references connection_requests(id);
alter table partnerships add column if not exists revenue_share numeric;
alter table partnerships alter column revenue_share drop not null;
alter table partnerships add column if not exists formalise_status text not null default 'none'; -- none | proposed | declined
alter table partnerships add column if not exists formalise_proposed_by uuid references profiles(id);
alter table partnerships add column if not exists formalise_declined_reason text;
alter table partnerships add column if not exists disconnected_at timestamptz;
alter table partnerships add column if not exists disconnected_by uuid references profiles(id);
alter table partnerships add column if not exists disconnect_reason text;

-- If your `partnerships.status` column has a CHECK constraint limiting it to
-- old values (e.g. 'active'/'ended'), you'll need to widen or drop it so it
-- accepts: trial | formalised | disconnected | ended. Check first with:
--   select conname, pg_get_constraintdef(oid) from pg_constraint
--   where conrelid = 'partnerships'::regclass;
-- Then, if one exists (replace the name from the query above):
--   alter table partnerships drop constraint <constraint_name>;

-- In-app messaging within a CrescoPact (trial or formalised).
create table if not exists messages (
    id uuid primary key default gen_random_uuid(),
    partnership_id uuid not null references partnerships(id),
    sender_id uuid not null references profiles(id),
    body text not null,
    created_at timestamptz not null default now()
);

-- Engagement metrics (views/clicks/downloads) — self-reported, lets both
-- sides see traction before there's any revenue to report.
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
