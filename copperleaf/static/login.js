(function () {
  'use strict';

  const F = window.Copperleaf;
  const { $ } = F;

  F.pages.login = function () {
    $('#login-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const email = $('#l-email').value.trim();
      const password = $('#l-password').value;
      const msg = $('#login-msg');
      if (!F.EMAIL.test(email)) return F.say(msg, 'Enter your email address.', 'error');
      if (!password) return F.say(msg, 'Enter your password.', 'error');
      const r = await F.api('/api/login', { email, password });
      if (!r.ok) return F.say(msg, r.data.error || 'Could not log you in.', 'error');
      const next = F.params.get('next') || '';
      const home = r.data.user.role === 'staff' ? '/staff' : '/accounts';
      location.href = next.startsWith('/') && !next.startsWith('//') ? next : home;
    });
  };
})();
