import requests
from datetime import datetime, timedelta
import time
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import pandas as pd
import re
import html
from preprint_lib import get_latest_preprints

def save_dataframe_to_html(df: pd.DataFrame, output_file: str = "journals_list.html"):
    """(Optional) Save the DataFrame as a styled HTML table."""
    html_table = df.to_html(index=False, border=0, classes="dataframe", justify="center")
    with open(output_file, "w") as html_file:
        html_file.write(f"""
        <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>Journal List</title>
            <style>
                body {{ font-family: Arial, sans-serif; padding: 20px; background-color: #f9f9f9; }}
                h2 {{ text-align: center; color: #4CAF50; }}
                table.dataframe {{ 
                    width: 100%; 
                    border-collapse: collapse;
                    margin-top: 20px;
                }}
                th, td {{ 
                    border: 1px solid #ddd; 
                    padding: 10px; 
                    text-align: center;
                }}
                th {{
                    background-color: #4CAF50;
                    color: white;
                }}
                tr:nth-child(even) {{ background-color: #f2f2f2; }}
                tr:hover {{ background-color: #ddd; }}
                @media screen and (max-width: 600px) {{
                    th, td {{ padding: 8px; font-size: 14px; }}
                }}
            </style>
        </head>
        <body>
            <h2>Journal List</h2>
            {html_table}
        </body>
        </html>
        """)
    print(f"HTML table saved to '{output_file}'")

def get_journal_info():
    """Fetch the list of journals from Google Sheets as CSV into a DataFrame."""
    sheet_id = "1HIBPpTTpuznVZdr5Kf-hd6vp6iWYJQvjasnrmKv6p8w"
    sheet_name = "Foglio1"
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    df = pd.read_csv(url)
    return df

def clean_abstract(raw_abstract):
    """Strip HTML tags from the abstract, fallback to 'No preview available' if missing."""
    if raw_abstract and raw_abstract != 'N/A':
        return clean_text(raw_abstract)
    return "No preview available"

def get_journal_toc(issn):
    """Fetch all articles from the last 30 days for a given journal (ISSN) using CrossRef API with pagination."""
    month_start = (datetime.utcnow() - timedelta(days=30)).strftime('%Y-%m-%d')

    url = f"https://api.crossref.org/journals/{issn}/works"
    params = {
        "filter": f"from-pub-date:{month_start}",
        "rows": 100,
        "cursor": "*"
    }

    all_articles = []
    while True:
        response = requests.get(url, params=params)
        if response.status_code != 200:
            print(f"Error fetching ISSN {issn}: {response.status_code} {response.text[:300]}")
            break

        data = response.json()
        items = data.get("message", {}).get("items", [])
        if not items:
            break

        for article in items:
            title = article.get('title', ['N/A'])[0]
            doi = article.get('URL', 'N/A')
            authors_raw = article.get('author', [])
            authors_list = [f"{auth.get('family', 'N/A')} {auth.get('given', ['N/A'])[0]}." for auth in authors_raw]
            authors = '; '.join(authors_list) if len(authors_list) <= 25 else '; '.join(authors_list[:25])
            journal = article.get('container-title', ['N/A'])[0]
            raw_abstract = article.get('abstract', 'No preview available')
            abstract = clean_abstract(raw_abstract)
            pub_date = article.get('published', {}).get('date-parts', [['N/A', 'N/A']])[0]
            if len(pub_date) == 1:
                pub_date.append('N/A')
            art_type = article.get('type', 'N/A')

            all_articles.append({
                'title': title,
                'journal': journal,
                'pub_date': pub_date,
                'abstract': abstract,
                'authors': authors,
                'type': art_type,
                'doi': doi
            })

        next_cursor = data.get("message", {}).get("next-cursor")
        if not next_cursor or next_cursor == params["cursor"]:
            break

        params["cursor"] = next_cursor

    # CrossRef no longer allows sorting by publication date together with a cursor, so sort here (newest first)
    all_articles.sort(key=lambda a: [p if isinstance(p, int) else 0 for p in a['pub_date']], reverse=True)
    return all_articles


