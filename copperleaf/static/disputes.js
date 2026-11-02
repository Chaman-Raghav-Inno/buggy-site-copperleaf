(function () {
  'use strict';

  const F = window.Copperleaf;
  const { $, esc } = F;

  F.pages.disputes = async function () {
    let data;

    function draw() {
      $('#dp-txn').innerHTML = '<option value="">Choose a payment</option>' + data.transactions.map((t) => `<option value="${t.id}">${F.date(t.date)} · ${esc(t.description)} · ${F.signed(t.amount)}</option>`).join('');
      $('#dp-list').innerHTML = data.disputes.map((d) => `<li><div class="section-head"><strong>${esc(d.description)} · ${F.eur(Math.abs(d.amount))}</strong>${F.status(d.status)}</div>
          <p class="muted small">Payment on ${F.date(d.date)} · opened ${F.date(d.opened)}</p><p>${esc(d.reason)}</p>
          ${d.reply ? `<p class="reply"><strong>Copperleaf:</strong> ${esc(d.reply)}${d.internal ? `<br><span class="muted small">${esc(d.internal)}</span>` : ''}</p>` : ''}</li>`).join('')
        || '<li class="muted">No disputes.</li>';
    }

    $('#dp-form').addEventListener('submit', async () => {
      const msg = $('#dp-msg');
      const transaction = Number($('#dp-txn').value);
      const reason = $('#dp-reason').value.trim();
      if (!transaction) return F.say(msg, 'Choose the card payment.', 'error');
      if (!reason) return F.say(msg, 'Tell us what went wrong.', 'error');
      const r = await F.api('/api/disputes', { transaction, reason });
      if (!r.ok) return F.say(msg, r.data.error || 'Could not open the dispute.', 'error');
      data = r.data;
      draw();
      $('#dp-form').reset();
      F.say(msg, 'Dispute opened. We\'ll reply within 10 working days.', 'success');
    });

    const r = await F.api('/api/disputes');
    if (!r.ok) return F.toast(r.data.error || 'Could not load your disputes.', 'error');
    data = r.data;
    draw();
  };
})();
