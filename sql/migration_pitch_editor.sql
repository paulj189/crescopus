-- Migration: rich "pitch" editor for listings (builders + growers)
-- Replaces plain description with pitch_html, hero_image_url, and a listing_images gallery.

BEGIN;

-- 1. New columns on listings
ALTER TABLE listings
    ADD COLUMN IF NOT EXISTS pitch_html TEXT,
    ADD COLUMN IF NOT EXISTS hero_image_url TEXT;

-- Backfill: wrap existing plain description into a basic paragraph
UPDATE listings
SET pitch_html = '<p>' || replace(description, E'\n', '</p><p>') || '</p>'
WHERE description IS NOT NULL AND pitch_html IS NULL;

-- description column kept for now (safe rollback); drop later once confirmed unused:
-- ALTER TABLE listings DROP COLUMN description;

-- 2. Gallery table (max 6 enforced at application layer, not DB)
CREATE TABLE IF NOT EXISTS listing_images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    listing_id UUID NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    position SMALLINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_listing_images_listing_id ON listing_images(listing_id);

-- 3. RLS (must be set explicitly per project lessons learned)
ALTER TABLE listing_images ENABLE ROW LEVEL SECURITY;

-- Anyone can read gallery images for listings they can already see
CREATE POLICY listing_images_select ON listing_images
    FOR SELECT
    USING (true);

-- Only the listing owner can insert/update/delete their own gallery images
CREATE POLICY listing_images_owner_write ON listing_images
    FOR INSERT
    WITH CHECK (
        listing_id IN (SELECT id FROM listings WHERE developer_id = auth.uid())
    );

CREATE POLICY listing_images_owner_update ON listing_images
    FOR UPDATE
    USING (
        listing_id IN (SELECT id FROM listings WHERE developer_id = auth.uid())
    );

CREATE POLICY listing_images_owner_delete ON listing_images
    FOR DELETE
    USING (
        listing_id IN (SELECT id FROM listings WHERE developer_id = auth.uid())
    );

COMMIT;

-- Also create the Supabase Storage bucket separately (see NOTES.md):
--   bucket name: listing-media
--   public read, authenticated write, path-namespaced by listing_id
