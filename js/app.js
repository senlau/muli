/* 目力: tabs, hash state, lightbox, broken-image placeholders.
   Pages work without this file: every tab panel is visible until it runs. */
(function () {
  "use strict";
  window.muliReady = true;

  /* ── tabs ─────────────────────────────────────────── */

  const groups = Array.from(document.querySelectorAll('[role="tablist"]')).map((list) => {
    const tabs = Array.from(list.querySelectorAll('[role="tab"]'));
    const panels = tabs.map((tab) => document.getElementById(tab.getAttribute("aria-controls")));
    return { tabs, panels };
  });

  function select(group, index, options) {
    const opts = options || {};
    group.tabs.forEach((tab, i) => {
      const on = i === index;
      tab.setAttribute("aria-selected", on ? "true" : "false");
      tab.tabIndex = on ? 0 : -1;
      if (group.panels[i]) group.panels[i].classList.toggle("is-active", on);
    });
    const tab = group.tabs[index];
    if (opts.focus) tab.focus();
    if (opts.record && tab.dataset.hash) {
      history.replaceState(null, "", "#" + tab.dataset.hash);
    }
  }

  groups.forEach((group) => {
    const start = Math.max(0, group.tabs.findIndex((tab) => tab.getAttribute("aria-selected") === "true"));
    select(group, start);
    group.tabs.forEach((tab, index) => {
      tab.addEventListener("click", (event) => {
        event.preventDefault();
        select(group, index, { record: true });
      });
      tab.addEventListener("keydown", (event) => {
        const last = group.tabs.length - 1;
        let next = null;
        if (event.key === "ArrowRight") next = index === last ? 0 : index + 1;
        else if (event.key === "ArrowLeft") next = index === 0 ? last : index - 1;
        else if (event.key === "Home") next = 0;
        else if (event.key === "End") next = last;
        if (next === null) return;
        event.preventDefault();
        select(group, next, { focus: true, record: true });
      });
    });
  });

  function followHash() {
    const id = decodeURIComponent(location.hash.slice(1));
    if (!id) return;
    for (const group of groups) {
      const byHash = group.tabs.findIndex((tab) => tab.dataset.hash === id);
      if (byHash >= 0) {
        select(group, byHash);
        return;
      }
    }
    const target = document.getElementById(id);
    if (!target) return;
    for (const group of groups) {
      const holder = group.panels.findIndex((panel) => panel && panel.contains(target));
      if (holder >= 0) {
        select(group, holder);
        target.scrollIntoView();
        return;
      }
    }
  }

  followHash();
  window.addEventListener("hashchange", followHash);

  /* ── broken images ────────────────────────────────── */

  const BROKEN = "图片暂时无法加载";

  function markBroken(img) {
    img.classList.add("is-broken");
    const box = img.closest(".plate-open, .card-img, .cell, .peer-img, .issue-figure a");
    if (box) box.setAttribute("data-broken", BROKEN);
  }

  document.querySelectorAll("main img").forEach((img) => {
    if (img.complete && img.naturalWidth === 0 && img.getAttribute("src")) markBroken(img);
    else img.addEventListener("error", () => markBroken(img), { once: true });
  });

  /* ── lightbox ─────────────────────────────────────── */

  const box = document.getElementById("lightbox");
  const openers = Array.from(document.querySelectorAll(".plate-open"));
  if (!box || !openers.length) return;

  const img = document.getElementById("lb-img");
  const cap = document.getElementById("lb-cap");
  const count = document.getElementById("lb-count");
  const prev = document.getElementById("lb-prev");
  const next = document.getElementById("lb-next");
  const close = document.getElementById("lb-close");
  let current = 0;
  let returnTo = null;

  function show(index) {
    current = index;
    const opener = openers[index];
    const thumb = opener.querySelector("img");
    img.classList.remove("is-broken");
    img.src = opener.dataset.src;
    img.alt = thumb ? thumb.alt : "";
    cap.textContent = opener.dataset.cap || "";
    count.textContent = openers.length > 1 ? index + 1 + " / " + openers.length : "";
    prev.hidden = next.hidden = openers.length < 2;
    prev.disabled = index === 0;
    next.disabled = index === openers.length - 1;
  }

  img.addEventListener("error", () => {
    img.classList.add("is-broken");
    cap.textContent = BROKEN;
  });

  openers.forEach((opener, index) => {
    opener.addEventListener("click", () => {
      if (typeof box.showModal !== "function") {
        window.open(opener.dataset.src, "_blank", "noopener");
        return;
      }
      returnTo = opener;
      show(index);
      box.showModal();
      close.focus();
    });
  });

  prev.addEventListener("click", () => current > 0 && show(current - 1));
  next.addEventListener("click", () => current < openers.length - 1 && show(current + 1));
  close.addEventListener("click", () => box.close());

  box.addEventListener("keydown", (event) => {
    if (event.key === "ArrowLeft" && current > 0) show(current - 1);
    else if (event.key === "ArrowRight" && current < openers.length - 1) show(current + 1);
  });

  box.addEventListener("click", (event) => {
    if (event.target === box || event.target.classList.contains("lb-figure")) box.close();
  });

  box.addEventListener("close", () => {
    img.removeAttribute("src");
    if (returnTo) returnTo.focus();
    returnTo = null;
  });
})();
