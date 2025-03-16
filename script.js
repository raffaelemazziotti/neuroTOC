document.addEventListener("DOMContentLoaded", () => {
  const body = document.body;
  const currentUpdatedDate = body.getAttribute("data-updated") || "N/A";
  const savedUpdatedDate = localStorage.getItem("siteUpdatedDate");

  // Check if site is updated or not
  if (savedUpdatedDate === currentUpdatedDate) {
      restoreSearchWord();
      restoreJournalSelect();
      restoreAccordionState();
      restoreScrollPosition();
  } else {
      // new/updated site
      localStorage.setItem("siteUpdatedDate", currentUpdatedDate);
      localStorage.removeItem("scrollPosition");
      localStorage.removeItem("accordionState");
      localStorage.removeItem("selectedJournal");
      localStorage.removeItem("searchWord");
  }

  // Setup input listeners
  document.getElementById('searchInput').addEventListener('keyup', onSearchChange);
  document.getElementById('searchInput').addEventListener('keyup', searchArticles);

  document.getElementById('journalSelect').addEventListener('change', onJournalSelect);
  document.getElementById('journalSelect').addEventListener('change', selectJournal);

  setupAccordion(); // "All Journals" accordion
  setupScrollSave(); // track scroll
  setupArticleCards(); // toggle abstract on article click, ignoring read-more link
  searchArticles(); // initial search
});

// -------------------------------------------
// 1) ACCORDION (ALL JOURNALS)
function setupAccordion() {
  const headers = document.querySelectorAll('.journal-header');
  headers.forEach(header => {
    header.addEventListener('click', toggleAccordion);
  });
}
function toggleAccordion(e) {
  e.preventDefault();
  const targetID = this.getAttribute('data-toggle');
  const icon = this.querySelector('.toggle-icon');
  const targetUl = document.getElementById(targetID);

  if (targetUl.style.display === 'block') {
    targetUl.style.display = 'none';
    icon.textContent = '+';
  } else {
    targetUl.style.display = 'block';
    icon.textContent = '-';
  }
  saveAccordionState();
}
function saveAccordionState() {
  const state = {};
  document.querySelectorAll('.accordion-item').forEach(item => {
    const header = item.querySelector('.journal-header');
    const toggleID = header.getAttribute('data-toggle');
    const ul = document.getElementById(toggleID);
    const open = (ul.style.display === 'block');
    state[toggleID] = open;
  });
  localStorage.setItem("accordionState", JSON.stringify(state));
}
function restoreAccordionState() {
  const savedState = localStorage.getItem("accordionState");
  if (!savedState) return;
  const state = JSON.parse(savedState);
  for (let toggleID in state) {
    const ul = document.getElementById(toggleID);
    if (!ul) continue;
    const open = state[toggleID];
    ul.style.display = open ? 'block' : 'none';
    // fix the icon
    const icon = ul.parentElement.querySelector('.toggle-icon');
    if (icon) icon.textContent = open ? '-' : '+';
  }
}

// -------------------------------------------
// 2) JOURNAL SELECT (DROPDOWN)
function onJournalSelect() {
  localStorage.setItem("selectedJournal", this.value);
  selectJournal();
}
function selectJournal() {
  const selected = document.getElementById('journalSelect').value;
  document.querySelectorAll('.journal-content').forEach(section => {
    section.style.display = (selected === 'All_Journals' || section.id === selected) ? 'block' : 'none';
  });
}
function restoreJournalSelect() {
  const savedJ = localStorage.getItem("selectedJournal");
  if (!savedJ) return;
  document.getElementById('journalSelect').value = savedJ;
  selectJournal();
}

// -------------------------------------------
// 3) SEARCH (TITLE, ABSTRACT, AUTHORS)
function onSearchChange() {
  localStorage.setItem("searchWord", this.value);
}
function restoreSearchWord() {
  const savedSearch = localStorage.getItem("searchWord");
  if (!savedSearch) return;
  document.getElementById('searchInput').value = savedSearch;
}
function searchArticles() {
  const input = document.getElementById('searchInput').value.toLowerCase().trim();
  const articles = document.querySelectorAll('.article-item');
  articles.forEach(article => {
    const title = article.getAttribute('data-title') || "";
    const abs   = article.getAttribute('data-abstract') || "";
    const auth  = article.getAttribute('data-authors') || "";
    article.style.display = (title.includes(input) || abs.includes(input) || auth.includes(input))
      ? ''
      : 'none';
  });
}

// -------------------------------------------
// 4) SCROLL POSITION
function setupScrollSave() {
  window.addEventListener('scroll', () => {
    localStorage.setItem("scrollPosition", window.scrollY);
  });
}
function restoreScrollPosition() {
  const savedPos = localStorage.getItem("scrollPosition");
  if (savedPos) {
    window.scrollTo({ top: parseInt(savedPos), left: 0, behavior: 'instant' });
  }
}

// -------------------------------------------
// 5) TOGGLE ABSTRACT WHEN CLICKING CARD, IGNORING <a>
function setupArticleCards() {
  const items = document.querySelectorAll('.article-item');
  items.forEach(item => {
    item.addEventListener('click', (e) => {
      // If clicked on <a>, do nothing special (open link).
      if (e.target.tagName.toLowerCase() === 'a') {
        return;
      }
      // Else, toggle the abstract
      e.preventDefault();
      const p = item.querySelector('.abstract');
      if (!p) return;
      const isOpen = (p.style.display === 'block');
      p.style.display = isOpen ? 'none' : 'block';
    });
  });
}

// -------------------------------------------
// 6) SCROLL TO TOP
function scrollToTop() {
  window.scrollTo({ top: 0, left: 0, behavior: 'smooth' });
  setTimeout(() => {
    document.documentElement.scrollTop = 0;
    document.body.scrollTop = 0;
  }, 800);
}
