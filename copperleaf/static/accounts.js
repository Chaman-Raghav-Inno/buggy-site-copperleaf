(function () {
  'use strict';

  const F = window.Copperleaf;
  const { $, esc } = F;

  F.pages.accounts = async function () {
    const r = await F.api('/api/overview');
    if (!r.ok) return F.toast(r.data.error || 'Could not load your accounts.', 'error');
    const o = r.data;
    $('#ov-hello').textContent = `Hello, ${o.name}`;
    $('#ov-accounts').innerHTML = o.accounts.map((a) => {
      const main = a.type === 'card' ? `${F.eur(-a.balance)} owed` : F.eur(a.balance);
      const sub = a.type === 'card' ? `${F.eur(a.available)} available to spend` : `${F.eur(a.available)} available`;
      return `<a class="tile account-tile ${a.type}" href="/account?id=${a.id}"><p class="tile-label">${esc(a.name)} · ${esc(a.number)}</p>
        <p class="tile-value">${main}</p><p class="tile-note">${sub}${a.pending ? ` · ${F.eur(-a.pending)} pending` : ''}</p></a>`;
    }).join('');
    const total = o.accounts.reduce((s, a) => s + Math.abs(a.balance), 0);
    $('#ov-total').textContent = F.eur(total);
    $('#ov-recent').innerHTML = o.recent.map((t) => `<li><span><strong>${esc(t.description)}</strong><span class="muted small">${F.day(t.date)} · ${esc(t.account_name)}${t.status === 'pending' ? ' · pending' : ''}</span></span>
        <span class="amt${t.amount > 0 ? ' in' : ''}">${F.signed(t.amount)}</span></li>`).join('');
  };
})();
