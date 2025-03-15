document.addEventListener("DOMContentLoaded", () => {
    document.getElementById('searchInput').addEventListener('keyup', searchArticles);
    document.getElementById('journalSelect').addEventListener('change', selectJournal);
    searchArticles();
});

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
        article.style.display = title.includes(input) || abstract.includes(input) || authors.includes(input) ? '' : 'none';
    });
}

function scrollToTop() {
    window.scrollTo({ top: 0, behavior: 'smooth' });
}
