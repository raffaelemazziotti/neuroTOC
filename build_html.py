import requests
from datetime import datetime, timedelta
import time
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import pandas as pd
import re
import html
import os
from preprint_lib import get_latest_preprints
from pubmed_lib import get_pubmed_records, normalize_doi
from openalex_lib import get_openalex_records
from trends_lib import build_trends

def load_env_file(filename=".env"):
    """Local runs: read API keys (OPENALEX_API_KEY, NCBI_API_KEY) from a .env file, which git ignores.
    Variables already set (e.g. GitHub secrets in the weekly job) take precedence."""
    if not os.path.exists(filename):
        return
    with open(filename, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip("'\""))


load_env_file()


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

def get_journal_toc(issn, end_date=None):
    """Fetch all articles from the 30 days before end_date (default: now) for a given journal (ISSN)
    using CrossRef API with pagination."""
    end = end_date or datetime.utcnow()
    month_start = (end - timedelta(days=30)).strftime('%Y-%m-%d')
    date_filter = f"from-pub-date:{month_start}"
    if end_date:
        date_filter += f",until-pub-date:{end_date.strftime('%Y-%m-%d')}"

    url = f"https://api.crossref.org/journals/{issn}/works"
    params = {
        "filter": date_filter,
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


def add_openalex_tags(article_elem, oa_record):
    """Store OpenAlex's topic and keywords on an <Article> element."""
    if oa_record:
        ET.SubElement(article_elem, "Topic").text = oa_record['topic']
        ET.SubElement(article_elem, "OpenAlexKeywords").text = '; '.join(oa_record['keywords'])
        ET.SubElement(article_elem, "TopicFields").text = '; '.join(oa_record['topic_fields'])


def save_all_toc_to_xml(journals, filename="all_journals_toc.xml", end_date=None):
    """Save all TOC data into an XML file. end_date (a datetime) downloads an earlier period instead of
    the latest one; backfill_trends.py uses it to rebuild the history of the trends page."""
    updated = (end_date or datetime.now()).strftime('%Y-%m-%d %H:%M:%S')
    root = ET.Element("JournalsTOC", updated=updated)
    print('Downloading TOC from: Biorxiv')
    try:
        neuro_preprints = get_latest_preprints(end_date)
    except:
        neuro_preprints = []
    biorxiv_updated = updated

    tocs = []
    for _, journal in journals.iterrows():
        print(f"Downloading TOC from: {journal['Journal Name']}")
        tocs.append((journal, get_journal_toc(journal['ISSN'], end_date), updated if end_date else datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        time.sleep(0.5)

    # PubMed adds what CrossRef lacks: article types (to drop news, editorials, errata, ...),
    # missing abstracts (Elsevier, Springer), MeSH terms and author keywords.
    # OpenAlex covers the articles PubMed has not indexed yet (types are coarser there),
    # and gives every article, preprints included, a topic and keywords.
    journal_dois = [article['doi'] for _, toc, _ in tocs for article in toc]
    print('Looking up articles in PubMed')
    try:
        pubmed = get_pubmed_records(journal_dois)
    except Exception as e:
        print(f"PubMed lookup failed, continuing without it: {e}")
        pubmed = {}
    print('Looking up articles in OpenAlex')
    try:
        openalex = get_openalex_records(journal_dois + [article['doi'] for article in neuro_preprints])
    except Exception as e:
        print(f"OpenAlex lookup failed: {e}")
        openalex = {}
    # Topics, keywords and the neuroscience filter depend on OpenAlex: without it the page would silently
    # lose them and general journals would come back unfiltered, so stop instead of publishing that
    found = sum(normalize_doi(d) in openalex for d in journal_dois)
    if journal_dois and found < 0.5 * len(journal_dois):
        raise RuntimeError(f"OpenAlex returned data for only {found} of {len(journal_dois)} articles; "
                           "not publishing. Set OPENALEX_API_KEY or retry later.")

    journal_elem = ET.SubElement(root, "Journal",
                                 name='Biorxiv',
                                 issn='0000-0000',
                                 updated=biorxiv_updated)
    for article in neuro_preprints:
        article_elem = ET.SubElement(journal_elem, "Article")
        ET.SubElement(article_elem, "Title").text = article['title']
        ET.SubElement(article_elem, "Type").text = article['type']
        ET.SubElement(article_elem, "PublicationDate").text = article['date']
        ET.SubElement(article_elem, "Authors").text = article['authors']
        ET.SubElement(article_elem, "DOI").text = article['doi']
        ET.SubElement(article_elem, "Abstract").text = article['abstract']
        add_openalex_tags(article_elem, openalex.get(normalize_doi(article['doi'])))

    for journal, toc, updated in tocs:
        journal_elem = ET.SubElement(root, "Journal",
                                     name=journal['Journal Name'],
                                     issn=journal['ISSN'],
                                     updated=updated)
        for article in toc:
            record = pubmed.get(normalize_doi(article['doi']))
            oa_record = openalex.get(normalize_doi(article['doi']))
            abstract = article['abstract']
            for source in (record, oa_record):
                if source and source['abstract'] and abstract == "No preview available":
                    abstract = source['abstract']
            article_elem = ET.SubElement(journal_elem, "Article")
            ET.SubElement(article_elem, "Title").text = article['title']
            ET.SubElement(article_elem, "Type").text = article['type']
            ET.SubElement(article_elem, "PublicationDate").text = f"{article['pub_date'][0]}/{article['pub_date'][1]}"
            ET.SubElement(article_elem, "Authors").text = article['authors']
            ET.SubElement(article_elem, "DOI").text = article['doi']
            ET.SubElement(article_elem, "Abstract").text = abstract
            if oa_record and not record:
                ET.SubElement(article_elem, "OpenAlexType").text = oa_record['type']
            add_openalex_tags(article_elem, oa_record)
            if record:
                ET.SubElement(article_elem, "PubMedTypes").text = '; '.join(record['types'])
                ET.SubElement(article_elem, "MeSH").text = '; '.join(record['mesh_major'])
                ET.SubElement(article_elem, "Keywords").text = '; '.join(record['keywords'])

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


# PubMed publication types that are not research articles or reviews
EXCLUDED_PUBMED_TYPES = {
    "News", "Newspaper Article", "Comment", "Editorial", "Interview", "Letter",
    "Published Erratum", "Retraction of Publication", "Retraction Notice", "Expression of Concern",
    "Biography", "Portrait", "Obituary", "Autobiography", "Personal Narrative", "Lecture",
    "Congress", "Bibliography", "Directory",
}
REVIEW_PUBMED_TYPES = {"Review", "Systematic Review", "Scoping Review"}
# OpenAlex types used for articles not yet in PubMed
EXCLUDED_OPENALEX_TYPES = {"erratum", "retraction", "editorial", "letter", "paratext", "book-review"}
# Journal front matter that has no title prefix to match on
FRONT_MATTER_TITLES = {
    "n/a", "editorial board", "editorial board page", "in this issue", "subscribers page",
    "issue information", "table of contents", "contents", "masthead", "cover", "front matter",
    "back matter", "information for authors", "instructions for authors",
}


def classify_article(article, title, filter_words):
    """Return (kind, reason): kind is 'research', 'review' or 'meta-analysis', or None when the
    article is excluded (news, editorials, comments, errata, ...); reason says which rule excluded it."""
    if any(title.lower().startswith(w) for w in filter_words):
        return None, "title"
    if title.lower().strip(' .') in FRONT_MATTER_TITLES or title.lower().endswith("books in brief"):
        return None, "front matter"
    pubmed_types = article.findtext('PubMedTypes')
    if pubmed_types is not None:
        types = {t.strip() for t in pubmed_types.split(';') if t.strip()}
        if types & EXCLUDED_PUBMED_TYPES:
            return None, "pubmed"
        if types & REVIEW_PUBMED_TYPES:
            return "review", None
        if "Meta-Analysis" in types:
            return "meta-analysis", None
        return "research", None
    if (article.findtext('OpenAlexType') or '') in EXCLUDED_OPENALEX_TYPES:
        return None, "openalex"
    return "research", None


# Neuroscience filter for general journals (Nature, Scientific Reports, PNAS, ...), based on OpenAlex topics.
# A journal where at least this share of articles is neuroscience counts as a neuroscience journal
# and is kept whole; in the others only the neuroscience articles are kept.
NEURO_JOURNAL_SHARE = 0.7
NEURO_SUBFIELDS = {
    "Psychiatry and Mental health", "Neurology", "Clinical Psychology", "Experimental and Cognitive Psychology",
    "Developmental and Educational Psychology", "Behavioral Neuroscience", "Cognitive Neuroscience", "Sensory Systems",
}
# phrases that contain neuro-words but are not neuroscience (machine learning, oncology of other organs, ...)
NOT_NEURO_RE = re.compile(
    r"neural networks?|neural operator|neural radiance|neural computing|neuromorphic|neuroendocrine|"
    r"dendritic cells?|adrenal cortex|renal cortex|adrenocortical|striated muscle", re.I)
NEURO_RE = re.compile(
    r"neur|brain|cortex|cortical|hippocamp|synap|glia|glioma|glioblastoma|astrocyt|microglia|\baxon|dendrit|spinal cord|"
    r"cerebr|alzheimer|parkinson|dementia|epilep|seizure|stroke|autis|schizophren|psychiatr|depressi|anxiety|bipolar|"
    r"\bcognit|sleep|nocicept|\bpain\b|\bnicotine\b|addiction|dopamin|serotonin|amygdala|thalam|striatum|striatal|cerebell|"
    r"multiple sclerosis|amyotrophic|huntington|migraine|concussion|nervous system|psychosis|psychotic|adhd|"
    r"consciousness|fmri|electroencephalogra|retina|optogenet|anesthe",
    re.I)


def neuro_title(text):
    """Does the text contain a neuroscience word?"""
    return bool(NEURO_RE.search(NOT_NEURO_RE.sub(' ', text)))


def is_neuroscience(article, title):
    """True/False from OpenAlex's topics (field, subfield, name) and the title; None when OpenAlex has no topics."""
    topic_fields = [t.split(' > ') for t in (article.findtext('TopicFields') or '').split('; ') if t.count(' > ') == 2]
    if not topic_fields:
        return None
    if any(field == "Neuroscience" or subfield in NEURO_SUBFIELDS for field, subfield, _ in topic_fields):
        return True
    return neuro_title(topic_fields[0][2]) or neuro_title(title)


def article_tags(article):
    """Major MeSH topics and author keywords from PubMed; OpenAlex keywords when PubMed has none."""
    tags, seen = [], set()
    fields = ('MeSH', 'Keywords') if (article.findtext('MeSH') or article.findtext('Keywords')) else ('OpenAlexKeywords',)
    for field in fields:
        for tag in (article.findtext(field) or '').split(';'):
            tag = tag.strip()
            if tag and tag.lower() not in seen:
                seen.add(tag.lower())
                tags.append(tag)
    return tags[:8]


def short_authors(authors, n=3):
    """First n authors followed by 'et al.' when the list is longer."""
    names = [a.strip() for a in authors.split(';') if a.strip()]
    if len(names) <= n:
        return authors
    return '; '.join(names[:n]) + ' et al.'


def generate_html_from_xml(xml_file="all_journals_toc.xml", html_file="index.html", trends_file="trends.html"):
    """Generate the final HTML file.
       - Every article is rendered once, grouped in one collapsible section per journal
       - General journals keep only their neuroscience articles (is_neuroscience)
       - The journal sidebar (a bottom sheet on mobile) and the search filter those sections client-side (script.js)
       - All text is HTML-escaped
    """
    tree = ET.parse(xml_file)
    root = tree.getroot()
    update_date = root.attrib.get('updated', 'N/A')
    filter_words = load_filter_words()
    excluded = {}

    journal_nav = ""
    sections_html = ""
    total_articles = 0
    page_articles = []  # what the trends page counts: exactly the articles shown

    for journal in root.findall('Journal'):
        journal_name = journal.get('name')
        journal_id = re.sub(r'[^a-z0-9]+', '_', journal_name.lower()).strip('_')

        cards = []  # (card html, is neuroscience per OpenAlex or None, neuroscience word in title, article info)
        for article in journal.findall('Article'):
            title = clean_text(article.findtext('Title')) or "N/A"
            doi = article.findtext('DOI') or "#"
            authors = clean_text(article.findtext('Authors')) or "N/A"
            pub_date = format_date(article.findtext('PublicationDate'))
            art_type = article.findtext('Type') or ""
            abstract = clean_text(article.findtext('Abstract'))
            has_abstract = bool(abstract) and abstract != "No preview available"
            kind, reason = classify_article(article, title, filter_words)
            if kind is None:
                excluded[reason] = excluded.get(reason, 0) + 1
                continue
            if not has_abstract:
                abstract = "No abstract available"
            tags = article_tags(article)
            topic = article.findtext('Topic') or ''
            tags_html = ''
            if topic:
                tags_html += f'<p class="article-tags"><span class="tags-label">Topic:</span> <span class="article-topic">{html.escape(topic)}</span></p>'
            if tags:
                tags_html += f'<p class="article-tags"><span class="tags-label">Keywords:</span> <span class="article-keywords">{html.escape(" · ".join(tags))}</span></p>'

            # 'journal-article' is almost every CrossRef item, so only show the other types
            if kind != "research":
                type_tag = f'<span class="tag tag-kind">{kind.capitalize()}</span>'
            elif art_type and art_type != 'journal-article':
                type_tag = f'<span class="tag">{html.escape(art_type)}</span>'
            else:
                type_tag = ''
            abstract_tag = '<span class="tag tag-abstract">Abstract</span>' if has_abstract else ''

            cards.append((
                '<li class="article-item"><details><summary>'
                f'<span class="article-title">{html.escape(title)}</span>'
                f'<span class="article-authors-short">{html.escape(short_authors(authors))}</span>'
                f'<span class="article-meta"><span>{html.escape(pub_date)}</span>{type_tag}{abstract_tag}</span>'
                '</summary><div class="article-body">'
                f'<p class="article-authors">{html.escape(authors)}</p>'
                f'<p class="abstract">{html.escape(abstract)}</p>{tags_html}</div></details>'
                f'<a href="{html.escape(doi)}" target="_blank" rel="noopener" class="read-more-link">Read article &#8599;</a></li>\n',
                is_neuroscience(article, title),
                neuro_title(title),
                {'title': title, 'abstract': abstract if has_abstract else '', 'has_abstract': has_abstract,
                 'topic': topic, 'tags': tags, 'journal': journal_name, 'kind': kind,
                 # one keyword source for every article, so trends compare like with like across periods
                 'oa_keywords': [k.strip() for k in (article.findtext('OpenAlexKeywords') or '').split(';') if k.strip()]}
            ))

        # General journals keep only their neuroscience articles (bioRxiv is already the neuroscience category)
        judged = [neuro for _, neuro, _, _ in cards if neuro is not None]
        neuro_share = sum(judged) / len(judged) if judged else 1
        if journal.get('issn') != '0000-0000' and neuro_share < NEURO_JOURNAL_SHARE:
            # articles OpenAlex does not know yet are judged on their title alone
            kept = [(card, info) for card, neuro, title_hit, info in cards if neuro or (neuro is None and title_hit)]
            excluded['off-topic'] = excluded.get('off-topic', 0) + len(cards) - len(kept)
            print(f"General journal: {journal_name} ({neuro_share:.0%} neuroscience), kept {len(kept)} of {len(cards)}")
        else:
            kept = [(card, info) for card, _, _, info in cards]
        articles_html = "".join(card for card, _ in kept)
        page_articles += [info for _, info in kept]
        n_articles = len(kept)

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
      <nav class="topnav"><a class="nav-pill active" href="index.html" aria-current="page">Articles</a><a class="nav-pill" href="trends.html">Trends</a></nav>
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

    print(f"Excluded articles: {sum(excluded.values())} {excluded}")
    print(f"HTML file saved to {html_file}")

    build_trends(page_articles, update_date.split(' ')[0], trends_file)


if __name__ == "__main__":
    #journals = get_journal_info()
    #save_dataframe_to_html(journals)
    #save_all_toc_to_xml(journals)
    generate_html_from_xml()