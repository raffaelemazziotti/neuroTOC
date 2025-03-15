import requests
import xml.etree.ElementTree as ET
from gsheet_reader import get_journal_info
from datetime import datetime
import time
from bs4 import BeautifulSoup


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


# Main execution
journals = get_journal_info()
save_all_toc_to_xml(journals)
