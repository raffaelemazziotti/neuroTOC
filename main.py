import sys
from build_html import *


# Main execution
journals = get_journal_info()
save_dataframe_to_html(journals) # refresh and save the list of journals to check
save_all_toc_to_xml(journals)

# Fail loudly (and skip the commit) if the CrossRef download returned nothing
crossref_journals = ET.parse("all_journals_toc.xml").getroot().findall("Journal")[1:]
non_empty = sum(1 for j in crossref_journals if j.find("Article") is not None)
print(f"{non_empty}/{len(crossref_journals)} journals have articles")
if non_empty < len(crossref_journals) / 2:
    sys.exit("Too many empty journals, check the CrossRef errors above")

generate_html_from_xml()
