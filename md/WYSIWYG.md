# Pitch editor — integration notes

## Files
- `migration_pitch_editor.sql` — run against Supabase. RLS policies use
  `developer_id` (confirmed from your `listings` table schema).
- `static/js/pitch-editor.js` — TipTap editor, curated toolbar + font picker.
- `static/js/image-uploader.js` — compression, 2MB cap with messaging,
  gallery capped at 6, Supabase Storage upload.

## Still needed on your side
1. Create the `listing-media` Storage bucket in Supabase (public read,
   authenticated write).
2. `npm install @tiptap/core @tiptap/starter-kit @tiptap/extension-link
   @tiptap/extension-text-style @tiptap/extension-font-family` (or CDN
   equivalents if you're not bundling JS yet).
3. Wire `pitch-editor.js` into the listing edit template, saving
   `editor.getHTML()` into `pitch_html` on submit.
4. Wire `image-uploader.js` into hero/gallery upload UI, saving
   `hero_image_url` and inserting into `listing_images`.
5. Update the listing display template to render `pitch_html` (sanitise
   server-side before render — TipTap output is clean but don't trust
   client input blindly) plus hero + gallery.
6. Style the "View website" link as a proper button (from earlier
   discussion) — separate small CSS change, not included here.

Once you've had a look, happy to help wire any of these into the actual
templates/routes.
