(function () {
  'use strict';

  const F = window.Copperleaf;
  const { $, esc } = F;

  F.pages.account = async function () {
    const id = Number(F.params.get('id'));
    let page = 1;

    function query() {
      const q = new URLSearchParams({ q: $('#ac-q').value.trim(), from: $('#ac-from').value, to: $('#ac-to').value, sort: $('#ac-sort').value });
      return q;
    }

    async function load() {
      const q = query();
      q.set('page', page);
      const r = await F.api(`/api/accounts/${id}/transactions?${q.toString()}`);
      const d = r.data;
      const a = d.account;
      document.title = `${a.name} · Copperleaf Bank`;
      $('#ac-name').textContent = a.name;
      $('#ac-number').textContent = a.number;
      const facts = a.type === 'card'
        ? [['Owed', F.eur(-a.balance)], ['Available to spend', F.eur(a.available)], ['Credit limit', F.eur(a.credit_limit)]]
        : [['Balance', F.eur(a.balance)], ['Available', F.eur(a.available)], ['Arranged overdraft', F.eur(a.overdraft)]];
      $('#ac-facts').innerHTML = facts.map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join('');
      $('#ac-rows').innerHTML = d.transactions.map((t) => `<tr${t.status === 'pending' ? ' class="pending"' : ''}><td>${F.date(t.date)}</td>
          <td>${esc(t.description)}${t.status === 'pending' ? ' <span class="pill pill-pending">Pending</span>' : ''}${t.reference ? `<br><span class="muted small">Ref: ${esc(t.reference)}</span>` : ''}${t.foreign ? `<br><span class="muted small">${esc(t.foreign)} converted to euros</span>` : ''}</td>
          <td class="num amt${t.amount > 0 ? ' in' : ''}">${F.signed(t.amount)}</td></tr>`).join('')
        || '<tr><td colspan="3" class="muted">No transactions match.</td></tr>';
      const posted = d.transactions.filter((t) => t.status === 'posted');
      const moneyIn = posted.filter((t) => t.amount > 0).reduce((s, t) => s + t.amount, 0);
      const moneyOut = posted.filter((t) => t.amount < 0).reduce((s, t) => s - t.amount, 0);
      $('#ac-count').textContent = F.plural(d.count, 'transaction');
      $('#ac-in').textContent = `Money in ${F.eur(moneyIn)}`;
      $('#ac-out').textContent = `Money out ${F.eur(moneyOut)}`;
      $('#ac-csv').href = `/api/accounts/${id}.csv?${query().toString()}`;
      $('#ac-csv').setAttribute('download', `${a.name.toLowerCase().replace(/\s+/g, '-')}.csv`);
      $('#ac-page').textContent = `Page ${d.page} of ${d.pages}`;
      $('#ac-prev').disabled = d.page <= 1;
      $('#ac-next').disabled = d.page >= d.pages;
    }

    let timer;
    $('#ac-q').addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(() => { page = 1; load(); }, 250); });
    ['#ac-from', '#ac-to', '#ac-sort'].forEach((s) => $(s).addEventListener('change', () => { page = 1; load(); }));
    $('#ac-prev').addEventListener('click', () => { page -= 1; load(); });
    $('#ac-next').addEventListener('click', () => { page += 1; load(); });
    await load();
    $('#loading').hidden = true;
    $('#account').hidden = false;
  };
})();
