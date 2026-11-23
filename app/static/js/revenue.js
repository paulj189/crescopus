/* Revenue agreement: live calculator, and the step-by-step wizard when the
   page has one (#rv-wizard). Without JavaScript the wizard shows every step
   on one page and still submits. */
(function () {
  var calcEl = document.getElementById('rv-calc');
  if (!calcEl) return;
  var $ = function (id) { return document.getElementById(id); };
  var form = $('rv-wizard');
  var SYM = calcEl.dataset.symbol || '';
  var BUILDER = calcEl.dataset.builder, GROWER = calcEl.dataset.grower;
  var fixed = JSON.parse(calcEl.dataset.terms || '{}');

  function money(n) { return SYM + Math.round(n).toLocaleString('en-GB'); }
  function money2(n) { return SYM + n.toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
  function esc(s) { var d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

  // Terms come from the wizard form when there is one, otherwise from the saved agreement.
  function terms() {
    if (!form) return fixed;
    var f = form.elements, checked = function (n) { var el = form.querySelector('[name="' + n + '"]:checked'); return el ? el.value : null; };
    return {
      basis: checked('basis') || 'net', share: +f.share.value || 0,
      tiers: f.tiers.checked, tier_at: +f.tier_at.value || 0, share2: +f.share2.value || 0,
      freq: f.freq.value, due_days: +f.due_days.value || 0, min_payout: +f.min_payout.value || 0,
      refunds: checked('refunds') || 'next', term_months: +f.term_months.value, notice_days: +f.notice_days.value,
      buyout: f.buyout.checked, buy_mult: +f.buy_mult.value, rofr: f.rofr.checked
    };
  }

  function calc(revenue, t) {
    var ios = +$('rv-ios').value || 0, and = +$('rv-android').value || 0, web = +$('rv-web').value || 0;
    var tot = ios + and + web || 1;
    var fee = +$('rv-fee').value / 100, refundPct = (+$('rv-refund').value || 0) / 100;
    var costs = +$('rv-costs').value || 0;
    var storeFees = revenue * ((ios + and) / tot) * fee;
    var webFees = revenue * (web / tot) * 0.029;
    var refunds = revenue * refundPct;
    var net = Math.max(0, revenue - storeFees - webFees - refunds);
    var base = t.basis === 'gross' ? revenue - refunds : t.basis === 'net' ? net : Math.max(0, net - costs);
    var grower = (t.tiers && base > t.tier_at)
      ? t.tier_at * t.share / 100 + (base - t.tier_at) * t.share2 / 100
      : base * t.share / 100;
    grower = Math.min(grower, net);
    return { revenue: revenue, fees: storeFees + webFees, refunds: refunds, net: net, base: base,
             grower: grower, builder: net - grower, mixTotal: ios + and + web };
  }

  function yearOf(t) {
    var rev = +$('rv-rev').value, g = +$('rv-growth').value / 100, out = [];
    for (var i = 0; i < 12; i++) out.push(calc(rev * Math.pow(1 + g, i), t));
    return out;
  }

  function renderCalc() {
    var t = terms();
    var rev = +$('rv-rev').value;
    $('rv-rev-out').textContent = money(rev);
    $('rv-costs-wrap').hidden = t.basis !== 'profit';
    var c = calc(rev, t), total = rev || 1;
    var parts = [
      ['Store & payment fees', c.fees, 'rv-c-fees'],
      ['Refunds', c.refunds, 'rv-c-refunds'],
      [GROWER + "'s share", c.grower, 'rv-c-grower'],
      [BUILDER + ' keeps', c.builder, 'rv-c-builder']
    ];
    $('rv-bar').innerHTML = parts.map(function (p) {
      return '<span class="' + p[2] + '" style="width:' + (p[1] / total * 100) + '%"></span>';
    }).join('');
    var basisLabel = { gross: 'gross revenue', net: 'net revenue', profit: 'profit' }[t.basis];
    $('rv-legend').innerHTML = parts.map(function (p) {
      return '<div><span><i class="' + p[2] + '"></i>' + esc(p[0]) + '</span><span>' + money(p[1]) + '</span></div>';
    }).join('') + '<div class="rv-legend-sum"><span>Shared on (' + basisLabel + ')</span><span>' + money(c.base) + '</span></div>';
    $('rv-g').textContent = money(c.grower);
    $('rv-b').textContent = money(c.builder);

    var warn = [];
    if (c.mixTotal !== 100) warn.push('The platform mix adds up to ' + c.mixTotal + '%. It\'s scaled to 100% for this estimate.');
    if (c.grower > 0 && c.grower < t.min_payout) warn.push('Under the ' + money(t.min_payout) + ' minimum, so this month\'s share would carry over to the next statement.');
    $('rv-warn').innerHTML = warn.map(function (w) { return '<p class="rv-warn">' + esc(w) + '</p>'; }).join('');

    $('rv-growth-out').textContent = $('rv-growth').value + '%';
    var months = yearOf(t);
    var max = Math.max.apply(null, months.map(function (m) { return m.grower + m.builder; }).concat([1]));
    var W = 340, H = 120, pad = 18, bw = (W - 8) / 12;
    var svg = '<line x1="0" y1="' + (H - pad) + '" x2="' + W + '" y2="' + (H - pad) + '" class="rv-axis"/>';
    months.forEach(function (m, i) {
      var h1 = m.builder / max * (H - pad - 14), h2 = m.grower / max * (H - pad - 14), x = 4 + i * bw;
      svg += '<rect x="' + x + '" y="' + (H - pad - h1) + '" width="' + (bw - 5) + '" height="' + h1 + '" class="rv-c-builder"/>';
      svg += '<rect x="' + x + '" y="' + (H - pad - h1 - h2) + '" width="' + (bw - 5) + '" height="' + h2 + '" class="rv-c-grower"/>';
      if (i === 0 || i === 5 || i === 11) svg += '<text x="' + (x + (bw - 5) / 2) + '" y="' + (H - 4) + '" text-anchor="middle">M' + (i + 1) + '</text>';
    });
    $('rv-spark').innerHTML = svg;
    var yg = 0, yb = 0;
    months.forEach(function (m) { yg += m.grower; yb += m.builder; });
    $('rv-year').innerHTML = 'First 12 months at this growth: <b>' + esc(GROWER) + ' ' + money(yg) + '</b>, <b>' + esc(BUILDER) + ' ' + money(yb) + '</b>.';

    if (form) renderWizardBits(t, c, yg);
  }

  /* ---------- wizard ---------- */
  function renderWizardBits(t, c, yearGrower) {
    $('rv-share-out').textContent = t.share + '%';
    $('rv-mult-out').textContent = t.buy_mult + '×';
    $('rv-tier-box').hidden = !t.tiers;
    $('rv-buyout-box').hidden = !t.buyout;
    $('rv-tier-share').textContent = t.share + '%';
    $('rv-buyout-est').textContent = money(yearGrower * t.buy_mult);

    var base = { gross: 'what customers pay (less refunds)',
                 net: 'what reaches ' + BUILDER + ' after store and payment fees and refunds',
                 profit: 'what reaches ' + BUILDER + ' after fees, refunds and running costs you\'ve both confirmed' }[t.basis];
    var s = GROWER + ' receives ' + t.share + '% of ' + base +
      (t.tiers ? ', falling to ' + t.share2 + '% on anything above ' + money(t.tier_at) + ' a month' : '') + '. ' +
      'Crescopus prepares a ' + t.freq + ' statement, and ' + BUILDER + ' pays ' + GROWER + ' directly within ' +
      t.due_days + ' days of receiving the money from the stores. ' +
      'The agreement runs for ' + t.term_months + ' months and then continues until either of you gives ' + t.notice_days + ' days\' notice. ' +
      (t.buyout ? BUILDER + ' can end ' + GROWER + '\'s share at any time by paying ' + t.buy_mult + '× what ' + GROWER + ' earned in the previous 12 months. ' : '') +
      (t.rofr ? 'If ' + BUILDER + ' sells the app, ' + GROWER + ' gets the first chance to buy it. ' : '') +
      BUILDER + ' owns the app throughout.';
    $('rv-plain').textContent = s;
    $('rv-example').textContent = money(c.revenue) + ' paid by customers → ' + GROWER + ' ' + money2(c.grower) + ', ' + BUILDER + ' ' + money2(c.builder);
  }

  var step = 0, steps = form ? [].slice.call(form.querySelectorAll('.rv-step')) : [];
  var rail = $('rv-rail');
  function showStep(i) {
    step = Math.max(0, Math.min(steps.length - 1, i));
    steps.forEach(function (s, n) { s.hidden = n !== step; });
    [].slice.call(rail.querySelectorAll('button')).forEach(function (b, n) {
      b.classList.toggle('rv-done', n < step);
      if (n === step) b.setAttribute('aria-current', 'step'); else b.removeAttribute('aria-current');
    });
  }
  if (form) {
    form.classList.add('rv-js');
    rail.hidden = false;
    rail.addEventListener('click', function (e) { var b = e.target.closest('button'); if (b) showStep(+b.dataset.go); });
    form.addEventListener('click', function (e) {
      var b = e.target.closest('[data-step-go]');
      if (!b) return;
      e.preventDefault();
      showStep(step + (+b.dataset.stepGo));
      rail.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
    form.addEventListener('input', renderCalc);
    form.addEventListener('change', renderCalc);
    var firstError = form.dataset.startStep;
    showStep(firstError ? +firstError : 0);
  }

  calcEl.addEventListener('input', renderCalc);
  calcEl.addEventListener('change', renderCalc);
  renderCalc();
})();
