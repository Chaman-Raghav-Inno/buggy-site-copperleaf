(function () {
  'use strict';

  const F = window.Copperleaf;
  const { $, esc } = F;

  F.pages.transfer = async function () {
    let accounts = [];
    let payees = [];
    let pending = null;

    const label = (id) => $(`#tf-to option[value="${id}"]`).textContent;

    function fill() {
      const own = accounts.filter((a) => a.type !== 'card');
      $('#tf-from').innerHTML = own.map((a) => `<option value="${a.id}">${esc(a.name)} (${F.eur(a.available)} available)</option>`).join('');
      $('#tf-to').innerHTML = `<optgroup label="Your accounts">${accounts.map((a) => `<option value="account:${a.id}">${esc(a.name)}</option>`).join('')}</optgroup>`
        + `<optgroup label="Payees">${payees.map((p) => `<option value="payee:${p.id}">${esc(p.name)}</option>`).join('')}</optgroup>`;
      const to = F.params.get('to');
      if (to && $(`#tf-to option[value="${to}"]`)) $('#tf-to').value = to;
      else $('#tf-to').value = 'account:2';
    }

    $('#tf-ref').addEventListener('input', (e) => { $('#tf-ref-count').textContent = `${e.target.value.length} / 35`; });
    $('#tf-form').addEventListener('submit', () => {
      const msg = $('#tf-msg');
      const raw = $('#tf-amount').value.trim();
      const amount = Number(raw);
      if (!raw || !(amount > 0)) return F.say(msg, 'Enter an amount, like 25.50.', 'error');
      const date = $('#tf-date').value || F.today;
      if (date < F.today) return F.say(msg, 'The date can\'t be in the past.', 'error');
      F.say(msg, '');
      const from = accounts.find((a) => String(a.id) === $('#tf-from').value);
      pending = { from: from.id, to: $('#tf-to').value, amount, date, repeat: $('#tf-repeat').value, reference: $('#tf-ref').value.trim() };
      const when = date === F.today && pending.repeat === 'once' ? 'Now' : `${F.day(date)}${pending.repeat === 'monthly' ? ', then every month' : ''}`;
      $('#tf-summary').innerHTML = [
        ['From', esc(from.name)], ['To', esc(label(pending.to))], ['Amount', `€${esc(raw)}`],
        ['Leaves your account', when], ['Reference', esc(pending.reference) || '—'],
      ].map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join('');
      F.say($('#tf-error'), '');
      $('#tf-review').hidden = false;
      $('#tf-done').hidden = true;
      $('#tf-confirm').focus();
    });
    $('#tf-edit').addEventListener('click', () => { $('#tf-review').hidden = true; $('#tf-amount').focus(); });
    $('#tf-confirm').addEventListener('click', async () => {
      if (!pending) return;
      $('#tf-confirm').disabled = true;
      const r = await F.api('/api/transfers', pending);
      $('#tf-confirm').disabled = false;
      if (!r.ok) return F.say($('#tf-error'), r.data.error || 'Could not make the payment.', 'error');
      const d = r.data;
      $('#tf-review').hidden = true;
      $('#tf-done').hidden = false;
      $('#tf-done').innerHTML = d.done === 'sent'
        ? `<h2>Sent</h2><p>${F.eur(-d.transaction.amount)} sent: ${esc(d.transaction.description)}.</p><p class="muted">New balance: ${F.eur(d.balance)}</p><p><a href="/account?id=${pending.from}">See the account</a></p>`
        : `<h2>Scheduled</h2><p>${F.eur(d.scheduled.amount)} to ${esc(d.scheduled.to_name)} leaves your account on ${d.scheduled.dates.map(F.day).join(', ')}${d.scheduled.repeat === 'monthly' ? ' and so on' : ''}.</p><p><a href="/scheduled">See scheduled payments</a></p>`;
      pending = null;
      $('#tf-form').reset();
      $('#tf-date').value = F.today;
      const fresh = await F.api('/api/overview');
      if (fresh.ok) { accounts = fresh.data.accounts; const keep = $('#tf-to').value; fill(); $('#tf-to').value = keep; }
    });

    const [o, p, me] = await Promise.all([F.api('/api/overview'), F.api('/api/payees'), F.api('/api/me')]);
    if (!o.ok || !p.ok) return F.toast('Could not load your accounts.', 'error');
    accounts = o.data.accounts;
    payees = p.data.payees;
    F.today = me.data.today;
    fill();
    $('#tf-date').value = F.today;
    $('#tf-date').min = F.today;
    $('#loading').hidden = true;
    $('#transfer').hidden = false;
  };
})();
