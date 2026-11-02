(function () {
  'use strict';

  const F = window.Copperleaf;
  const { $, $$, esc } = F;
  const IBAN = /^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$/;

  F.pages.payees = async function () {
    let payees = [];
    let deleting = null;

    function draw() {
      $('#py-list').innerHTML = payees.map((p) => `<li><div><strong>${esc(p.name)}</strong>${p.new ? ' <span class="pill pill-pending">New</span>' : ''}
          <span class="muted small mono">${esc(p.iban)}</span>${p.reference ? `<span class="muted small">Ref: ${esc(p.reference)}</span>` : ''}</div>
          <div class="actions"><a class="btn btn-small" href="/transfer?to=payee:${p.id}">Pay</a><button type="button" class="btn btn-small btn-ghost" data-delete="${p.id}">Delete</button></div></li>`).join('')
        || '<li class="muted">No payees yet.</li>';
    }

    $('#py-form').addEventListener('submit', async () => {
      const msg = $('#py-msg');
      const name = $('#py-name').value.trim();
      const iban = $('#py-iban').value.replace(/\s/g, '').toUpperCase();
      if (!name) return F.say(msg, 'Enter the payee\'s name.', 'error');
      if (!IBAN.test(iban)) return F.say(msg, 'That IBAN isn\'t valid. Check it and try again.', 'error');
      const r = await F.api('/api/payees', { name, iban, reference: $('#py-ref').value.trim() });
      if (!r.ok) return F.say(msg, r.data.error || 'Could not add the payee.', 'error');
      payees = r.data.payees;
      draw();
      $('#py-form').reset();
      F.say(msg, `${name} added. New payees can be sent up to €1,000 in their first 24 hours.`, 'success');
    });
    $('#py-list').addEventListener('click', (e) => {
      const b = e.target.closest('[data-delete]');
      if (!b) return;
      deleting = payees.find((p) => String(p.id) === b.dataset.delete);
      $('#py-dialog-text').textContent = `${deleting.name} (${deleting.iban}) will be removed, with any payments scheduled to them.`;
      $('#py-dialog').returnValue = '';
      $('#py-dialog').showModal();
    });
    $$('#py-dialog button').forEach((b) => b.addEventListener('click', () => $('#py-dialog').close(b.dataset.value)));
    $('#py-dialog').addEventListener('close', async () => {
      if ($('#py-dialog').returnValue !== 'delete' || !deleting) return;
      const r = await F.api(`/api/payees/${deleting.id}/delete`, {});
      if (!r.ok) return F.toast(r.data.error || 'Could not delete the payee.', 'error');
      payees = r.data.payees;
      draw();
      F.toast(`${deleting.name} deleted.`);
    });

    const r = await F.api('/api/payees');
    if (!r.ok) return F.toast(r.data.error || 'Could not load your payees.', 'error');
    payees = r.data.payees;
    draw();
  };
})();
