// browse.js
// Opens browse cards as a popup (full-screen sheet on phones), keeps the
// address bar and Back button in step, and applies filters as soon as a
// box is ticked. Without JavaScript every card is still a normal link.
//
// Speed: loading starts the moment a finger touches a card (or the mouse
// hovers), the popup opens straight away showing the card's name while the
// rest arrives, and profiles already opened are kept for instant reopening.
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

  const cache = new Map();   // url -> Promise<string> (popup HTML)
  let current = null;        // url of the popup being shown

  function fetchOnce(url) {
    const sep = url.includes('?') ? '&' : '?';
    const ctrl = new AbortController();
    const timer = setTimeout(function () { ctrl.abort(); }, 15000);
    return fetch(url + sep + 'partial=1', {
      headers: { 'X-Requested-With': 'fetch' },
      credentials: 'same-origin',
      signal: ctrl.signal,
    }).then(function (res) {
      clearTimeout(timer);
      if (!res.ok) throw new Error('HTTP ' + res.status);
      return res.text();
    }, function (err) { clearTimeout(timer); throw err; });
  }

  // Load a popup, retrying once after a short pause if the first try fails.
  function load(url) {
    if (!cache.has(url)) {
      const p = fetchOnce(url).catch(function () {
        return new Promise(function (r) { setTimeout(r, 600); }).then(function () { return fetchOnce(url); });
      });
      p.catch(function () { cache.delete(url); });  // don't keep failures
      cache.set(url, p);
    }
    return cache.get(url);
  }

  // Top bar with a close button, for the loading and error states.
  function topBar() {
    const top = document.createElement('div');
    top.className = 'cu-profile-top';
    const close = document.createElement('button');
    close.type = 'button';
    close.className = 'cu-icon-btn cu-close';
    close.setAttribute('data-close', '');
    close.setAttribute('aria-label', 'Close');
    close.innerHTML = '<svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>';
    top.append(document.createElement('span'), close);
    return top;
  }

  // Shown instantly while the full profile loads: the card's own picture and name.
  function placeholder(card) {
    const wrap = document.createElement('div');
    wrap.className = 'cu-profile cu-profile-loading';
    const top = topBar();
    const head = card ? card.querySelector('.cu-card-head') : null;
    const person = head ? head.cloneNode(true) : document.createElement('div');
    person.classList.add('cu-loading-head');
    const note = document.createElement('p');
    note.className = 'cu-loading';
    note.textContent = 'Loading…';
    wrap.append(top, person, note);
    return wrap;
  }

  function showError(url) {
    body.innerHTML = '';
    const box = document.createElement('div');
    box.className = 'cu-loading';
    box.innerHTML = '<p>That profile didn\'t load. This is usually a brief connection hiccup.</p>';
    const again = document.createElement('button');
    again.type = 'button';
    again.className = 'cu-btn cu-btn-primary';
    again.textContent = 'Try again';
    again.addEventListener('click', function () { openPopup(url, false, null); });
    const link = document.createElement('a');
    link.className = 'cu-btn cu-btn-secondary';
    link.href = url;
    link.textContent = 'Open as a page';
    const actions = document.createElement('div');
    actions.className = 'cu-loading-actions';
    actions.append(again, link);
    box.appendChild(actions);
    body.append(topBar(), box);
  }

  function openPopup(url, push, card) {
    current = url;
    body.innerHTML = '';
    body.appendChild(placeholder(card));
    if (!dialog.open) dialog.showModal();
    if (push) history.pushState({ cuPopup: url }, '', url);
    load(url).then(function (html) {
      if (current !== url) return;           // user moved on
      body.innerHTML = html;
      const heading = body.querySelector('h2');
      if (heading) { heading.setAttribute('tabindex', '-1'); heading.focus({ preventScroll: true }); }
    }).catch(function () {
      if (current === url) showError(url);
    });
  }

  // Start loading early: on touch/press, and on mouse hover.
  function warm(e) {
    const card = e.target.closest && e.target.closest('a[data-popup]');
    if (card) load(card.getAttribute('href'));
  }
  document.addEventListener('pointerdown', warm, { passive: true });
  document.addEventListener('mouseover', warm, { passive: true });

  document.addEventListener('click', function (e) {
    const card = e.target.closest('a[data-popup]');
    if (!card || e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
    e.preventDefault();
    openPopup(card.getAttribute('href'), true, card);
  });

  // Close button, or a click on the dimmed area outside the popup.
  dialog.addEventListener('click', function (e) {
    if (e.target === dialog || e.target.closest('[data-close]')) dialog.close();
  });

  // Closing the popup returns the address bar to the browse page.
  dialog.addEventListener('close', function () {
    current = null;
    if (history.state && history.state.cuPopup) history.back();
  });

  // Back button closes the popup; Forward reopens it.
  window.addEventListener('popstate', function (e) {
    if (e.state && e.state.cuPopup) {
      openPopup(e.state.cuPopup, false, null);
    } else if (dialog.open) {
      dialog.close();
    }
  });
})();
