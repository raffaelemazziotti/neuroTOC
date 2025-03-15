import requests
from datetime import datetime
import time
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import pandas as pd
import re

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
        print()
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
    tree = ET.parse(xml_file)
    root = tree.getroot()
    update_date = root.attrib.get('updated', 'N/A')

    html_content = [
        '<html>',
        '<head>',
        '<title>Journal TOC</title>',
        '<link rel="stylesheet" type="text/css" href="style.css">',
        '<script>',
        """
        document.addEventListener("DOMContentLoaded", () => {
            const tooltip = document.getElementById("tooltip");

            document.body.addEventListener("mouseover", function (e) {
                if (e.target.classList.contains("article-link")) {
                    tooltip.innerHTML = e.target.getAttribute("data-tooltip");
                    tooltip.style.display = "block";
                    tooltip.style.top = (e.pageY + 10) + "px";
                    tooltip.style.left = (e.pageX + 10) + "px";
                }
            });

            document.body.addEventListener("mousemove", function (e) {
                if (tooltip.style.display === "block") {
                    tooltip.style.top = (e.pageY + 10) + "px";
                    tooltip.style.left = (e.pageX + 10) + "px";
                }
            });

            document.body.addEventListener("mouseout", function (e) {
                if (e.target.classList.contains("article-link")) {
                    tooltip.style.display = "none";
                }
            });
        });

        function searchArticles() {
            const input = document.getElementById('searchInput');
            const filter = input.value.toLowerCase();
            const articles = document.getElementsByClassName('article-item');

            for (let i = 0; i < articles.length; i++) {
                const text = articles[i].textContent || articles[i].innerText;
                articles[i].style.display = text.toLowerCase().includes(filter) ? '' : 'none';
            }
        }

        function openTab(evt, tabName) {
            let i, tabcontent, tablinks;
            tabcontent = document.getElementsByClassName("tabcontent");
            for (i = 0; i < tabcontent.length; i++) {
                tabcontent[i].style.display = "none";
            }
            tablinks = document.getElementsByClassName("tablinks");
            for (i = 0; i < tablinks.length; i++) {
                tablinks[i].className = tablinks[i].className.replace(" active", "");
            }
            document.getElementById(tabName).style.display = "block";
            evt.currentTarget.className += " active";
        }
        """,
        '</script>',
        '</head>',
        '<body>',
        '<div id="tooltip" class="tooltip"></div>',
        f'<h1>Table of Contents (Updated: {update_date})</h1>',
        '<input type="text" id="searchInput" onkeyup="searchArticles()" placeholder="Search for articles...">',
        '<div class="tab">'
    ]

    html_content.append('<button class="tablinks" onclick="openTab(event, \'All_Journals\')">All Journals</button>')

    for journal in root.findall('Journal'):
        journal_name = journal.get('name').replace(" ", "_")
        html_content.append(f'<button class="tablinks" onclick="openTab(event, \'{journal_name}\')">{journal.get("name")}</button>')

    html_content.append('</div>')

    # All Journals Tab with Journal Grouping
    html_content.append('<div id="All_Journals" class="tabcontent" style="display:block;">')
    html_content.append('<h2>All Journals</h2>')

    for journal in root.findall('Journal'):
        journal_name = journal.get('name')
        html_content.append(f'<h3>{journal_name}</h3>')

        articles = journal.findall('Article')
        if articles:
            html_content.append('<ul>')
            for article in articles:
                title = article.find('Title').text
                doi = article.find('DOI').text
                abstract = article.find('Abstract').text or "No preview available"
                abstract = replace_ignore_case(abstract, 'abstract', 'Abstract: ')
                preview = abstract[:500] + "..." if len(abstract) > 500 else abstract

                html_content.append(f"<li class='article-item'><a href='{doi}' target='_blank' class='article-link' data-tooltip='{preview}'>{title}</a></li>")
            html_content.append('</ul>')
        else:
            html_content.append('<p>No articles found.</p>')

    html_content.append('</div>')

    # Individual Journal Tabs
    for journal in root.findall('Journal'):
        journal_name = journal.get('name')
        journal_id = journal_name.replace(" ", "_")
        updated_date = journal.get('updated')

        html_content.append(f'<div id="{journal_id}" class="tabcontent">')
        html_content.append(f'<h2>{journal_name}</h2>')
        html_content.append(f'<p>Last Updated: {updated_date}</p>')
        articles = journal.findall('Article')

        if articles:
            html_content.append('<ul>')
            for article in articles:
                title = article.find('Title').text
                pub_date = article.find('PublicationDate').text
                authors = article.find('Authors').text
                doi = article.find('DOI').text
                abstract = article.find('Abstract').text or "No preview available"
                preview = abstract[:500] + "..." if len(abstract) > 500 else abstract

                html_content.append(f"<li class='article-item'><strong>{title}</strong> "
                                    f"({pub_date})<br>"
                                    f"Authors: {authors}<br>"
                                    f"<a href='{doi}' target='_blank' class='article-link' data-tooltip='{preview}'>Read More</a></li>")
            html_content.append('</ul>')
        else:
            html_content.append('<p>No articles found.</p>')

        html_content.append('</div>')

    html_content.append('</body></html>')

    with open(html_file, 'w', encoding='utf-8') as file:
        file.write('\n'.join(html_content))

    print(f"HTML file saved to {html_file}")



# Main execution
#journals = get_journal_info()
#save_all_toc_to_xml(journals)
generate_html_from_xml()