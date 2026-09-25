/**
 * Arcane Forge docs SPA — hash router, i18n, search, TOC, Markdown render.
 */
(function () {
  "use strict";

  const CFG = window.DOCS_CONTENT;
  if (!CFG) {
    console.error("DOCS_CONTENT missing");
    return;
  }

  /** docs/{lang}/*.md live one level above /docs/site/ */
  const MD_BASE = "../";

  const els = {
    article: document.getElementById("article"),
    loading: document.getElementById("article-loading"),
    sidebarNav: document.getElementById("sidebar-nav"),
    sidebar: document.getElementById("sidebar"),
    sidebarBackdrop: document.getElementById("sidebar-backdrop"),
    btnMenu: document.getElementById("btn-menu"),
    tocNav: document.getElementById("toc-nav"),
    tocTitle: document.getElementById("toc-title"),
    pager: document.getElementById("pager"),
    brandLink: document.getElementById("brand-link"),
    brandName: document.getElementById("brand-name"),
    brandTag: document.getElementById("brand-tag"),
    searchLabel: document.getElementById("search-label"),
    searchKbd: document.getElementById("search-kbd"),
    btnSearch: document.getElementById("btn-search"),
    searchModal: document.getElementById("search-modal"),
    searchBackdrop: document.getElementById("search-backdrop"),
    searchInput: document.getElementById("search-input"),
    searchResults: document.getElementById("search-results"),
    searchEmpty: document.getElementById("search-empty"),
    langPt: document.getElementById("lang-pt"),
    langEn: document.getElementById("lang-en"),
  };

  let currentLang = CFG.defaultLang;
  let currentPage = null;
  let tocObserver = null;
  let searchActiveIndex = 0;

  const isMac = /Mac|iPhone|iPad/.test(navigator.platform || "");

  /* —— helpers —— */

  function ui() {
    return CFG.ui[currentLang] || CFG.ui.pt;
  }

  function pageLocale(page, lang) {
    return page[lang] || page.pt;
  }

  function findPageBySlug(lang, slug) {
    return CFG.pages.find((p) => pageLocale(p, lang).slug === slug) || null;
  }

  function findPageById(id) {
    return CFG.pages.find((p) => p.id === id) || null;
  }

  function hashFor(lang, slug) {
    return `#/${lang}/${slug}`;
  }

  function parseHash() {
    const raw = (location.hash || "").replace(/^#\/?/, "").trim();
    if (!raw) return { lang: CFG.defaultLang, slug: "overview" };
    const parts = raw.split("/").filter(Boolean);
    let lang = parts[0];
    let slug = parts.slice(1).join("/") || "overview";
    if (!CFG.langs[lang]) {
      lang = CFG.defaultLang;
      slug = parts.join("/") || "overview";
    }
    return { lang, slug };
  }

  function mdUrl(lang, file) {
    return `${MD_BASE}${lang}/${file}`;
  }

  function githubMdPath(lang, file) {
    return `../${lang}/${file}`;
  }

  function stripNavFooters(md) {
    return md
      .replace(/^\[←[^\]]+\]\([^)]+\)(?:\s*·\s*\[[^\]]+\]\([^)]+\))*\s*$/gm, "")
      .replace(/^\[[^\]]+\]\([^)]+\)(?:\s*·\s*\[[^\]]+\]\([^)]+\))+?\s*$/gm, (line) => {
        if (/Índice|Index|Seguinte|Next|Anterior|Previous|←|→/.test(line)) return "";
        return line;
      })
      .replace(/\n{3,}/g, "\n\n");
  }

  function rewriteMdLinks(html, lang) {
    const container = document.createElement("div");
    container.innerHTML = html;
    container.querySelectorAll("a[href]").forEach((a) => {
      const href = a.getAttribute("href") || "";
      if (/^https?:\/\//i.test(href) || href.startsWith("#") || href.startsWith("mailto:")) {
        return;
      }
      const cleaned = href.replace(/^\.\.\//, "").replace(/^\.\//, "");
      const file = cleaned.split("/").pop() || "";
      if (!file.endsWith(".md")) return;
      const base = file.replace(/\.md$/i, "");
      let target = findPageBySlug(lang, base);
      if (!target && (base === "README" || base.toLowerCase() === "readme")) {
        target = findPageById("overview");
      }
      if (!target) {
        // cross-lang filename (e.g. PT link to architecture slug)
        target = CFG.pages.find(
          (p) =>
            pageLocale(p, "pt").file === file ||
            pageLocale(p, "en").file === file ||
            pageLocale(p, "pt").slug === base ||
            pageLocale(p, "en").slug === base
        );
      }
      if (target) {
        a.setAttribute("href", hashFor(lang, pageLocale(target, lang).slug));
      }
    });
    return container.innerHTML;
  }

  function slugify(text) {
    return String(text)
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9\s-]/g, "")
      .trim()
      .replace(/\s+/g, "-")
      .slice(0, 80);
  }

  function applyHeadingIds(root) {
    const used = new Set();
    root.querySelectorAll("h2, h3").forEach((h) => {
      let id = h.id || slugify(h.textContent || "section");
      let n = 1;
      const base = id;
      while (used.has(id)) {
        id = `${base}-${n++}`;
      }
      used.add(id);
      h.id = id;
    });
  }

  function enhanceCodeBlocks(root) {
    const labels = ui();
    root.querySelectorAll("pre").forEach((pre) => {
      if (pre.querySelector(".code-copy")) return;
      const code = pre.querySelector("code");
      if (!code) return;
      if (code.classList.contains("language-mermaid")) return;
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "code-copy";
      btn.textContent = labels.copy;
      btn.addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(code.textContent || "");
          btn.textContent = labels.copied;
          setTimeout(() => {
            btn.textContent = labels.copy;
          }, 1400);
        } catch (_) {
          btn.textContent = "Error";
        }
      });
      pre.appendChild(btn);
      if (window.hljs) {
        window.hljs.highlightElement(code);
      }
    });
  }

  async function renderMermaid(root) {
    if (!window.mermaid) return;
    const blocks = root.querySelectorAll("code.language-mermaid, pre > code.language-mermaid");
    const nodes = [];
    blocks.forEach((code, i) => {
      const pre = code.closest("pre") || code.parentElement;
      const div = document.createElement("div");
      div.className = "mermaid";
      div.textContent = code.textContent || "";
      div.setAttribute("data-mermaid-id", `mmd-${Date.now()}-${i}`);
      pre.replaceWith(div);
      nodes.push(div);
    });
    if (!nodes.length) return;
    try {
      await window.mermaid.run({ nodes });
    } catch (err) {
      console.warn("mermaid render failed", err);
    }
  }

  /* —— UI chrome —— */

  function applyChrome() {
    const t = ui();
    document.documentElement.lang = CFG.langs[currentLang].htmlLang;
    els.brandName.textContent = t.brand;
    els.brandTag.textContent = t.tagline;
    els.brandLink.href = hashFor(currentLang, "overview");
    els.searchLabel.textContent = t.searchPlaceholder.replace("…", "…").slice(0, 18) || t.openSearch;
    els.searchKbd.textContent = isMac ? "⌘K" : "Ctrl K";
    els.btnSearch.setAttribute("aria-label", t.openSearch);
    els.searchInput.placeholder = t.searchPlaceholder;
    els.searchEmpty.textContent = t.searchEmpty;
    els.tocTitle.textContent = t.onThisPage;
    els.btnMenu.setAttribute("aria-label", t.menu);
    els.langPt.classList.toggle("is-active", currentLang === "pt");
    els.langEn.classList.toggle("is-active", currentLang === "en");
    document.title = `${t.brand} — Docs`;
  }

  function buildSidebar() {
    const t = ui();
    const sections = ["start", "generation", "play", "reference"];
    const frag = document.createDocumentFragment();
    sections.forEach((sec) => {
      const pages = CFG.pages.filter((p) => p.section === sec);
      if (!pages.length) return;
      const label = document.createElement("p");
      label.className = "sidebar__section";
      label.textContent = t.sections[sec] || sec;
      frag.appendChild(label);
      pages.forEach((page) => {
        const loc = pageLocale(page, currentLang);
        const a = document.createElement("a");
        a.className = "sidebar__link";
        a.href = hashFor(currentLang, loc.slug);
        a.dataset.pageId = page.id;
        a.textContent = loc.title;
        frag.appendChild(a);
      });
    });
    els.sidebarNav.replaceChildren(frag);
  }

  function setActiveSidebar(pageId) {
    els.sidebarNav.querySelectorAll(".sidebar__link").forEach((a) => {
      a.classList.toggle("is-active", a.dataset.pageId === pageId);
    });
  }

  function buildToc(root) {
    const headings = root.querySelectorAll("h2, h3");
    els.tocNav.replaceChildren();
    if (!headings.length) return;
    headings.forEach((h) => {
      const a = document.createElement("a");
      a.href = `#${h.id}`;
      a.textContent = h.textContent;
      a.className = h.tagName === "H3" ? "toc__h3" : "";
      a.addEventListener("click", (e) => {
        e.preventDefault();
        h.scrollIntoView({ behavior: "smooth", block: "start" });
        history.replaceState(null, "", `${location.hash.split("#")[0] || location.pathname}${location.hash}`.replace(/#$/, "") || location.href);
        // keep page hash; only scroll
        history.replaceState(null, "", location.hash);
      });
      els.tocNav.appendChild(a);
    });

    if (tocObserver) tocObserver.disconnect();
    const links = [...els.tocNav.querySelectorAll("a")];
    tocObserver = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting);
        if (!visible.length) return;
        const id = visible[0].target.id;
        links.forEach((l) => l.classList.toggle("is-active", l.getAttribute("href") === `#${id}`));
      },
      { rootMargin: "-20% 0px -65% 0px", threshold: 0 }
    );
    headings.forEach((h) => tocObserver.observe(h));
  }

  function buildPager(page) {
    const t = ui();
    const idx = CFG.pages.findIndex((p) => p.id === page.id);
    const prev = idx > 0 ? CFG.pages[idx - 1] : null;
    const next = idx < CFG.pages.length - 1 ? CFG.pages[idx + 1] : null;
    els.pager.replaceChildren();
    if (prev) {
      const loc = pageLocale(prev, currentLang);
      const a = document.createElement("a");
      a.className = "pager__link pager__link--prev";
      a.href = hashFor(currentLang, loc.slug);
      a.innerHTML = `<span class="pager__label">${t.prev}</span><span class="pager__title">${loc.title}</span>`;
      els.pager.appendChild(a);
    }
    if (next) {
      const loc = pageLocale(next, currentLang);
      const a = document.createElement("a");
      a.className = "pager__link pager__link--next";
      a.href = hashFor(currentLang, loc.slug);
      a.innerHTML = `<span class="pager__label">${t.next}</span><span class="pager__title">${loc.title}</span>`;
      els.pager.appendChild(a);
    }
  }

  function closeSidebar() {
    els.sidebar.classList.remove("is-open");
    els.btnMenu.setAttribute("aria-expanded", "false");
    els.sidebarBackdrop.hidden = true;
  }

  function openSidebar() {
    els.sidebar.classList.add("is-open");
    els.btnMenu.setAttribute("aria-expanded", "true");
    els.sidebarBackdrop.hidden = false;
  }

  /* —— Search —— */

  function openSearch() {
    els.searchModal.hidden = false;
    els.searchInput.value = "";
    els.searchResults.replaceChildren();
    els.searchEmpty.hidden = true;
    searchActiveIndex = 0;
    setTimeout(() => els.searchInput.focus(), 30);
  }

  function closeSearch() {
    els.searchModal.hidden = true;
  }

  function runSearch(q) {
    const query = q.trim().toLowerCase();
    const t = ui();
    els.searchResults.replaceChildren();
    if (!query) {
      els.searchEmpty.hidden = true;
      return;
    }
    const hits = CFG.pages
      .map((page) => {
        const loc = pageLocale(page, currentLang);
        const hay = `${loc.title} ${loc.search || ""} ${page.id} ${t.sections[page.section] || ""}`.toLowerCase();
        const score = hay.includes(query) ? (loc.title.toLowerCase().includes(query) ? 2 : 1) : 0;
        return { page, loc, score, section: t.sections[page.section] || page.section };
      })
      .filter((h) => h.score > 0)
      .sort((a, b) => b.score - a.score || a.loc.title.localeCompare(b.loc.title));

    if (!hits.length) {
      els.searchEmpty.hidden = false;
      return;
    }
    els.searchEmpty.hidden = true;
    hits.forEach((hit, i) => {
      const li = document.createElement("li");
      const btn = document.createElement("button");
      btn.type = "button";
      btn.role = "option";
      if (i === 0) btn.classList.add("is-active");
      btn.innerHTML = `<span class="result-title">${hit.loc.title}</span><span class="result-section">${hit.section}</span>`;
      btn.addEventListener("click", () => {
        closeSearch();
        location.hash = hashFor(currentLang, hit.loc.slug);
      });
      li.appendChild(btn);
      els.searchResults.appendChild(li);
    });
    searchActiveIndex = 0;
  }

  function moveSearch(delta) {
    const buttons = [...els.searchResults.querySelectorAll("button")];
    if (!buttons.length) return;
    buttons[searchActiveIndex]?.classList.remove("is-active");
    searchActiveIndex = (searchActiveIndex + delta + buttons.length) % buttons.length;
    buttons[searchActiveIndex].classList.add("is-active");
    buttons[searchActiveIndex].scrollIntoView({ block: "nearest" });
  }

  /* —— Load page —— */

  async function loadPage(lang, slug) {
    currentLang = lang;
    applyChrome();
    buildSidebar();

    let page = findPageBySlug(lang, slug);
    if (!page) {
      // try twin slug from other language
      const other = lang === "pt" ? "en" : "pt";
      const viaOther = findPageBySlug(other, slug);
      if (viaOther) {
        page = viaOther;
        const twinSlug = pageLocale(page, lang).slug;
        history.replaceState(null, "", hashFor(lang, twinSlug));
        slug = twinSlug;
      }
    }

    const t = ui();
    if (!page) {
      currentPage = null;
      setActiveSidebar("");
      els.article.innerHTML = `<p class="article__error">${t.notFound}</p>`;
      els.tocNav.replaceChildren();
      els.pager.replaceChildren();
      return;
    }

    currentPage = page;
    setActiveSidebar(page.id);
    closeSidebar();

    els.article.classList.add("is-fading");
    els.article.innerHTML = `<p class="article__loading">${t.loading}</p>`;

    const loc = pageLocale(page, lang);
    const url = mdUrl(lang, loc.file);

    let md;
    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error(String(res.status));
      md = await res.text();
    } catch (err) {
      els.article.classList.remove("is-fading");
      els.article.innerHTML = `<div class="article__error"><p>${t.fetchError}</p><p><code>${t.serveHint}</code></p></div>`;
      console.warn(err);
      return;
    }

    md = stripNavFooters(md);
    let html = window.marked.parse(md);
    html = rewriteMdLinks(html, lang);

    const wrap = document.createElement("div");
    wrap.innerHTML = html;

    // drop empty leading hrs from stripped nav
    while (wrap.firstChild && wrap.firstChild.nodeType === 1 && wrap.firstChild.tagName === "HR") {
      wrap.removeChild(wrap.firstChild);
    }

    applyHeadingIds(wrap);
    enhanceCodeBlocks(wrap);

    const source = document.createElement("a");
    source.className = "source-link";
    source.href = githubMdPath(lang, loc.file);
    source.target = "_blank";
    source.rel = "noopener";
    source.textContent = t.markdownSource;

    let calloutHtml = "";
    if (page.showBillingCallout) {
      calloutHtml = `<aside class="callout"><strong>Note.</strong> ${t.billingCallout}</aside>`;
    }

    els.article.replaceChildren();
    els.article.insertAdjacentHTML("beforeend", calloutHtml);
    els.article.appendChild(source);
    while (wrap.firstChild) {
      els.article.appendChild(wrap.firstChild);
    }

    els.article.classList.remove("is-fading");
    // re-trigger enter animation
    void els.article.offsetWidth;
    els.article.classList.add("article");

    buildToc(els.article);
    buildPager(page);
    await renderMermaid(els.article);

    document.title = `${loc.title} · ${t.brand}`;
    window.scrollTo(0, 0);
  }

  function switchLang(nextLang) {
    if (!CFG.langs[nextLang] || nextLang === currentLang) return;
    const page = currentPage || findPageById("overview");
    const slug = pageLocale(page, nextLang).slug;
    location.hash = hashFor(nextLang, slug);
  }

  function onRoute() {
    const { lang, slug } = parseHash();
    loadPage(lang, slug);
  }

  /* —— init —— */

  function initMarked() {
    if (!window.marked) return;
    window.marked.setOptions({
      gfm: true,
      breaks: false,
      mangle: false,
      headerIds: false,
    });
  }

  function initMermaid() {
    if (!window.mermaid) return;
    window.mermaid.initialize({
      startOnLoad: false,
      theme: "neutral",
      securityLevel: "strict",
      flowchart: { curve: "basis", htmlLabels: true },
    });
  }

  els.btnMenu.addEventListener("click", () => {
    if (els.sidebar.classList.contains("is-open")) closeSidebar();
    else openSidebar();
  });
  els.sidebarBackdrop.addEventListener("click", closeSidebar);

  els.langPt.addEventListener("click", () => switchLang("pt"));
  els.langEn.addEventListener("click", () => switchLang("en"));

  els.btnSearch.addEventListener("click", openSearch);
  els.searchBackdrop.addEventListener("click", closeSearch);
  els.searchInput.addEventListener("input", () => runSearch(els.searchInput.value));
  els.searchInput.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      moveSearch(1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      moveSearch(-1);
    } else if (e.key === "Enter") {
      e.preventDefault();
      const btn = els.searchResults.querySelectorAll("button")[searchActiveIndex];
      btn?.click();
    } else if (e.key === "Escape") {
      closeSearch();
    }
  });

  document.addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      if (els.searchModal.hidden) openSearch();
      else closeSearch();
    }
    if (e.key === "Escape" && !els.searchModal.hidden) closeSearch();
  });

  window.addEventListener("hashchange", onRoute);

  initMarked();
  initMermaid();
  applyChrome();
  buildSidebar();

  if (!location.hash) {
    location.replace(hashFor(CFG.defaultLang, "overview"));
  } else {
    onRoute();
  }
})();
