-- Optional cleanup: the listing_images gallery table is no longer used —
-- images are now inserted inline into pitch_html via the advert editor.
-- Only run this once you're confident you don't want it back.

DROP TABLE IF EXISTS listing_images;
