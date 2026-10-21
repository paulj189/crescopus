// browse.js
// Opens browse cards as a popup (full-screen sheet on phones), keeps the
// address bar and Back button in step, and applies filters as soon as a
// box is ticked. Without JavaScript every card is still a normal link.
(function () {
  const dialog = document.getElementById('cu-popup');
  const body = dialog && dialog.querySelector('.cu-dialog-body');
  const form = document.getElementById('cu-filter-form');
  const filters = document.querySelector('.cu-filters');

  // Filters start collapsed on small screens.
  if (filters && window.matchMedia('(max-width: 859px)').matches) {
    filters.removeAttribute('open');
  }

  // Apply filters straight away when a box is ticked.
  if (form) {
    form.addEventListener('change', function (e) {
      if (e.target.matches('input[type=checkbox]')) form.submit();
    });
  }

  if (!dialog || typeof dialog.showModal !== 'function') return;

  async function openPopup(url, push) {
    body.innerHTML = '<p class="cu-loading">Loading…</p>';
    if (!dialog.open) dialog.showModal();
    try {
      const sep = url.includes('?') ? '&' : '?';
      const res = await fetch(url + sep + 'partial=1', { headers: { 'X-Requested-With': 'fetch' } });
      if (!res.ok) throw new Error(res.status);
      body.innerHTML = await res.text();
      const heading = body.querySelector('h2');
      if (heading) { heading.setAttribute('tabindex', '-1'); heading.focus(); }
    } catch (err) {
      body.innerHTML = '<p class="cu-loading">Sorry, that profile couldn\'t be loaded. <a href="' + url + '">Open it as a page</a>.</p>';
    }
    if (push) history.pushState({ cuPopup: url }, '', url);
  }

  document.addEventListener('click', function (e) {
    const card = e.target.closest('a[data-popup]');
    if (!card || e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
    e.preventDefault();
    openPopup(card.getAttribute('href'), true);
  });

  // Close button, or a click on the dimmed area outside the popup.
  dialog.addEventListener('click', function (e) {
    if (e.target === dialog || e.target.closest('[data-close]')) dialog.close();
  });

  // Closing the popup returns the address bar to the browse page.
  dialog.addEventListener('close', function () {
    if (history.state && history.state.cuPopup) history.back();
  });

  // Back button closes the popup; Forward reopens it.
  window.addEventListener('popstate', function (e) {
    if (e.state && e.state.cuPopup) {
      openPopup(e.state.cuPopup, false);
    } else if (dialog.open) {
      dialog.close();
    }
  });
})();
