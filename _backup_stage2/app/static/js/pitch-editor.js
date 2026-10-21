// pitch-editor.js
// TinyMCE-based rich "advert" editor — text, images, and fonts flow together
// in one canvas, with a polished icon toolbar out of the box.
// Requires tinymce.min.js loaded globally first (see base.html) — self-hosted,
// no API key or custom build needed.

// Curated font set — matches Crescopus brand fonts + approved pairings.
export const CRESCOPUS_FONTS = [
    { label: 'Fraunces (heading)', value: '"Fraunces", serif' },
    { label: 'Public Sans (body)', value: '"Public Sans", sans-serif' },
    { label: 'IBM Plex Mono', value: '"IBM Plex Mono", monospace' },
    { label: 'Lora', value: '"Lora", serif' },
    { label: 'Playfair Display', value: '"Playfair Display", serif' },
    { label: 'Inter', value: '"Inter", sans-serif' },
    { label: 'Work Sans', value: '"Work Sans", sans-serif' },
];

const FONT_FORMATS = CRESCOPUS_FONTS.map(f => `${f.label}=${f.value}`).join(';');

/**
 * Mount the pitch editor onto a <textarea> element.
 * @param {HTMLTextAreaElement} textareaEl - element TinyMCE will replace
 * @param {string} initialHtml - existing pitch_html (or '' for new listing)
 * @param {(html: string) => void} onChange - called on content change
 * @param {(file: File|Blob) => Promise<string|null>} uploadImage - uploads a
 *   file and resolves to its public URL (or null on failure)
 * @returns {Promise} resolves once TinyMCE has initialized
 */
export function mountPitchEditor(textareaEl, initialHtml, onChange, uploadImage) {
    if (!textareaEl.id) {
        textareaEl.id = 'pitch-editor-' + Math.random().toString(36).slice(2);
    }
    textareaEl.value = initialHtml || '';

    return tinymce.init({
        target: textareaEl,
        license_key: 'gpl',
        height: 420,
        menubar: false,
        branding: false,
        plugins: 'link image lists',
        link_assume_external_targets: true,
        toolbar: 'undo redo | bold italic | fontfamily | h2 h3 | bullist | link image | removeformat',
        font_family_formats: FONT_FORMATS,
        images_upload_handler: (blobInfo) =>
            new Promise((resolve, reject) => {
                uploadImage(blobInfo.blob())
                    .then((url) => (url ? resolve(url) : reject('Upload failed')))
                    .catch(() => reject('Upload failed'));
            }),
        setup: (editor) => {
            editor.on('change keyup undo redo', () => onChange(editor.getContent()));
        },
    });
}
