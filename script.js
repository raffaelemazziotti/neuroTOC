// Each journal section, with its articles and the text used for searching
let sections = [];
let navLinks = [];
let selectedJournal = 'All_Journals';
let searchTimer = null;

document.addEventListener("DOMContentLoaded", () => {
  sections = Array.from(document.querySelectorAll('.journal-section')).map(sec => ({
    sec,
    header: sec.querySelector('.journal-header'),
    list: sec.querySelector('.article-list'),
    countEl: sec.querySelector('.journal-count'),
    items: Array.from(sec.querySelectorAll('.article-item')).map(el => {
      // searchable fields + the short author list, which is only highlighted
      const fields = [
        ['.article-title', true], ['.article-authors', true], ['.abstract', true],
        ['.article-topic', true], ['.article-keywords', true], ['.article-authors-short', false]
      ]
        .map(([sel, searchable]) => ({ node: el.querySelector(sel), searchable }))
        .filter(f => f.node)
        .map(f => ({ ...f, text: f.node.textContent }));
      return {
        el,
        fields,
        search: fields.filter(f => f.searchable).map(f => f.text).join(' ').toLowerCase(),
        highlighted: ''
      };
    })
  }));
  navLinks = Array.from(document.querySelectorAll('.journal-link')).map(btn => ({
    btn,
    id: btn.dataset.journal,
    countEl: btn.querySelector('.nav-count')
  }));

  const body = document.body;
  const currentUpdatedDate = body.getAttribute("data-updated") || "N/A";
  const savedUpdatedDate = localStorage.getItem("siteUpdatedDate");

  // A link from the trends page (index.html?q=microglia) opens a search across all journals
  // (&journal=biorxiv limits it to one journal)
  const params = new URLSearchParams(location.search);
  const linkedQuery = params.get('q');
  if (linkedQuery !== null) {
    localStorage.setItem("searchWord", linkedQuery);
    localStorage.setItem("selectedJournal", params.get('journal') || "All_Journals");
    localStorage.removeItem("scrollPosition");
  }

  // Check if site is updated or not
  if (savedUpdatedDate === currentUpdatedDate || linkedQuery !== null) {
      restoreSearchWord();
      restoreJournalSelect();
      restoreAccordionState();
  } else {
      // new/updated site
      localStorage.setItem("siteUpdatedDate", currentUpdatedDate);
      localStorage.removeItem("scrollPosition");
      localStorage.removeItem("accordionState");
      localStorage.removeItem("selectedJournal");
      localStorage.removeItem("searchWord");
  }
  if (linkedQuery !== null) localStorage.setItem("siteUpdatedDate", currentUpdatedDate);

  // Setup input listeners
  document.getElementById('searchInput').addEventListener('input', onSearchChange);
  document.getElementById('expandAll').addEventListener('click', () => setAllSections(true));
  document.getElementById('collapseAll').addEventListener('click', () => setAllSections(false));
  document.getElementById('toTop').addEventListener('click', scrollToTop);

  trackTopbarHeight(); // sticky headers sit right below the top bar
  setupJournalNav(); // sidebar on desktop, bottom sheet on mobile
  setupAccordion(); // collapsible journal sections
  setupArticleCards(); // toggle abstract on article click, ignoring read-more link
  applyFilters(); // initial search + journal filter
  if (savedUpdatedDate === currentUpdatedDate) restoreScrollPosition();
  setupScrollSave(); // track scroll + back-to-top button
});

// -------------------------------------------
// 0) LAYOUT
function trackTopbarHeight() {
  const topbar = document.querySelector('.topbar');
  const update = () => document.documentElement.style.setProperty('--topbar-h', `${topbar.offsetHeight}px`);
  new ResizeObserver(update).observe(topbar);
  update();
}

// -------------------------------------------
// 1) ACCORDION (JOURNAL SECTIONS)
function setupAccordion() {
  sections.forEach(s => {
    s.header.addEventListener('click', () => toggleSection(s));
    s.header.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        toggleSection(s);
      }
    });
  });
}
function setSectionOpen(s, open) {
  s.list.hidden = !open;
  s.header.setAttribute('aria-expanded', open);
}
function toggleSection(s) {
  const wasStuck = s.header.getBoundingClientRect().top <= s.sec.getBoundingClientRect().top - 1;
  setSectionOpen(s, s.list.hidden);
  // collapsing from a sticky header: bring the header back into view
  if (wasStuck && s.list.hidden) s.sec.scrollIntoView({ block: 'start' });
  saveAccordionState();
}
function setAllSections(open) {
  sections.forEach(s => setSectionOpen(s, open));
  saveAccordionState();
}
function saveAccordionState() {
  const state = {};
  sections.forEach(s => { state[s.sec.id] = !s.list.hidden; });
  localStorage.setItem("accordionState", JSON.stringify(state));
}
function restoreAccordionState() {
  const savedState = localStorage.getItem("accordionState");
  if (!savedState) return;
  const state = JSON.parse(savedState);
  sections.forEach(s => {
    if (s.sec.id in state) setSectionOpen(s, state[s.sec.id]);
  });
}

