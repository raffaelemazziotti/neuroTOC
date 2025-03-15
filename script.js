document.addEventListener("DOMContentLoaded", () => {
    document.getElementById('searchInput').addEventListener('keyup', searchArticles);
    document.getElementById('journalSelect').addEventListener('change', selectJournal);

    searchArticles();
    setupAccordion();
});

function setupAccordion() {
    const headers = document.querySelectorAll('.journal-header');
    headers.forEach(header => {
        // Listen for both click + touchstart
        header.addEventListener('click', toggleAccordion);
        header.addEventListener('touchstart', toggleAccordion, { passive: true });
    });
}

function toggleAccordion(e) {
    e.preventDefault();
    const targetID = this.getAttribute('data-toggle');
    const icon = this.querySelector('.toggle-icon');
    const targetUl = document.getElementById(targetID);

    if (targetUl.style.display === 'block') {
        targetUl.style.display = 'none';
        icon.textContent = '▲'; // Collapsed
    } else {
        targetUl.style.display = 'block';
        icon.textContent = '▼'; // Expanded
    }
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

// Attempt to go to real top, even on mobile
function scrollToTop() {
    window.scrollTo({ top: 0, left: 0, behavior: 'smooth' });
    setTimeout(() => {
        document.documentElement.scrollTop = 0;
        document.body.scrollTop = 0;
    }, 800);
}
