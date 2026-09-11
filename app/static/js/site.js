document.addEventListener('DOMContentLoaded', () => {
  const themeToggle = document.querySelector('.theme-toggle');
  const root = document.documentElement;

  const updateThemeToggle = () => {
    if (!themeToggle) return;
    const isDark = root.dataset.theme === 'dark';
    const icon = themeToggle.querySelector('i');
    const label = themeToggle.querySelector('span');
    const actionLabel = isDark ? 'Ativar tema claro' : 'Ativar tema escuro';

    themeToggle.setAttribute('aria-label', actionLabel);
    themeToggle.setAttribute('title', actionLabel);
    if (icon) icon.className = isDark ? 'bi bi-sun-fill' : 'bi bi-moon-stars-fill';
    if (label) label.textContent = isDark ? 'Tema claro' : 'Tema escuro';
  };

  updateThemeToggle();
  themeToggle?.addEventListener('click', () => {
    const nextTheme = root.dataset.theme === 'dark' ? 'light' : 'dark';
    root.dataset.theme = nextTheme;
    try { localStorage.setItem('eu-te-apresento-foz-theme', nextTheme); } catch (error) {}
    updateThemeToggle();
  });

  const menuToggle = document.querySelector('[data-menu-toggle]');
  const menuPanel = document.querySelector('[data-menu-panel]');
  menuToggle?.addEventListener('click', () => {
    menuPanel?.classList.toggle('is-open');
  });

  document.querySelectorAll('[data-before-after]').forEach((card) => {
    const wrap = card.querySelector('.mv-before-card__images');
    const before = card.querySelector('.mv-before-img--before');
    const after = card.querySelector('.mv-before-img--after');
    const divider = card.querySelector('.mv-before-divider');
    if (!wrap || !before || !after) return;

    const setSplit = (percent) => {
      const value = Math.max(12, Math.min(88, percent));
      before.style.clipPath = `inset(0 ${100 - value}% 0 0)`;
      after.style.clipPath = `inset(0 0 0 ${value}%)`;
      if (divider) divider.style.left = `${value}%`;
    };

    wrap.addEventListener('pointermove', (event) => {
      const rect = wrap.getBoundingClientRect();
      setSplit(((event.clientX - rect.left) / rect.width) * 100);
    });
    wrap.addEventListener('pointerleave', () => setSplit(50));
  });
});

(function () {
  const cfg = window.__SITE_ANALYTICS__;
  if (!cfg || !cfg.endpoint || !window.fetch || !window.localStorage || !window.sessionStorage) return;

  const uid = () => `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`;
  const visitorKey = 'mv_visitor_id';
  const sessionKey = 'mv_session_id';
  const startedAtKey = 'mv_session_started_at';

  let visitorId = localStorage.getItem(visitorKey);
  let isNewUser = false;
  if (!visitorId) {
    visitorId = uid();
    localStorage.setItem(visitorKey, visitorId);
    isNewUser = true;
  }

  let sessionId = sessionStorage.getItem(sessionKey);
  if (!sessionId) {
    sessionId = uid();
    sessionStorage.setItem(sessionKey, sessionId);
    sessionStorage.setItem(startedAtKey, String(Date.now()));
  }

  const send = (eventName, durationSeconds = 0) => {
    const payload = {
      event: eventName,
      session_id: sessionId,
      visitor_id: visitorId,
      page_path: cfg.path || window.location.pathname,
      referrer: document.referrer || '',
      duration_seconds: durationSeconds,
      is_new_user: isNewUser,
    };
    const body = JSON.stringify(payload);
    if (navigator.sendBeacon && eventName === 'heartbeat') {
      navigator.sendBeacon(cfg.endpoint, new Blob([body], { type: 'application/json' }));
      return;
    }
    fetch(cfg.endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
      keepalive: true,
      credentials: 'same-origin',
    }).catch(() => {});
  };

  send('pageview', 0);

  const flushDuration = () => {
    const startedAt = parseInt(sessionStorage.getItem(startedAtKey) || String(Date.now()), 10);
    const seconds = Math.max(0, Math.round((Date.now() - startedAt) / 1000));
    send('heartbeat', seconds);
  };

  window.addEventListener('beforeunload', flushDuration);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') flushDuration();
  });
})();