def save_all_toc_to_xml(journals, filename="all_journals_toc.xml"):
    """Save all TOC data into an XML file."""
    root = ET.Element("JournalsTOC", updated=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    # TODO insert preprints
    print('Downloading TOC from: Biorxiv')
    try:
        neuro_preprints = get_latest_preprints()
    except:
        neuro_preprints = []
    journal_elem = ET.SubElement(root, "Journal",
                                 name='Biorxiv',
                                 issn='0000-0000',
                                 updated=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    for article in neuro_preprints:
        article_elem = ET.SubElement(journal_elem, "Article")
        ET.SubElement(article_elem, "Title").text = article['title']
        ET.SubElement(article_elem, "Type").text = article['type']
        ET.SubElement(article_elem, "PublicationDate").text = article['date']
        ET.SubElement(article_elem, "Authors").text = article['authors']
        ET.SubElement(article_elem, "DOI").text = article['doi']
        ET.SubElement(article_elem, "Abstract").text = article['abstract']

    for _, journal in journals.iterrows():
        print(f"Downloading TOC from: {journal['Journal Name']}")
        journal_elem = ET.SubElement(root, "Journal",
                                     name=journal['Journal Name'],
                                     issn=journal['ISSN'],
                                     updated=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        toc = get_journal_toc(journal['ISSN'])
        for article in toc:
            article_elem = ET.SubElement(journal_elem, "Article")
            ET.SubElement(article_elem, "Title").text = article['title']
            ET.SubElement(article_elem, "Type").text = article['type']
            ET.SubElement(article_elem, "PublicationDate").text = f"{article['pub_date'][0]}/{article['pub_date'][1]}"
            ET.SubElement(article_elem, "Authors").text = article['authors']
            ET.SubElement(article_elem, "DOI").text = article['doi']
            ET.SubElement(article_elem, "Abstract").text = article['abstract']
        time.sleep(0.5)

    tree = ET.ElementTree(root)
    tree.write(filename, encoding="utf-8", xml_declaration=True)
    print(f"TOC with update dates saved to {filename}")


def clean_text(raw):
    """Strip HTML tags (e.g. <i> in titles) and collapse whitespace."""
    if not raw:
        return ""
    return " ".join(BeautifulSoup(raw, "html.parser").get_text().split())


def load_filter_words(filename="article_filter_words"):
    """Titles starting with one of these prefixes (corrections, errata, ...) are skipped."""
    try:
        with open(filename, encoding="utf-8") as f:
            return [line.strip().lower() for line in f if line.strip()]
    except FileNotFoundError:
        return []


def format_date(raw):
    """'2026-10-05' -> '5 Oct 2026', '2026/10' -> 'Oct 2026'; anything else is returned unchanged."""
    parts = re.split(r'[-/]', raw or '')
    try:
        year, month = int(parts[0]), int(parts[1])
        label = datetime(year, month, 1).strftime('%b %Y')
        return f"{int(parts[2])} {label}" if len(parts) > 2 else label
    except (ValueError, IndexError):
        return parts[0] if parts[0].isdigit() else (raw or "N/A")


def short_authors(authors, n=3):
    """First n authors followed by 'et al.' when the list is longer."""
    names = [a.strip() for a in authors.split(';') if a.strip()]
    if len(names) <= n:
        return authors
    return '; '.join(names[:n]) + ' et al.'


def generate_html_from_xml(xml_file="all_journals_toc.xml", html_file="index.html"):
    """Generate the final HTML file.
       - Every article is rendered once, grouped in one collapsible section per journal
       - The journal sidebar (a bottom sheet on mobile) and the search filter those sections client-side (script.js)
       - All text is HTML-escaped
    """
    tree = ET.parse(xml_file)
    root = tree.getroot()
    update_date = root.attrib.get('updated', 'N/A')
    filter_words = load_filter_words()

    journal_nav = ""
    sections_html = ""
    total_articles = 0

    for journal in root.findall('Journal'):
        journal_name = journal.get('name')
        journal_id = re.sub(r'[^a-z0-9]+', '_', journal_name.lower()).strip('_')

        articles_html = ""
        n_articles = 0
        for article in journal.findall('Article'):
            title = clean_text(article.findtext('Title')) or "N/A"
            if any(title.lower().startswith(w) for w in filter_words):
                continue
            doi = article.findtext('DOI') or "#"
            authors = clean_text(article.findtext('Authors')) or "N/A"
            pub_date = format_date(article.findtext('PublicationDate'))
            art_type = article.findtext('Type') or ""
            abstract = clean_text(article.findtext('Abstract'))
            has_abstract = bool(abstract) and abstract != "No preview available"
            if not has_abstract:
                abstract = "No abstract available"

            # 'journal-article' is almost every CrossRef item, so only show the other types
            type_tag = f'<span class="tag">{html.escape(art_type)}</span>' if art_type and art_type != 'journal-article' else ''
            abstract_tag = '<span class="tag tag-abstract">Abstract</span>' if has_abstract else ''

            articles_html += (
                '<li class="article-item"><details><summary>'
                f'<span class="article-title">{html.escape(title)}</span>'
                f'<span class="article-authors-short">{html.escape(short_authors(authors))}</span>'
                f'<span class="article-meta"><span>{html.escape(pub_date)}</span>{type_tag}{abstract_tag}</span>'
                '</summary><div class="article-body">'
                f'<p class="article-authors">{html.escape(authors)}</p>'
                f'<p class="abstract">{html.escape(abstract)}</p></div></details>'
                f'<a href="{html.escape(doi)}" target="_blank" rel="noopener" class="read-more-link">Read article &#8599;</a></li>\n'
            )
            n_articles += 1

        total_articles += n_articles
        journal_nav += (
            f'<li><button type="button" class="journal-link" data-journal="{journal_id}">'
            f'<span class="journal-link-name">{html.escape(journal_name)}</span>'
            f'<span class="nav-count">{n_articles}</span></button></li>\n'
        )
        sections_html += f"""
<section class="journal-section" id="{journal_id}">
  <h2 class="journal-header" role="button" tabindex="0" aria-expanded="true">
    <span class="toggle-icon" aria-hidden="true"></span>
    <span class="journal-name">{html.escape(journal_name)}</span>
    <span class="journal-count">{n_articles}</span>
  </h2>
  <ul class="article-list">
{articles_html}  </ul>
</section>
"""

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="color-scheme" content="dark light">
  <link rel="icon" type="image/svg+xml" href="logo.svg">
  <title>NeuroTOC</title>
  <link rel="stylesheet" type="text/css" href="style.css">
  <script src="script.js" defer></script>
</head>
<body data-updated="{html.escape(update_date)}">
  <header class="topbar">
    <div class="topbar-inner">
      <a class="brand" href="#" aria-label="NeuroTOC home">
        <img src="logo.svg" alt="" width="32" height="32">
        <span class="brand-text">NeuroTOC</span>
      </a>
      <span class="updated">Updated {html.escape(update_date.split(' ')[0])}</span>
      <input type="search" id="searchInput" placeholder="Search titles, authors, abstracts..." aria-label="Search articles">
      <button type="button" id="journalsButton" class="journals-button" aria-controls="sidebar" aria-expanded="false">
        <span id="journalsButtonLabel">All journals</span> &#9662;
      </button>
    </div>
  </header>

  <div class="layout">
    <nav id="sidebar" class="sidebar" aria-label="Journals">
      <div class="sidebar-head">
        <span>Journals</span>
        <button type="button" id="sidebarClose" class="sidebar-close" aria-label="Close journal list">&#10005;</button>
      </div>
      <ul class="journal-nav">
        <li><button type="button" class="journal-link" data-journal="All_Journals">
          <span class="journal-link-name">All journals</span><span class="nav-count">{total_articles}</span></button></li>
        {journal_nav}
      </ul>
    </nav>

    <main id="journals">
      <div class="results-bar">
        <p class="article-count"><span id="articleCount">Showing {total_articles} articles</span><span class="updated-inline"> &middot; Updated {html.escape(update_date.split(' ')[0])}</span></p>
        <div class="toolbar">
          <button type="button" id="expandAll">Expand all</button>
          <button type="button" id="collapseAll">Collapse all</button>
        </div>
      </div>
      {sections_html}
    </main>
  </div>

  <div id="sheetBackdrop" class="sheet-backdrop" hidden></div>

  <button type="button" id="toTop" class="to-top" aria-label="Back to top" hidden>
    <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path d="M12 5l-7 7m7-7l7 7M12 5v14" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
  </button>
</body>
</html>
"""
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"HTML file saved to {html_file}")


if __name__ == "__main__":
    #journals = get_journal_info()
    #save_dataframe_to_html(journals)
    #save_all_toc_to_xml(journals)
    generate_html_from_xml()