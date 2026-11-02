(function () {
  'use strict';

  const F = window.Copperleaf;
  const { $, $$, esc } = F;

  F.pages.staff = async function () {
    let data;
    let rejecting = null;

    function draw() {
      $('#sf-rows').innerHTML = data.disputes.map((d) => `<tr><td>${F.date(d.opened)}</td><td>${esc(d.description)}<br><span class="muted small">${F.date(d.date)} · ${F.eur(Math.abs(d.amount))}</span></td>
          <td>${esc(d.reason)}</td><td>${F.status(d.status)}</td>
          <td>${d.status === 'open' ? `<div class="actions"><button type="button" class="btn btn-small" data-refund="${d.id}">Refund</button><button type="button" class="btn btn-small btn-ghost" data-reject="${d.id}">Reject</button></div>` : ''}</td></tr>`).join('');
      const c = data.customer;
      $('#od-who').textContent = `${c.name} · ${c.account} ${c.number} · balance ${F.eur(c.balance)}`;
      $('#od-amount').value = c.overdraft;
    }

    async function decide(id, body) {
      const r = await F.api(`/api/staff/disputes/${id}`, body);
      if (!r.ok) return F.say($('#sf-msg'), r.data.error || 'Could not save the decision.', 'error');
      data = r.data;
      draw();
      F.say($('#sf-msg'), body.action === 'refund' ? 'Refunded.' : 'Rejected.', 'success');
    }

    $('#sf-rows').addEventListener('click', (e) => {
      const refund = e.target.closest('[data-refund]');
      if (refund) return decide(Number(refund.dataset.refund), { action: 'refund' });
      const reject = e.target.closest('[data-reject]');
      if (!reject) return;
      rejecting = Number(reject.dataset.reject);
      $('#sf-reply').value = '';
      $('#sf-internal').value = '';
      $('#sf-dialog').returnValue = '';
      $('#sf-dialog').showModal();
    });
    $$('#sf-dialog button').forEach((b) => b.addEventListener('click', () => $('#sf-dialog').close(b.dataset.value)));
    $('#sf-dialog').addEventListener('close', () => {
      if ($('#sf-dialog').returnValue !== 'reject' || !rejecting) return;
      decide(rejecting, { action: 'reject', reply: $('#sf-reply').value.trim(), internal: $('#sf-internal').value.trim() });
    });
    $('#od-form').addEventListener('submit', async () => {
      const amount = Number($('#od-amount').value.replace(/,/g, ''));
      if (Number.isNaN(amount) || amount < 0) return F.say($('#od-msg'), 'Enter an overdraft limit.', 'error');
      const r = await F.api('/api/staff/overdraft', { amount });
      if (!r.ok) return F.say($('#od-msg'), r.data.error || 'Could not save the limit.', 'error');
      data = r.data;
      draw();
      F.say($('#od-msg'), `Overdraft set to ${F.eur(data.customer.overdraft)}.`, 'success');
    });

    const r = await F.api('/api/staff');
    if (!r.ok) return F.toast(r.data.error || 'Could not load the staff desk.', 'error');
    data = r.data;
    draw();
  };
})();
