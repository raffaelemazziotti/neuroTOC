import requests
from datetime import datetime
import time
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import pandas as pd
import re


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
        soup = BeautifulSoup(raw_abstract, 'html.parser')
        return soup.get_text(strip=True)
    return "No preview available"


def get_journal_toc(issn, num_articles=30):
    """Fetch the TOC for a given ISSN from CrossRef."""
    url = f"https://api.crossref.org/journals/{issn}/works?sort=published&order=desc&rows={num_articles}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        articles = data.get('message', {}).get('items', [])
        toc = []
        for article in articles:
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

            toc.append({
                'title': title,
                'journal': journal,
                'pub_date': pub_date,
                'abstract': abstract,
                'authors': authors,
                'type': art_type,
                'doi': f'{doi}'
            })
        return toc
    else:
        print(f"Error fetching ISSN {issn}: {response.status_code}")
        return []


def save_all_toc_to_xml(journals, filename="all_journals_toc.xml"):
    """Save all TOC data into an XML file."""
    root = ET.Element("JournalsTOC", updated=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

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


def generate_html_from_xml(xml_file="all_journals_toc.xml", html_file="index.html"):
    """Generate the final HTML file with:
       - All Journals (accordion)
       - Individual Journal sections (dropdown)
       - Searching (data-title, data-abstract, data-authors)
       - Clicking anywhere toggles abstract, except on Read More link
       - Home button pinned bottom-center
       - localStorage used in script.js
    """
    import xml.etree.ElementTree as ET
    tree = ET.parse(xml_file)
    root = tree.getroot()
    update_date = root.attrib.get('updated', 'N/A')

    dropdown_options = '<option value="All_Journals">All Journals</option>'
    all_journals_html = "<h2>All Journals</h2>"
    individual_journals_html = ""

    for journal in root.findall('Journal'):
        journal_name = journal.get('name')
        journal_id = journal_name.replace(" ", "_").lower()
        dropdown_options += f'<option value="{journal_id}">{journal_name}</option>'

        articles_html = ""
        for article in journal.findall('Article'):
            title_node = article.find('Title')
            doi_node = article.find('DOI')
            authors_node = article.find('Authors')
            pub_date_node = article.find('PublicationDate')
            type_node = article.find('Type')
            abstract_node = article.find('Abstract')

            title = title_node.text if title_node is not None else "N/A"
            doi = doi_node.text if doi_node is not None else "#"
            authors = authors_node.text if authors_node is not None else "N/A"
            pub_date = pub_date_node.text if pub_date_node is not None else "N/A"
            art_type = type_node.text if type_node is not None else "N/A"
            abstract = abstract_node.text if abstract_node is not None else "No preview available"

            # data- attrs for searching
            articles_html += f"""
<li class="article-item"
    data-title="{title.lower()}"
    data-abstract="{abstract.lower()}"
    data-authors="{authors.lower() if authors else None}">

  <strong>{title}</strong><br>
  <em>Authors:</em> {authors}<br>
  <em>Published:</em> {pub_date} ({art_type})<br>

  <!-- 'Read More' link (works on click) -->
  <a href="{doi}" target="_blank" class="read-more-link">Read More</a>

  <!-- Hidden abstract initially -->
  <p class="abstract" style="display:none;">
    {abstract}
  </p>
</li>
"""

        accordion_id = "acc_" + journal_id
        all_journals_html += f"""
<div class="accordion-item">
  <h3 class="journal-header" data-toggle="{accordion_id}">
    <span class="toggle-icon">-</span> {journal_name}
  </h3>
  <ul id="{accordion_id}" style="display: block;">
    {articles_html}
  </ul>
</div>
"""

        individual_journals_html += f'''
<div id="{journal_id}" class="journal-content" style="display:none;">
  <ul>{articles_html}</ul>
</div>
'''

    html_content = f"""
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link 
    rel="stylesheet" 
    href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css"
  />
  <link rel="icon" type="image/svg+xml" href="logo.svg">
  <title>NeuroTOC</title>
  <link rel="stylesheet" type="text/css" href="style.css">
  <script src="script.js" defer></script>
</head>
<body data-updated="{update_date}">
  <h1>NeuroTOC</h1>
  <h2 style="text-align: center;">Updated: {update_date.split(' ')[0]}</h2>

  <input type="text" id="searchInput" placeholder="Search for articles...">

  <div class="custom-select">
    <select id="journalSelect">
      {dropdown_options}
    </select>
  </div>

  <div id="All_Journals" class="journal-content" style="display:block;">
    {all_journals_html}
  </div>

  {individual_journals_html}

  <!-- Centered home button at bottom -->
  <button onclick="scrollToTop()" class="home-button">
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