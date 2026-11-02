(function () {
  'use strict';

  const F = window.Copperleaf;
  const { $ } = F;

  F.pages.settings = async function () {
    function draw(s) {
      $('#se-alerts').checked = s.alerts;
      $('#se-threshold').value = s.alert_threshold;
      $('#se-email').value = s.email;
    }

    $('#se-form').addEventListener('submit', async () => {
      const msg = $('#se-msg');
      const threshold = parseInt($('#se-threshold').value, 10);
      if (Number.isNaN(threshold) || threshold < 0) return F.say(msg, 'Enter an alert amount.', 'error');
      const r = await F.api('/api/settings', { alert_threshold: threshold, email: $('#se-email').value.trim(), alerts: $('#se-alerts').checked });
      if (!r.ok) return F.say(msg, r.data.error || 'Could not save your settings.', 'error');
      draw(r.data);
      F.say(msg, `Saved. We'll email ${r.data.email} when your balance drops below ${F.eur(r.data.alert_threshold)}.`, 'success');
    });
    $('#pw-form').addEventListener('submit', async () => {
      const msg = $('#pw-msg');
      const r = await F.api('/api/password', { current: $('#pw-current').value, new: $('#pw-new').value });
      if (!r.ok) return F.say(msg, r.data.error || 'Could not change your password.', 'error');
      $('#pw-form').reset();
      F.say(msg, 'Password changed.', 'success');
    });

    const r = await F.api('/api/settings');
    if (!r.ok) return F.toast(r.data.error || 'Could not load your settings.', 'error');
    draw(r.data);
  };
})();
