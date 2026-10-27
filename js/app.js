/* Minimal behaviour: hash state, tag filter, lightbox, focus return.
   Layout of tabs and entries is CSS :target, so the archive still opens without this file. */
(function () {
  const tabs = Array.from(document.querySelectorAll('[role="tab"]'));
  const navLinks = Array.from(document.querySelectorAll("[data-nav]"));
  const dialog = document.getElementById("lightbox");
  const lbImg = document.getElementById("lb-img");
  const lbCap = document.getElementById("lb-cap");
  const lbCount = document.getElementById("lb-count");
  let lastCard = null;
  let gallery = [];
  let galleryIndex = 0;
  let previousId = (location.hash || "").slice(1);

  function isEntryId(id) {
    return /^(photographer|aesthetic|28mm)-\d{4}-\d{2}-\d{2}$/.test(id);
  }

  function streamFromHash() {
    const id = (location.hash || "#photographer").slice(1);
    if (id === "aesthetic" || id.startsWith("aesthetic-")) return "aesthetic";
    if (id === "28mm" || id.startsWith("28mm-")) return "28mm";
    if (id === "about" || id === "lines" || id === "top") return id === "top" ? "photographer" : id;
    return "photographer";
  }

  function syncAria() {
    const stream = streamFromHash();
    const entryOpen = Boolean(document.querySelector(".entry:target"));
    document.body.dataset.stream = entryOpen ? stream : stream;
    const current = "#" + stream;
    navLinks.forEach((a) => {
      if (a.getAttribute("href") === current && stream !== "about" && stream !== "lines") {
        a.setAttribute("aria-current", "page");
      } else if (a.getAttribute("href") === "#about" && stream === "about" && !entryOpen) {
        a.setAttribute("aria-current", "page");
      } else {
        a.removeAttribute("aria-current");
      }
    });
    tabs.forEach((a) => {
      const on = !entryOpen && a.getAttribute("href") === current;
      if (on) a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
      a.setAttribute("aria-selected", on ? "true" : "false");
    });
  }

  function normalizeQuery() {
    const params = new URLSearchParams(location.search);
    const tab = params.get("tab");
    const entry = params.get("entry");
    if (!tab && !entry) return;
    const map = { photographer: "photographer", aesthetic: "aesthetic", "28mm": "28mm", mm28: "28mm" };
    const stream = map[tab] || "";
    let hash = "";
    if (stream && entry && /^\d{4}-\d{2}-\d{2}$/.test(entry)) hash = stream + "-" + entry;
    else if (stream) hash = stream;
    if (!hash) return;
    history.replaceState(null, "", location.pathname + "#" + hash);
  }

  function focusEntry() {
    const entry = document.querySelector(".entry:target");
    if (!entry) return;
    const title = entry.querySelector("[data-entry-title]");
    if (title) title.focus();
  }

  document.addEventListener("click", (event) => {
    const card = event.target.closest("a.card");
    if (card) lastCard = card;
  });

  tabs.forEach((tab, index) => {
    tab.addEventListener("keydown", (event) => {
      if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
      event.preventDefault();
      const dir = event.key === "ArrowRight" ? 1 : -1;
      const next = tabs[(index + dir + tabs.length) % tabs.length];
      next.focus();
      next.click();
    });
  });

  document.querySelectorAll(".filters").forEach((group) => {
    group.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-filter]");
      if (!button) return;
      const panel = group.closest(".stream-panel");
      const key = button.dataset.filter;
      group.querySelectorAll("button[data-filter]").forEach((item) => {
        item.setAttribute("aria-pressed", item === button ? "true" : "false");
      });
      let visible = 0;
      panel.querySelectorAll("a.card").forEach((card) => {
        const show = key === "*" || card.dataset.cat === key;
        card.hidden = !show;
        if (show) visible += 1;
      });
      const empty = panel.querySelector(".empty");
      if (empty) empty.hidden = visible !== 0;
    });
  });

  function renderLightbox() {
    const item = gallery[galleryIndex];
    if (!item) return;
    lbImg.src = item.src;
    lbImg.alt = item.alt || "";
    lbCap.textContent = item.cap || "";
    lbCount.textContent = gallery.length > 1 ? galleryIndex + 1 + " / " + gallery.length : "";
  }

  function openLightbox(images, index) {
    gallery = images;
    galleryIndex = index;
    renderLightbox();
    if (typeof dialog.showModal === "function") dialog.showModal();
  }

  document.addEventListener("click", (event) => {
    const opener = event.target.closest(".plate-open");
    if (!opener) return;
    const entry = opener.closest(".entry");
    const buttons = Array.from(entry.querySelectorAll(".plate-open"));
    const images = buttons.map((button) => ({
      src: button.dataset.src,
      alt: button.dataset.alt || "",
      cap: button.dataset.cap || "",
    }));
    const index = buttons.indexOf(opener);
    openLightbox(images, index < 0 ? 0 : index);
  });

  document.getElementById("lb-prev").addEventListener("click", () => {
    if (!gallery.length) return;
    galleryIndex = (galleryIndex - 1 + gallery.length) % gallery.length;
    renderLightbox();
  });
  document.getElementById("lb-next").addEventListener("click", () => {
    if (!gallery.length) return;
    galleryIndex = (galleryIndex + 1) % gallery.length;
    renderLightbox();
  });
  document.getElementById("lb-close").addEventListener("click", () => dialog.close());

  dialog.addEventListener("keydown", (event) => {
    if (event.key === "ArrowLeft") document.getElementById("lb-prev").click();
    if (event.key === "ArrowRight") document.getElementById("lb-next").click();
  });

  dialog.addEventListener("close", () => {
    lbImg.removeAttribute("src");
  });

  window.addEventListener(
    "error",
    (event) => {
      const target = event.target;
      if (target && target.tagName === "IMG") target.classList.add("is-broken");
    },
    true
  );

  window.addEventListener("hashchange", () => {
    const id = (location.hash || "").slice(1);
    const wasEntry = isEntryId(previousId);
    syncAria();
    if (isEntryId(id)) focusEntry();
    else if (wasEntry && lastCard && document.contains(lastCard) && !lastCard.hidden) lastCard.focus();
    previousId = id;
  });

  normalizeQuery();
  previousId = (location.hash || "").slice(1);
  syncAria();
  if (isEntryId(previousId)) focusEntry();
})();
