document.addEventListener("DOMContentLoaded", () => {
    const body = document.body;
    const currentUpdatedDate = body.getAttribute("data-updated") || "N/A";
    const savedUpdatedDate = localStorage.getItem("siteUpdatedDate");

    // If the site hasn't changed, restore previously saved states
    if (savedUpdatedDate === currentUpdatedDate) {
        restoreSearchWord();
        restoreJournalSelect();
        restoreAccordionState();
        restoreScrollPosition();
    } else {
        // The site is new or updated
        localStorage.setItem("siteUpdatedDate", currentUpdatedDate);
        // Clear old states
        localStorage.removeItem("scrollPosition");
        localStorage.removeItem("accordionState");
        localStorage.removeItem("selectedJournal");
        localStorage.removeItem("searchWord");
    }

    document.getElementById('searchInput').addEventListener('keyup', searchArticles);
    document.getElementById('journalSelect').addEventListener('change', selectJournal);

    document.getElementById('searchInput').addEventListener('keyup', onSearchChange);
    document.getElementById('journalSelect').addEventListener('change', onJournalSelect);

    setupAccordion();
    setupScrollSave();

    setupAbstractToggles();
});

function restoreState() {
    restoreAccordionState();
    restoreScrollPosition();
}

function setupAccordion() {
    const headers = document.querySelectorAll('.journal-header');
    headers.forEach(header => {
        header.addEventListener('click', toggleAccordion); // single event for mobile
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

// Restores each journal's open/close state
function restoreAccordionState() {
    const savedState = localStorage.getItem("accordionState");
    if (!savedState) return;

    const state = JSON.parse(savedState);
    for (let toggleID in state) {
        const ul = document.getElementById(toggleID);
        const open = state[toggleID];
        if (ul) {
            ul.style.display = open ? 'block' : 'none';
            // Also fix the icon
            const icon = ul.parentElement.querySelector('.toggle-icon');
            if (icon) icon.textContent = open ? '▼' : '▲';
        }
    }
}

// Track and save scroll position while user scrolls
function setupScrollSave() {
    window.addEventListener('scroll', () => {
        localStorage.setItem("scrollPosition", window.scrollY);
    });
}

function restoreJournalSelect() {
    const savedJ = localStorage.getItem("selectedJournal");
    if (!savedJ) return;
    document.getElementById('journalSelect').value = savedJ;
    selectJournal();
}

// Restore scroll position
function restoreScrollPosition() {
    const savedPos = localStorage.getItem("scrollPosition");
    if (savedPos) {
        // Jump to the old position
        window.scrollTo({ top: parseInt(savedPos), left: 0, behavior: 'instant' });
    }
}

// Save the changed search word
function onSearchChange() {
    localStorage.setItem("searchWord", this.value);
    searchArticles();  // The existing search function
}

// Restore search word from localStorage
function restoreSearchWord() {
    const savedSearch = localStorage.getItem("searchWord");
    if (!savedSearch) return;
    document.getElementById('searchInput').value = savedSearch;
    searchArticles();
}


function selectJournal() {
    const selected = document.getElementById('journalSelect').value;
    document.querySelectorAll('.journal-content').forEach(section => {
        section.style.display = (selected === 'All_Journals' || section.id === selected) ? 'block' : 'none';
    });
}

function searchArticles() {
    const input = document.getElementById('searchInput').value.toLowerCase().trim();
    const articles = document.querySelectorAll('.article-item');

    articles.forEach(article => {
        const title = article.getAttribute('data-title');
        const abstract = article.getAttribute('data-abstract');
        const authors = article.getAttribute('data-authors');
        article.style.display = (title.includes(input) || abstract.includes(input) || authors.includes(input))
            ? ''
            : 'none';
    });
}

// Save the changed dropdown selection
function onJournalSelect() {
    localStorage.setItem("selectedJournal", this.value);
    selectJournal();  // The existing function that toggles journal visibility
}

// Restore the selected journal
function restoreJournalSelect() {
    const savedJ = localStorage.getItem("selectedJournal");
    if (!savedJ) return;
    document.getElementById('journalSelect').value = savedJ;
    selectJournal();
}

function scrollToTop() {
    window.scrollTo({ top: 0, left: 0, behavior: 'smooth' });
    setTimeout(() => {
        document.documentElement.scrollTop = 0;
        document.body.scrollTop = 0;
    }, 800);
}

function setupAbstractToggles() {
  const toggleBtns = document.querySelectorAll('.toggle-abstract-btn');
  toggleBtns.forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const item = btn.closest('.article-item');
      const p = item.querySelector('.abstract');
      //const icon = btn.querySelector('.abs-expand-icon');

      // Toggle open/close
      const isOpen = (p.style.display === 'block');
      p.style.display = isOpen ? 'none' : 'block';
      btn.textContent = isOpen ? '+' : '-';
    });
  });
}


