import requests
from datetime import datetime
import time
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import pandas as pd
import re

def save_dataframe_to_html(df: pd.DataFrame, output_file: str = "journals_list.html"):
    """Save the given DataFrame as a styled HTML table."""
    html_table = df.to_html(index=False, border=0, classes="dataframe", justify="center")

    # Write the HTML content
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
            <h2>📚 Journal List</h2>
            {html_table}
        </body>
        </html>
        """)
    print(f"HTML table saved to '{output_file}'")

def get_journal_info():
    # Replace with your Google Sheets URL and export it as CSV
    sheet_id = "1HIBPpTTpuznVZdr5Kf-hd6vp6iWYJQvjasnrmKv6p8w"
    sheet_name = "Foglio1"  # Adjust if the sheet name is different
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"

    # Read the sheet into a DataFrame
    df = pd.read_csv(url)

    return df

def clean_abstract(raw_abstract):
    if raw_abstract and raw_abstract != 'N/A':
        soup = BeautifulSoup(raw_abstract, 'html.parser')
        return soup.get_text(strip=True)
    return "No preview available"


def get_journal_toc(issn, num_articles=30):
    url = f"https://api.crossref.org/journals/{issn}/works?sort=published&order=desc&rows={num_articles}"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        articles = data.get('message', {}).get('items', [])
        toc = []
        for article in articles:
            title = article.get('title', ['N/A'])[0]
            doi = article.get('URL', 'N/A')
            authors = [f"{auth.get('family', 'N/A')} {auth.get('given', ['N/A'])[0]}." for auth in
                       article.get('author', [])]
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
                'authors': '; '.join(authors) if len(authors) <= 25 else '; '.join(authors[:25]),
                'type': art_type,
                'doi': f'{doi}'
            })
        return toc
    else:
        print(f"Error fetching ISSN {issn}: {response.status_code}")
        return []


def save_all_toc_to_xml(journals, filename="all_journals_toc.xml"):
    root = ET.Element("JournalsTOC", updated=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    for _, journal in journals.iterrows():
        print(f"Downloading TOC from: {journal['Journal Name']}")
        journal_elem = ET.SubElement(root, "Journal", name=journal['Journal Name'], issn=journal['ISSN'],
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


def replace_ignore_case(text, old, new):
    return re.sub(re.escape(old), new, text, flags=re.IGNORECASE)


def generate_html_from_xml(xml_file="all_journals_toc.xml", html_file="index.html"):
    import xml.etree.ElementTree as ET
    from datetime import datetime

    tree = ET.parse(xml_file)
    root = tree.getroot()
    update_date = root.attrib.get('updated', 'N/A')

    # Build the dropdown + HTML for "All Journals" and individual journals
    dropdown_options = '<option value="All_Journals">All Journals</option>'
    all_journals_html = "<h2>All Journals</h2>"
    individual_journals_html = ""

    # Loop over each Journal
    for journal in root.findall('Journal'):
        journal_name = journal.get('name')
        journal_id = journal_name.replace(" ", "_").lower()
        dropdown_options += f'<option value="{journal_id}">{journal_name}</option>'

        # Build article HTML
        articles_html = ""
        for article in journal.findall('Article'):
            title = article.find('Title').text if article.find('Title') is not None else "N/A"
            doi = article.find('DOI').text if article.find('DOI') is not None else "#"
            authors = article.find('Authors').text if article.find('Authors') is not None else "N/A"
            pub_date = article.find('PublicationDate').text if article.find('PublicationDate') is not None else "N/A"
            art_type = article.find('Type').text if article.find('Type') is not None else "N/A"
            abstract = article.find('Abstract').text if article.find('Abstract') is not None else "No preview available"

            articles_html += f"""
                <li class='article-item'
                    data-title='{title.lower()}'
                    data-abstract='{abstract.lower()}'
                    data-authors='{authors}'>
                    <strong>{title}</strong> <br>
                    <p></p>
                    <em>Authors:</em> {authors}<br>
                    <em>Published:</em> {pub_date} ({art_type})<br>
                    <a href='{doi}' target='_blank'>Read More</a><br>
                    <p>{abstract}</p>
                </li>
            """

        # Accordion for All Journals: open by default
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

        # Individual journal sections (hidden by default, toggled via dropdown)
        individual_journals_html += f'''
            <div id="{journal_id}" class="journal-content" style="display:none;">
                <ul>{articles_html}</ul>
            </div>
        '''

    # Final HTML content
    html_content = f"""
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Journal TOC</title>
        <link rel="stylesheet" type="text/css" href="style.css">
        <link 
            rel="stylesheet" 
        href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css"
            />
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

        <button onclick="scrollToTop()" class="home-button">
            <i class="fas fa-home"></i>
        </button>
    </body>
    </html>
    """

    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"HTML file saved to {html_file}")






# Main execution
#journals = get_journal_info()
#save_dataframe_to_html(journals)
#save_all_toc_to_xml(journals)
generate_html_from_xml()