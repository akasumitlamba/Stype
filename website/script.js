/* ═══════════════════════════════════════════════════
   STYPE  —  script.js
═══════════════════════════════════════════════════ */

(function () {
  'use strict';

  /* ── Theme Toggle ─────────────────────────────── */
  const html = document.documentElement;
  const themeBtn = document.getElementById('theme-toggle');
  const STORAGE_KEY = 'stype-theme';

  function applyTheme(theme) {
    html.setAttribute('data-theme', theme);
    localStorage.setItem(STORAGE_KEY, theme);
  }

  // Restore saved preference
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved === 'light' || saved === 'dark') {
    applyTheme(saved);
  }

  themeBtn.addEventListener('click', () => {
    const next = html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    applyTheme(next);
  });

  /* ── Custom Cursor ────────────────────────────── */
  const cur  = document.getElementById('cur');
  const ring = document.getElementById('cur-ring');
  let mx = -200, my = -200;
  let rx = -200, ry = -200;
  let rafId;

  document.addEventListener('mousemove', e => {
    mx = e.clientX;
    my = e.clientY;
    cur.style.left = mx + 'px';
    cur.style.top  = my + 'px';
  });

  function trackRing() {
    rx += (mx - rx) * 0.095;
    ry += (my - ry) * 0.095;
    ring.style.left = rx + 'px';
    ring.style.top  = ry + 'px';
    rafId = requestAnimationFrame(trackRing);
  }
  trackRing();

  // Hover expansion on interactive elements
  const interactiveEls = 'a, button, summary, .step, .feat-card, .tech-tag, kbd, .btn';
  document.querySelectorAll(interactiveEls).forEach(el => {
    el.addEventListener('mouseenter', () => ring.classList.add('hov'));
    el.addEventListener('mouseleave', () => ring.classList.remove('hov'));
  });

  /* ── Navbar Scroll ────────────────────────────── */
  const nav = document.getElementById('nav');
  const onScroll = () => nav.classList.toggle('scrolled', window.scrollY > 50);
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  /* ── Waveform Bars ────────────────────────────── */
  const waveWrap = document.getElementById('waveWrap');
  const BAR_COUNT = 44;

  for (let i = 0; i < BAR_COUNT; i++) {
    const bar = document.createElement('div');
    bar.className = 'wave-bar';
    // Organic heights — taller in the middle
    const center = BAR_COUNT / 2;
    const dist   = Math.abs(i - center) / center;          // 0 near center, 1 at edges
    const base   = 8 + (1 - dist * dist) * 36;             // bell-shaped envelope
    const jitter = (Math.random() - 0.5) * 16;             // ±8px noise
    const h = Math.max(5, Math.round(base + jitter));
    const d  = (0.35 + Math.random() * 0.55).toFixed(2);   // duration 0.35–0.90s
    const dl = (Math.random() * 0.55).toFixed(2);          // delay 0–0.55s
    bar.style.setProperty('--h',  h  + 'px');
    bar.style.setProperty('--d',  d  + 's');
    bar.style.setProperty('--dl', dl + 's');
    waveWrap.appendChild(bar);
  }

  /* ── Pill State Cycler ────────────────────────── */
  const pill   = document.getElementById('pill');
  const pDot   = document.getElementById('pDot');
  const pLabel = document.getElementById('pLabel');

  const states = [
    { label: 'Recording...',  dot: 'rec',  mod: ''     },
    { label: 'Processing...', dot: 'proc', mod: 'proc' },
    { label: 'Pasted',        dot: 'done', mod: 'done' },
    { label: 'Ready',         dot: 'rec',  mod: ''     },
  ];
  const durations = [2600, 1800, 1400, 1600]; // ms per state
  let si = 0;

  function advancePill() {
    si = (si + 1) % states.length;
    const s = states[si];

    pLabel.style.opacity = '0';
    setTimeout(() => {
      pLabel.textContent = s.label;
      pLabel.style.opacity = '1';
      pDot.className   = 'pill-dot ' + s.dot;
      pill.className   = 'pill'      + (s.mod ? ' ' + s.mod : '');
    }, 200);

    setTimeout(advancePill, durations[si]);
  }

  setTimeout(advancePill, durations[0]);

  /* ── Scroll Reveal ────────────────────────────── */
  const revealEls = document.querySelectorAll('.r');

  if ('IntersectionObserver' in window) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('vis');
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.07, rootMargin: '0px 0px -24px 0px' });

    revealEls.forEach(el => io.observe(el));
  } else {
    // Fallback: show everything immediately
    revealEls.forEach(el => el.classList.add('vis'));
  }

})();
