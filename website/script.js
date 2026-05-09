(function () {
  "use strict";

  const nav = document.querySelector("[data-sticky-nav]");
  const storySteps = Array.from(document.querySelectorAll("[data-story]"));
  const storyPanel = document.querySelector("[data-story-panel]");
  const storyTitle = document.querySelector("[data-story-title]");
  const storyStatus = document.querySelector("[data-story-status]");
  const tabs = Array.from(document.querySelectorAll("[data-tab]"));

  const storyContent = {
    engine: {
      title: "Engine",
      status: "Ready"
    },
    audio: {
      title: "Audio",
      status: "Ready"
    },
    dictionary: {
      title: "Dictionary",
      status: "Ready"
    },
    history: {
      title: "History",
      status: "Ready"
    }
  };

  const storyTemplates = {
    engine: () => `
      <div class="app-form engine-preview">
        <label>Accuracy Model</label>
        <div class="app-select">Balanced (Small)<span></span></div>
        <label>Processing Device</label>
        <div class="app-select">CPU<span></span></div>
        <div class="app-toggle-row">
          <span class="mini-toggle on"><i></i></span>
          <strong>Start Stype when Windows signs in</strong>
        </div>
        <button class="app-primary">Apply Reload Engine</button>
      </div>
    `,
    audio: () => `
      <div class="app-form audio-preview">
        <label>Microphone</label>
        <div class="app-select">System Default<span></span></div>
        <label>Global Hotkey</label>
        <div class="app-hotkey">CTRL+SPACE</div>
        <p class="app-help">Click to change - then press your new key combo</p>
        <label>System Sound Input</label>
        <div class="app-toggle-row">
          <span class="mini-toggle"><i></i></span>
          <strong>Use system sound instead of the microphone</strong>
        </div>
        <p class="app-help">The pill adds a left speaker button for capturing audio playing on Windows.</p>
        <button class="app-primary">Save Audio Settings</button>
      </div>
    `,
    dictionary: () => `
      <div class="dictionary-preview">
        <div class="dict-head">
          <strong>Personal Dictionary</strong>
          <span><button>+ Word</button><button>+ Replacement</button></span>
        </div>
        <p>Add words to improve recognition, or set replacements.</p>
        <div class="dict-row"><b>Replace</b><span>out words</span><i>-></i><span>outwards</span><button>x</button></div>
        <div class="dict-row"><b>Replace</b><span>in words</span><i>-></i><span>inwards</span><button>x</button></div>
        <div class="dict-row"><b>Replace</b><span>stype</span><i>-></i><span>Stype</span><button>x</button></div>
      </div>
    `,
    history: () => `
      <div class="history-preview">
        <div class="search-like">Search transcriptions...</div>
        <div class="history-card">
          <p>Notes from a long dictation are stored locally with word count and character count.</p>
          <button>Copy</button>
          <small>just now · 188 words · 1027 chars</small>
        </div>
        <div class="history-actions">
          <button>Import History</button>
          <button>Export History</button>
          <button>Clear All</button>
        </div>
      </div>
    `
  };

  function setScrolledNav() {
    if (!nav) return;
    nav.classList.toggle("is-scrolled", window.scrollY > 8);
  }

  function renderStory(key) {
    const data = storyContent[key];
    if (!data || !storyPanel) return;

    storyTitle.textContent = data.title;
    storyStatus.textContent = data.status;
    storyStatus.style.background = data.status === "Pasted" || data.status === "Ready" ? "var(--green)" : "var(--yellow)";
    storyStatus.style.color = data.status === "Loading Model..." ? "var(--ink)" : "#fff";

    tabs.forEach((tab) => tab.classList.toggle("active", tab.dataset.tab === data.title));

    storyPanel.innerHTML = storyTemplates[key] ? storyTemplates[key]() : "";
  }

  function activateStory(key) {
    storySteps.forEach((step) => step.classList.toggle("is-active", step.dataset.story === key));
    renderStory(key);
  }

  function setupStoryObserver() {
    if (!storySteps.length || !("IntersectionObserver" in window)) {
      renderStory("engine");
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];

        if (visible) {
          activateStory(visible.target.dataset.story);
        }
      },
      { threshold: [0.35, 0.55, 0.75], rootMargin: "-12% 0px -28% 0px" }
    );

    storySteps.forEach((step) => observer.observe(step));
    renderStory("engine");
  }

  function setupReveal() {
    const revealTargets = document.querySelectorAll(".feature-card, .flow-card, .quick-panel, .section-heading");
    revealTargets.forEach((el) => el.classList.add("reveal"));

    if (!("IntersectionObserver" in window)) {
      revealTargets.forEach((el) => el.classList.add("is-visible"));
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: "0px 0px -40px 0px" }
    );

    revealTargets.forEach((el) => observer.observe(el));
  }

  function cloneMarquee() {
    const track = document.querySelector(".marquee-track");
    if (!track) return;
    track.innerHTML = track.innerHTML + track.innerHTML;
  }

  window.addEventListener("scroll", setScrolledNav, { passive: true });
  setScrolledNav();
  cloneMarquee();
  setupStoryObserver();
  setupReveal();
})();
