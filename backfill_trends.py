"""Rebuild the history of the trends page for earlier periods.

Downloads the 30 days of articles (and 7 days of preprints) before each date, exactly like the weekly job,
and saves only trends/<date>.json. The site's own files (index.html, all_journals_toc.xml, ...) are not touched.

    python backfill_trends.py 2026-09-10 2026-08-11 2026-07-12
"""
import os
import sys
import tempfile
from datetime import datetime

from build_html import get_journal_info, save_all_toc_to_xml, generate_html_from_xml
from trends_lib import TRENDS_DIR

if __name__ == "__main__":
    dates = sys.argv[1:]
    if not dates:
        sys.exit(__doc__)
    journals = get_journal_info()
    with tempfile.TemporaryDirectory() as tmp:
        for d in dates:
            end_date = datetime.strptime(d, "%Y-%m-%d")
            if os.path.exists(os.path.join(TRENDS_DIR, f"{d}.json")):
                print(f"{d}: snapshot already exists, skipping")
                continue
            print(f"=== {d}: downloading the 30 days before")
            xml_file = os.path.join(tmp, f"{d}.xml")
            save_all_toc_to_xml(journals, xml_file, end_date=end_date)
            generate_html_from_xml(xml_file, os.path.join(tmp, "index.html"), os.path.join(tmp, "trends.html"))
            print(f"=== {d}: saved {TRENDS_DIR}/{d}.json")
