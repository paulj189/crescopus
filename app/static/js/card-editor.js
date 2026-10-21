// card-editor.js
// Edit Card page: rich-text editors, photo uploads, and a live preview of the
// browse card that updates as you type or tick tags.
import { mountPitchEditor, mountListEditor } from './pitch-editor.js';
import { uploadListingImage } from './image-uploader.js';

const form = document.getElementById('cu-card-form');
const preview = document.getElementById('cu-preview');
const supabase = window.supabaseClient;
let dirty = false;

// ---------- live preview ----------

function initials(text) {
  const parts = (text || '').split(/[\s.]+/).filter(Boolean);
  if (!parts.length) return '?';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function setPreviewAvatar(url) {
  const slot = preview.querySelector('[data-preview="avatar"]');
  slot.textContent = '';
  if (url) {
    const img = document.createElement('img');
    img.src = url;
    img.alt = '';
    slot.appendChild(img);
  } else {
    const nameEl = preview.querySelector('[data-preview="name"]');
    slot.textContent = initials(nameEl.textContent);
  }
}

function cardAvatarField() {
  const input = form.querySelector('input[type=file][data-card-avatar]');
  return input ? document.getElementById(input.dataset.imageFor) : null;
}

function updateText(src) {
  const target = preview.querySelector(`[data-preview="${src.dataset.previewSrc}"]`);
  if (!target) return;
  const value = src.value.trim();
  target.textContent = src.dataset.previewSrc === 'by' ? `Builder · ${value}` : value;
  if (src.dataset.previewSrc === 'name') {
    const field = cardAvatarField();
    if (field && !field.value) setPreviewAvatar('');
  }
}

function updateTags() {
  const box = preview.querySelector('[data-preview="tags"]');
  box.textContent = '';
  for (const kind of ['needs', 'offers']) {
    const ticked = [...form.querySelectorAll(`input[data-tag-kind="${kind}"]:checked`)];
    if (!ticked.length) continue;
    const row = document.createElement('div');
    row.className = 'cu-tag-row';
    const label = document.createElement('span');
    label.className = `cu-tag-label cu-${kind}-ink`;
    label.textContent = kind === 'needs' ? 'Needs' : 'Offers';
    const tags = document.createElement('span');
    tags.className = 'cu-tags';
    for (const input of ticked) {
      const tag = document.createElement('span');
      tag.className = `cu-tag cu-tag-${kind}`;
      tag.textContent = input.parentElement.textContent.trim();
      tags.appendChild(tag);
    }
    row.append(label, tags);
    box.appendChild(row);
  }
}

function updateCount(input) {
  const out = document.getElementById(input.dataset.count);
  if (out) out.textContent = `${input.value.length}/${input.maxLength}.`;
}

form.querySelectorAll('[data-preview-src]').forEach((el) => {
  el.addEventListener('input', () => updateText(el));
  updateText(el);
});
form.querySelectorAll('[data-count]').forEach((el) => {
  el.addEventListener('input', () => updateCount(el));
  updateCount(el);
});
form.addEventListener('change', (e) => {
  if (e.target.matches('input[data-tag-kind]')) updateTags();
});
updateTags();

// ---------- rich text ----------

form.querySelectorAll('textarea[data-rich]').forEach((ta) => {
  const hidden = document.getElementById(ta.dataset.target);
  const onChange = (html) => { hidden.value = html; dirty = true; };
  if (ta.dataset.rich === 'pitch') {
    const uploadId = ta.dataset.uploadId;
    mountPitchEditor(ta, hidden.value, onChange,
      (file) => uploadListingImage(supabase, file, uploadId, (msg) => window.alert(msg)), { height: 300 });
  } else {
    mountListEditor(ta, hidden.value, onChange);
  }
});

// ---------- photos ----------

function showPicked(field, url) {
  const box = form.querySelector(`[data-image-preview="${field}"]`);
  box.textContent = '';
  if (url) {
    const img = document.createElement('img');
    img.src = url;
    img.alt = '';
    box.appendChild(img);
  } else {
    box.textContent = box.dataset.initials;
  }
  form.querySelector(`[data-image-remove="${field}"]`).hidden = !url;
}

form.querySelectorAll('input[type=file][data-image-for]').forEach((input) => {
  const field = input.dataset.imageFor;
  const hidden = document.getElementById(field);
  const msg = form.querySelector(`[data-image-msg="${field}"]`);
  input.addEventListener('change', async () => {
    const file = input.files[0];
    if (!file) return;
    msg.textContent = 'Uploading…';
    const url = await uploadListingImage(supabase, file, input.dataset.uploadId, (m) => { msg.textContent = m; });
    if (url) {
      hidden.value = url;
      showPicked(field, url);
      if (input.hasAttribute('data-card-avatar')) setPreviewAvatar(url);
      msg.textContent = 'Uploaded. Save the card to keep it.';
      dirty = true;
    }
    input.value = '';
  });
});

form.querySelectorAll('[data-image-remove]').forEach((btn) => {
  btn.addEventListener('click', () => {
    const field = btn.dataset.imageRemove;
    document.getElementById(field).value = '';
    showPicked(field, '');
    const fileInput = form.querySelector(`input[type=file][data-image-for="${field}"]`);
    if (fileInput && fileInput.hasAttribute('data-card-avatar')) setPreviewAvatar('');
    dirty = true;
  });
});

// ---------- saving ----------

form.addEventListener('input', () => { dirty = true; });
form.addEventListener('submit', () => {
  // Make sure the latest editor content is in the hidden fields.
  form.querySelectorAll('textarea[data-rich]').forEach((ta) => {
    const editor = window.tinymce && window.tinymce.get(ta.id);
    if (editor) document.getElementById(ta.dataset.target).value = editor.getContent();
  });
  dirty = false;
});
window.addEventListener('beforeunload', (e) => {
  if (dirty) { e.preventDefault(); e.returnValue = ''; }
});
