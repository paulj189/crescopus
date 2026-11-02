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

form.addEventListener('click', (e) => {
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
