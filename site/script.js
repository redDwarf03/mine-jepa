/*
  Mine-JEPA learning site — shared script.
  Vanilla JS, no dependencies. Progressive enhancement only: every page must
  already be readable with this file missing or blocked (see style.css,
  section 8 — without the "js" class on <html>, both track panels render
  stacked and labelled, and the tab buttons stay hidden).

  What this does:
  1. Powers the beginner/expert tab switch inside any `[data-tracks]` group
     on a chapter page (keyboard-operable tabs, ARIA kept in sync).
  2. Remembers the reader's preferred track (localStorage) and applies it to
     every `[data-tracks]` group found on the page, including on first load.
  3. Powers the small "Show me: Beginner / Expert" control in the header
     (`[data-track-pref]`), which is hidden by CSS until this script runs.
*/

(function () {
  "use strict";

  var STORAGE_KEY = "mine-jepa-track";
  var TRACKS = ["beginner", "expert"];

  function getPreferredTrack() {
    try {
      var value = localStorage.getItem(STORAGE_KEY);
      return TRACKS.indexOf(value) !== -1 ? value : null;
    } catch (err) {
      return null;
    }
  }

  function setPreferredTrack(track) {
    try {
      localStorage.setItem(STORAGE_KEY, track);
    } catch (err) {
      /* localStorage unavailable (private mode, etc.) — the toggle still
         works for the current page view, it just won't persist. */
    }
  }

  function activateTrack(group, track) {
    var panels = group.querySelectorAll("[data-track-panel]");
    var tabs = group.querySelectorAll("[data-track-tab]");
    var applied = track;

    var hasPanel = false;
    for (var i = 0; i < panels.length; i++) {
      if (panels[i].getAttribute("data-track-panel") === track) {
        hasPanel = true;
        break;
      }
    }
    if (!hasPanel && panels.length) {
      applied = panels[0].getAttribute("data-track-panel");
    }

    for (var p = 0; p < panels.length; p++) {
      var isMatch = panels[p].getAttribute("data-track-panel") === applied;
      panels[p].classList.toggle("is-active", isMatch);
    }

    for (var t = 0; t < tabs.length; t++) {
      var tabMatch = tabs[t].getAttribute("data-track-tab") === applied;
      tabs[t].setAttribute("aria-selected", tabMatch ? "true" : "false");
      tabs[t].tabIndex = tabMatch ? 0 : -1;
    }

    return applied;
  }

  function initTrackGroup(group, preferred) {
    var tabs = group.querySelectorAll("[data-track-tab]");
    if (!tabs.length) return;

    activateTrack(group, preferred || getPreferredTrack() || "beginner");

    for (var i = 0; i < tabs.length; i++) {
      var tab = tabs[i];
      tab.addEventListener("click", function (event) {
        var track = event.currentTarget.getAttribute("data-track-tab");
        activateTrack(group, track);
        setPreferredTrack(track);
        syncPrefControls(track);
      });

      tab.addEventListener("keydown", function (event) {
        var list = Array.prototype.slice.call(tabs);
        var index = list.indexOf(event.currentTarget);
        var nextIndex = null;

        if (event.key === "ArrowRight" || event.key === "ArrowDown") {
          nextIndex = (index + 1) % list.length;
        } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
          nextIndex = (index - 1 + list.length) % list.length;
        } else if (event.key === "Home") {
          nextIndex = 0;
        } else if (event.key === "End") {
          nextIndex = list.length - 1;
        }

        if (nextIndex !== null) {
          event.preventDefault();
          list[nextIndex].focus();
          list[nextIndex].click();
        }
      });
    }
  }

  function syncPrefControls(track) {
    var controls = document.querySelectorAll("[data-track-pref] button");
    for (var i = 0; i < controls.length; i++) {
      var match = controls[i].getAttribute("data-track-pref-value") === track;
      controls[i].setAttribute("aria-pressed", match ? "true" : "false");
    }
  }

  function initPrefControl() {
    var buttons = document.querySelectorAll("[data-track-pref] button");
    if (!buttons.length) return;

    var preferred = getPreferredTrack() || "beginner";
    syncPrefControls(preferred);

    for (var i = 0; i < buttons.length; i++) {
      buttons[i].addEventListener("click", function (event) {
        var track = event.currentTarget.getAttribute("data-track-pref-value");
        setPreferredTrack(track);
        syncPrefControls(track);
        var groups = document.querySelectorAll("[data-tracks]");
        for (var g = 0; g < groups.length; g++) {
          activateTrack(groups[g], track);
        }
      });
    }
  }

  function init() {
    var preferred = getPreferredTrack();
    var groups = document.querySelectorAll("[data-tracks]");
    for (var i = 0; i < groups.length; i++) {
      initTrackGroup(groups[i], preferred);
    }
    initPrefControl();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
