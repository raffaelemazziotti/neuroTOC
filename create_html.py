import xml.etree.ElementTree as ET

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

    # All Journals Tab
    html_content.append('<div id="All_Journals" class="tabcontent" style="display:block;">')
    html_content.append('<h2>All Journals</h2>')

    for journal in root.findall('Journal'):
        for article in journal.findall('Article'):
            title = article.find('Title').text
            doi = article.find('DOI').text
            abstract = article.find('Abstract').text or "No preview available"
            preview = abstract[:200] + "..." if len(abstract) > 200 else abstract
            html_content.append(f"<p class='article-item'><a href='{doi}' target='_blank' class='article-link' data-tooltip='{preview}'>{title}</a></p>")

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
                preview = abstract[:200] + "..." if len(abstract) > 200 else abstract

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
generate_html_from_xml()
