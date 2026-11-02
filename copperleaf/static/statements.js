(function () {
  'use strict';

  const F = window.Copperleaf;
  const { $, esc } = F;

  F.pages.statements = async function () {
    async function load() {
      const q = new URLSearchParams({ account: $('#st-account').value, month: $('#st-month').value });
      const r = await F.api('/api/statements?' + q.toString());
      if (!r.ok) return F.toast(r.data.error || 'Could not load the statement.', 'error');
      const s = r.data;
      const keep = $('#st-month').value;
      $('#st-month').innerHTML = s.months.map((m) => `<option value="${m}">${F.month(m + '-01')}</option>`).join('');
      $('#st-month').value = keep || s.month;
      $('#st-title').textContent = `${s.account.name} · ${F.month(s.month + '-01')}`;
      $('#st-facts').innerHTML = [['Opening balance', s.opening], ['Money in', s.in], ['Money out', -s.out], ['Closing balance', s.closing]]
        .map(([k, v], i) => `<div${i === 3 ? ' class="total"' : ''}><dt>${k}</dt><dd>${F.eur(v)}</dd></div>`).join('');
      $('#st-rows').innerHTML = s.transactions.map((t) => `<tr><td>${F.date(t.date)}</td><td>${esc(t.description)}</td>
          <td class="num amt${t.amount > 0 ? ' in' : ''}">${F.signed(t.amount)}</td></tr>`).join('') || '<tr><td colspan="3" class="muted">No transactions this month.</td></tr>';
      $('#st-csv').href = `/api/statements.csv?${new URLSearchParams({ account: s.account.id, month: s.month }).toString()}`;
      $('#st-csv').setAttribute('download', `statement-${s.account.name.toLowerCase().replace(/\s+/g, '-')}-${s.month}.csv`);
      $('#loading').hidden = true;
      $('#statement').hidden = false;
    }
    $('#st-account').addEventListener('change', load);
    $('#st-month').addEventListener('change', load);
    const account = F.params.get('account');
    if (account) $('#st-account').value = account;
    await load();
  };
})();
