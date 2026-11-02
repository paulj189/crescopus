// image-uploader.js
// Upload a single image (thumbnail, or an inline pitch image) to Supabase
// Storage, with client-side compression toward a 2MB cap and clear
// messaging if a file still can't be brought under it.

const MAX_BYTES = 2 * 1024 * 1024; // 2MB
const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp'];

async function compressImage(file) {
    const bitmap = await createImageBitmap(file);
    let { width, height } = bitmap;
    let quality = 0.85;

    const MAX_DIM = 1920;
    if (width > MAX_DIM || height > MAX_DIM) {
        const scale = MAX_DIM / Math.max(width, height);
        width = Math.round(width * scale);
        height = Math.round(height * scale);
    }

    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    canvas.getContext('2d').drawImage(bitmap, 0, 0, width, height);

    let blob = await canvasToBlob(canvas, quality);
    let attempts = 0;
    while (blob.size > MAX_BYTES && attempts < 5) {
        quality -= 0.15;
        blob = await canvasToBlob(canvas, Math.max(quality, 0.3));
        attempts++;
    }
    return blob;
}

function canvasToBlob(canvas, quality) {
    return new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', quality));
}

/**
 * Validate, compress, and upload a single image file to Supabase Storage.
 * @param {SupabaseClient} supabase
 * @param {File} file
 * @param {string} listingId
 * @param {(msg: string) => void} onError - user-facing error message
 * @returns {Promise<string|null>} public URL, or null on failure
 */
export async function uploadListingImage(supabase, file, listingId, onError) {
    if (!ALLOWED_TYPES.includes(file.type)) {
        onError('Please upload a JPG, PNG, or WebP image.');
        return null;
    }

    let uploadBlob = file;
    if (file.size > MAX_BYTES) {
        uploadBlob = await compressImage(file);
        if (uploadBlob.size > MAX_BYTES) {
            onError('Image too large even after compression (max 2MB). Try a smaller or simpler image.');
            return null;
        }
    }

    // Sent to Crescopus, which checks you own the card and stores it. (The browser
    // isn't signed in to Supabase itself, so it can't write to Storage directly.)
    const body = new FormData();
    body.append('file', uploadBlob, file.name || 'image');
    body.append('upload_id', listingId);
    try {
        const res = await fetch('/browse/upload-image', {
            method: 'POST', body, headers: { 'X-Requested-With': 'fetch' }, credentials: 'same-origin',
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || !data.url) {
            onError(data.error || 'Upload failed. Please try again.');
            return null;
        }
        return data.url;
    } catch (e) {
        onError('Upload failed. Check your connection and try again.');
        return null;
    }
}

export const IMAGE_UPLOAD_LIMITS = { MAX_BYTES, ALLOWED_TYPES };
