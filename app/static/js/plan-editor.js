// plan-editor.js
// Edit CrescoPlan page: Needs/Offers editors, add/remove action and measure rows,
// and a warning before leaving with unsaved changes.
import { mountListEditor } from './pitch-editor.js';

const form = document.getElementById('cu-plan-form');
let dirty = false;

form.querySelectorAll('textarea[data-rich="list"]').forEach((ta) => {
  const hidden = document.getElementById(ta.dataset.target);
  mountListEditor(ta, hidden.value, (html) => { hidden.value = html; dirty = true; });
});

// Tags from the cards: tapping one adds it as a bullet in that editor.
function addBullet(target, text) {
  const ta = form.querySelector(`textarea[data-target="${target}"]`);
  const editor = ta && window.tinymce && window.tinymce.get(ta.id);
  if (!editor) return;
  const li = document.createElement('li');
  li.textContent = text;
  const doc = document.createElement('div');
  doc.innerHTML = editor.getContent();
  let list = doc.lastElementChild;
  if (!list || list.tagName !== 'UL') {
    list = document.createElement('ul');
    // Drop a lone empty paragraph so the list doesn't start with a blank line.
    if (doc.textContent.trim() === '') doc.innerHTML = '';
    doc.appendChild(list);
  }
  list.appendChild(li);
  editor.setContent(doc.innerHTML);
  document.getElementById(target).value = editor.getContent();
  editor.focus();
  editor.selection.select(editor.getBody(), true);
  editor.selection.collapse(false);
  dirty = true;
}

form.addEventListener('click', (e) => {
  const tag = e.target.closest('[data-add-tag]');
  if (tag) {
    addBullet(tag.dataset.addTag, tag.dataset.text);
    tag.classList.add('cx-tag-added');
    return;
  }
  const add = e.target.closest('[data-add]');
  if (add) {
    const kind = add.dataset.add;
    const rows = form.querySelector(`[data-rows="${kind}"]`);
    const row = document.getElementById(`tpl-${kind}`).content.firstElementChild.cloneNode(true);
    rows.appendChild(row);
    row.querySelector('input').focus();
    dirty = true;
    return;
  }
  const remove = e.target.closest('[data-remove]');
  if (remove) {
    const row = remove.closest('[data-row]');
    const rows = row.parentElement;
    if (rows.querySelectorAll('[data-row]').length > 1) {
      row.remove();
    } else {
      // Keep one row on screen; just empty it.
      row.querySelectorAll('input').forEach((i) => { i.value = ''; });
    }
    dirty = true;
  }
});

form.addEventListener('input', () => { dirty = true; });
form.addEventListener('submit', () => {
  form.querySelectorAll('textarea[data-rich]').forEach((ta) => {
    const editor = window.tinymce && window.tinymce.get(ta.id);
    if (editor) document.getElementById(ta.dataset.target).value = editor.getContent();
  });
  dirty = false;
});
window.addEventListener('beforeunload', (e) => {
  if (dirty) { e.preventDefault(); e.returnValue = ''; }
});
