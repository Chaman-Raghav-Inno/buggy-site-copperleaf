(function () {
  'use strict';

  const F = window.Copperleaf;
  const { $ } = F;

  F.pages.card = async function () {
    let c;

    function draw() {
      $('#cd-name').textContent = c.name;
      $('#cd-number').textContent = `•••• •••• •••• ${c.last4}`;
      $('#cd-holder').textContent = c.holder;
      const d = new Date(c.expiry + '-01T00:00:00Z');
      $('#cd-expiry').textContent = `${String(d.getUTCMonth()).padStart(2, '0')}/${String(d.getUTCFullYear()).slice(2)}`;
      $('#cd-frozen').hidden = !c.frozen;
      $('#cd-visual').classList.toggle('frozen', c.frozen);
      $('#cd-status').innerHTML = c.frozen ? '<strong>Your card is frozen.</strong>' : 'Your card is active.';
      $('#cd-freeze').textContent = c.frozen ? 'Unfreeze card' : 'Freeze card';
      $('#cd-facts').innerHTML = [
        ['Owed now', F.eur(c.owed)], ['Available to spend', F.eur(c.available)], ['Credit limit', F.eur(c.credit_limit)],
        ['Last statement balance', F.eur(c.statement_balance)], ['Minimum payment', F.eur(c.minimum)], ['Payment due', F.date(c.due)],
      ].map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join('');
    }

    $('#cd-freeze').addEventListener('click', async () => {
      const r = await F.api('/api/card/freeze', { frozen: !c.frozen });
      if (!r.ok) return F.toast(r.data.error || 'Could not update your card.', 'error');
      c = r.data;
      draw();
      F.toast(c.frozen ? 'Card frozen.' : 'Card unfrozen.');
    });
    $('#cd-form').addEventListener('submit', async () => {
      const limit = Number($('#cd-limit').value.replace(/,/g, ''));
      if (!(limit > 0)) return F.say($('#cd-msg'), 'Enter a monthly limit.', 'error');
      const r = await F.api('/api/card/settings', { online: $('#cd-online').checked, limit });
      if (!r.ok) return F.say($('#cd-msg'), r.data.error || 'Could not save your settings.', 'error');
      c = r.data;
      draw();
      F.say($('#cd-msg'), 'Settings saved.', 'success');
    });

    const r = await F.api('/api/card');
    if (!r.ok) return F.toast(r.data.error || 'Could not load your card.', 'error');
    c = r.data;
    draw();
    $('#cd-online').checked = c.online;
    $('#cd-limit').value = c.limit;
    $('#loading').hidden = true;
    $('#card').hidden = false;
  };
})();