// -------------------------------------------
// 2) JOURNAL NAVIGATION (SIDEBAR / BOTTOM SHEET)
function setupJournalNav() {
  navLinks.forEach(link => link.btn.addEventListener('click', () => {
    selectJournal(link.id);
    closeSheet();
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
  }));
  document.getElementById('journalsButton').addEventListener('click', openSheet);
  document.getElementById('sidebarClose').addEventListener('click', closeSheet);
  document.getElementById('sheetBackdrop').addEventListener('click', closeSheet);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeSheet(); });
}
function selectJournal(id) {
  selectedJournal = id;
  localStorage.setItem("selectedJournal", id);
  applyFilters();
}
function restoreJournalSelect() {
  const savedJ = localStorage.getItem("selectedJournal");
  if (savedJ && navLinks.some(link => link.id === savedJ)) selectedJournal = savedJ;
}
function openSheet() {
  document.getElementById('sidebar').classList.add('open');
  document.getElementById('sheetBackdrop').hidden = false;
  document.getElementById('journalsButton').setAttribute('aria-expanded', 'true');
  const active = document.querySelector('.journal-link.active');
  if (active) active.focus();
}
function closeSheet() {
  document.getElementById('sidebar').classList.remove('open');
  document.getElementById('sheetBackdrop').hidden = true;
  document.getElementById('journalsButton').setAttribute('aria-expanded', 'false');
}

// -------------------------------------------
// 3) SEARCH (TITLE, AUTHORS, ABSTRACT)
function onSearchChange() {
  localStorage.setItem("searchWord", this.value);
  clearTimeout(searchTimer);
  searchTimer = setTimeout(applyFilters, 200);
}
function restoreSearchWord() {
  const savedSearch = localStorage.getItem("searchWord");
  if (!savedSearch) return;
  document.getElementById('searchInput').value = savedSearch;
}

// An article matches when it contains every word of the query, in any order
function applyFilters() {
  const query = document.getElementById('searchInput').value.toLowerCase().trim();
  const words = query.split(/\s+/).filter(Boolean);
  // Highlighting thousands of articles is slow, so skip it for very short queries
  const highlightKey = words.join('').length >= 3 ? words.join(' ') : '';
  const visibleBySection = {};
  let count = 0;
  let total = 0;

  sections.forEach(s => {
    let visible = 0;
    s.items.forEach(item => {
      const isVisible = words.every(w => item.search.includes(w));
      item.el.hidden = !isVisible;
      if (isVisible) {
        visible++;
        if (item.highlighted !== highlightKey) highlightItem(item, words, highlightKey);
      }
    });
    visibleBySection[s.sec.id] = visible;
    total += visible;

    const journalShown = (selectedJournal === 'All_Journals' || s.sec.id === selectedJournal);
    s.sec.hidden = !journalShown || (words.length > 0 && visible === 0);
    s.countEl.textContent = words.length ? `${visible} / ${s.items.length}` : `${s.items.length}`;
    if (journalShown) count += visible;
  });

  // Sidebar: counts follow the search, the selected journal is highlighted
  navLinks.forEach(link => {
    const n = link.id === 'All_Journals' ? total : visibleBySection[link.id];
    link.countEl.textContent = n;
    link.btn.classList.toggle('active', link.id === selectedJournal);
    link.btn.classList.toggle('empty', n === 0);
    if (link.id === selectedJournal) {
      document.getElementById('journalsButtonLabel').textContent = link.btn.querySelector('.journal-link-name').textContent;
    }
  });

  document.getElementById('articleCount').textContent = `Showing ${count} article${count !== 1 ? 's' : ''}`;
}

function escapeHtml(text) {
  return text.replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
}
function escapeRegExp(text) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}
function highlightItem(item, words, highlightKey) {
  if (!highlightKey) {
    item.fields.forEach(f => { f.node.textContent = f.text; });
  } else {
    const re = new RegExp(`(${words.map(escapeRegExp).join('|')})`, 'gi');
    item.fields.forEach(f => {
      f.node.innerHTML = escapeHtml(f.text).replace(re, '<mark>$1</mark>');
    });
  }
  item.highlighted = highlightKey;
}

// -------------------------------------------
// 4) SCROLL POSITION + BACK-TO-TOP BUTTON
function setupScrollSave() {
  const toTop = document.getElementById('toTop');
  const onScroll = () => {
    localStorage.setItem("scrollPosition", window.scrollY);
    toTop.hidden = window.scrollY < 600;
  };
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
}
function restoreScrollPosition() {
  const savedPos = localStorage.getItem("scrollPosition");
  if (savedPos) {
    window.scrollTo({ top: parseInt(savedPos), left: 0, behavior: 'instant' });
  }
}

// -------------------------------------------
// 5) TOGGLE ABSTRACT WHEN CLICKING CARD
// <details>/<summary> already handle clicks on the summary and the keyboard;
// this extends the click area to the rest of the card, ignoring the link and text selection.
function setupArticleCards() {
  document.getElementById('journals').addEventListener('click', (e) => {
    const item = e.target.closest('.article-item');
    if (!item || e.target.closest('a, summary')) return;
    if (window.getSelection().toString()) return;
    const details = item.querySelector('details');
    details.open = !details.open;
  });
}

// -------------------------------------------
// 6) SCROLL TO TOP
function scrollToTop() {
  window.scrollTo({ top: 0, left: 0, behavior: 'smooth' });
}
