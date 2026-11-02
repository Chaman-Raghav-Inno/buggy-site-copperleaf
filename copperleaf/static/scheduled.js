(function () {
  'use strict';

  const F = window.Copperleaf;
  const { $, $$, esc } = F;

  F.pages.scheduled = async function () {
    let data;
    let picked = null;

    function draw() {
      $('#sc-total').textContent = F.eur(data.next30);
      const shown = [...data.items].sort((a, b) => String(a.next).localeCompare(String(b.next)));
      $('#sc-rows').innerHTML = shown.map((s, i) => `<tr><td>${esc(s.to_name)}${s.reference ? `<br><span class="muted small">Ref: ${esc(s.reference)}</span>` : ''}</td>
          <td>${esc(s.from_name)}</td><td class="num">${F.eur(s.amount)}</td><td>${s.repeat === 'monthly' ? `Monthly on day ${s.day}` : 'Once'}</td>
          <td>${s.dates.length ? s.dates.map(F.day).join('<br>') : '—'}</td><td>${F.status(s.status === 'active' ? 'active' : 'cancelled')}</td>
          <td>${s.status === 'active' ? `<button type="button" class="link" data-index="${i}" data-show="${s.id}">Cancel</button>` : ''}</td></tr>`).join('')
        || '<tr><td colspan="7" class="muted">Nothing scheduled.</td></tr>';
    }

    $('#sc-rows').addEventListener('click', (e) => {
      const b = e.target.closest('[data-index]');
      if (!b) return;
      const shown = data.items.find((s) => String(s.id) === b.dataset.show);
      picked = data.items[Number(b.dataset.index)];
      $('#sc-dialog-text').textContent = `${F.eur(shown.amount)} to ${shown.to_name} won't be paid.`;
      $('#sc-dialog').returnValue = '';
      $('#sc-dialog').showModal();
    });
    $$('#sc-dialog button').forEach((b) => b.addEventListener('click', () => $('#sc-dialog').close(b.dataset.value)));
    $('#sc-dialog').addEventListener('close', async () => {
      if ($('#sc-dialog').returnValue !== 'cancel' || !picked) return;
      const r = await F.api(`/api/scheduled/${picked.id}/cancel`, {});
      if (!r.ok) return F.toast(r.data.error || 'Could not cancel the payment.', 'error');
      data = r.data;
      draw();
      F.toast('Payment cancelled.');
    });

    const r = await F.api('/api/scheduled');
    if (!r.ok) return F.toast(r.data.error || 'Could not load your scheduled payments.', 'error');
    data = r.data;
    draw();
  };
})();
