// Shared Atlas theme helper. It changes presentation only and never fetches data.
(function () {
  "use strict";

  const root = document.documentElement;
  if (!root || !root.hasAttribute("data-atlas")) return;

  const storageKey = "brain.atlas.theme";
  const valid = value => value === "light" || value === "dark";
  let theme = valid(root.dataset.theme) ? root.dataset.theme : "light";
  try {
    const saved = localStorage.getItem(storageKey);
    if (valid(saved)) theme = saved;
  } catch (_) {}

  function buttons() {
    return Array.from(document.querySelectorAll("[data-atlas-theme]"));
  }

  function paint(next, announce) {
    const previous = root.dataset.theme;
    theme = valid(next) ? next : "light";
    root.dataset.theme = theme;
    const target = theme === "light" ? "Dark" : "Light";
    buttons().forEach(button => {
      button.textContent = target + " theme";
      button.setAttribute("aria-label", "Switch to " + target.toLowerCase() + " theme");
      button.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
    });
    if (announce && previous !== theme && typeof window.CustomEvent === "function") {
      window.dispatchEvent(new window.CustomEvent("atlas-theme-change", {detail: {theme}}));
    }
  }

  document.addEventListener("click", event => {
    const button = event.target.closest && event.target.closest("[data-atlas-theme]");
    if (!button) return;
    const next = theme === "light" ? "dark" : "light";
    try { localStorage.setItem(storageKey, next); } catch (_) {}
    paint(next, true);
  });

  paint(theme, false);
})();
