-- Adds the same rich "pitch" fields to profiles (builders + growers)
-- that listings already have. bio column is kept for backward compatibility
-- as a fallback for any profile that hasn't set a pitch yet.

ALTER TABLE profiles
    ADD COLUMN IF NOT EXISTS pitch_html TEXT,
    ADD COLUMN IF NOT EXISTS hero_image_url TEXT;

-- Backfill: wrap any existing plain bio into a basic paragraph
UPDATE profiles
SET pitch_html = '<p>' || replace(bio, E'\n', '</p><p>') || '</p>'
WHERE bio IS NOT NULL AND pitch_html IS NULL;
