(function () {
  'use strict';

  const F = (window.Copperleaf = window.Copperleaf || {});
  F.pages = F.pages || {};
  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));
  const ENTITIES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  F.$ = $;
  F.$$ = $$;
  F.esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ENTITIES[c]);
  F.params = new URLSearchParams(location.search);
  F.role = document.body.dataset.role || '';
  F.EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

  document.addEventListener('submit', (e) => {
    if (!e.target.matches('[data-native]')) e.preventDefault();
  }, true);

  F.api = async function (path, body) {
    const opts = body === undefined
      ? { credentials: 'same-origin' }
      : { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };
    let res;
    try {
      res = await fetch(path, opts);
    } catch (e) {
      return { ok: false, status: 0, data: { error: 'You appear to be offline. Try again.' } };
    }
    if (res.status === 401 && !path.startsWith('/api/login')) {
      location.href = '/login?next=' + encodeURIComponent(location.pathname + location.search);
    }
    let data = {};
    try {
      data = await res.json();
    } catch (e) {
      data = {};
    }
    return { ok: res.ok, status: res.status, data };
  };

  let toastTimer;
  F.toast = function (text, kind) {
    const el = $('#toast');
    el.textContent = text;
    el.className = 'toast' + (kind ? ' toast-' + kind : '');
    el.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { el.hidden = true; }, 3500);
  };
  F.say = function (el, text, kind) {
    el.textContent = text || '';
    el.classList.toggle('error', kind === 'error');
    el.classList.toggle('success', kind === 'success');
  };
  F.plural = (n, word, many) => `${n} ${n === 1 ? word : many || word + 's'}`;
  const DAY_FMT = { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC' };
  F.day = (iso) => new Date(iso + 'T00:00:00Z').toLocaleDateString('en-GB', DAY_FMT);
  F.date = (iso) => new Date(iso + 'T00:00:00Z').toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
  F.month = (iso) => new Date(iso + 'T00:00:00Z').toLocaleDateString('en-GB', { month: 'long', year: 'numeric', timeZone: 'UTC' });
  F.eur = (n) => (n < 0 ? '−€' : '€') + Math.abs(Number(n)).toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  F.signed = (n) => (n > 0 ? '+' : '') + F.eur(n);
  F.addDays = (iso, n) => {
    const d = new Date(iso + 'T00:00:00Z');
    d.setUTCDate(d.getUTCDate() + n);
    return d.toISOString().slice(0, 10);
  };
  F.status = (s) => `<span class="pill pill-${F.esc(s)}">${F.esc(s[0].toUpperCase() + s.slice(1))}</span>`;

  function setupChrome() {
    const page = document.body.dataset.page;
    $$('.nav a').forEach((a) => { if (a.dataset.nav === page) a.setAttribute('aria-current', 'page'); });
    const logout = $('#logout');
    if (logout) {
      logout.addEventListener('click', async () => {
        await F.api('/api/logout', {});
        location.href = '/';
      });
    }
  }

  document.addEventListener('DOMContentLoaded', async () => {
    setupChrome();
    const run = F.pages[document.body.dataset.page];
    if (!run) return;
    document.body.classList.add('is-loading');
    try {
      await run();
    } finally {
      document.body.classList.remove('is-loading');
    }
  });
})();
