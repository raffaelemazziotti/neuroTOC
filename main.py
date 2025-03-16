from build_html import *


# Main execution
journals = get_journal_info()
save_dataframe_to_html(journals)
save_all_toc_to_xml(journals)
generate_html_from_xml()