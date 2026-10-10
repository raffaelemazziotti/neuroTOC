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


def generate_html_from_xml(xml_file="all_journals_toc.xml", html_file="index.html"):
    """Generate the final HTML file.
       - Every article is rendered once, grouped in one collapsible section per journal
       - The dropdown and the search filter those sections client-side (script.js)
       - All text is HTML-escaped
    """
    tree = ET.parse(xml_file)
    root = tree.getroot()
    update_date = root.attrib.get('updated', 'N/A')
    filter_words = load_filter_words()

    dropdown_options = ""
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
            pub_date = article.findtext('PublicationDate') or "N/A"
            art_type = article.findtext('Type') or "N/A"
            abstract = clean_text(article.findtext('Abstract'))
            if not abstract or abstract == "No preview available":
                abstract = "No abstract available"

            articles_html += (
                '<li class="article-item"><details><summary>'
                f'<span class="article-title">{html.escape(title)}</span>'
                f'<span class="article-meta"><em>Authors:</em> <span class="article-authors">{html.escape(authors)}</span></span>'
                f'<span class="article-meta"><em>Published:</em> {html.escape(pub_date)} ({html.escape(art_type)})</span>'
                f'</summary><p class="abstract">{html.escape(abstract)}</p></details>'
                f'<a href="{html.escape(doi)}" target="_blank" rel="noopener" class="read-more-link">Read More</a></li>\n'
            )
            n_articles += 1

        total_articles += n_articles
        dropdown_options += f'<option value="{journal_id}">{html.escape(journal_name)} ({n_articles})</option>'
        sections_html += f"""
<section class="journal-section" id="{journal_id}">
  <h3 class="journal-header" role="button" tabindex="0" aria-expanded="true">
    <span class="toggle-icon">-</span> {html.escape(journal_name)} <span class="journal-count">({n_articles})</span>
  </h3>
  <ul class="article-list">
{articles_html}  </ul>
</section>
"""

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link
    rel="stylesheet"
    href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css"
  />
  <link rel="icon" type="image/svg+xml" href="logo.svg">
  <title>NeuroTOC</title>
  <link rel="stylesheet" type="text/css" href="style.css">
  <script src="script.js" defer></script>
</head>
<body data-updated="{html.escape(update_date)}">
  <h1>NeuroTOC</h1>
  <h2 style="text-align: center;">Updated: {html.escape(update_date.split(' ')[0])}</h2>

  <input type="search" id="searchInput" placeholder="Search titles, authors, abstracts..." aria-label="Search articles">
  <p id="articleCount" class="article-count">Showing {total_articles} articles</p>

  <div class="custom-select">
    <select id="journalSelect" aria-label="Journal">
      <option value="All_Journals">All Journals ({total_articles})</option>
      {dropdown_options}
    </select>
  </div>

  <div class="toolbar">
    <button type="button" id="expandAll">Expand all</button>
    <button type="button" id="collapseAll">Collapse all</button>
  </div>

  <div id="journals" class="journal-content">
    {sections_html}
  </div>

  <!-- Centered home button at bottom -->
  <button onclick="scrollToTop()" class="home-button" aria-label="Back to top">
    <i class="fas fa-home"></i>
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