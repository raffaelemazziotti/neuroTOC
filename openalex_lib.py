import time
import requests

from pubmed_lib import normalize_doi

BATCH = 50


def _abstract_from_index(inverted_index):
    """OpenAlex stores abstracts as {word: [positions]}; rebuild the text."""
    if not inverted_index:
        return ""
    words = {}
    for word, positions in inverted_index.items():
        for p in positions:
            words[p] = word
    return " ".join(words[p] for p in sorted(words))


def get_openalex_records(dois):
    """Look up DOIs in OpenAlex. Returns {normalized doi: {'type': ..., 'abstract': ...}}.
    Used for articles PubMed has not indexed yet (OpenAlex picks up new CrossRef records within days)."""
    wanted = sorted({normalize_doi(d) for d in dois if d and d != "N/A"})
    records = {}
    for i in range(0, len(wanted), BATCH):
        batch = wanted[i:i + BATCH]
        for attempt in range(3):
            try:
                r = requests.get("https://api.openalex.org/works", timeout=60, params={
                    "filter": "doi:" + "|".join(batch),
                    "per-page": BATCH,
                    "select": "doi,type,abstract_inverted_index",
                })
                if r.status_code == 200:
                    break
            except requests.RequestException:
                pass
            time.sleep(2 * (attempt + 1))
        else:
            print(f"OpenAlex lookup failed for batch {i // BATCH + 1}")
            continue
        for work in r.json().get("results", []):
            if work.get("doi"):
                records[normalize_doi(work["doi"])] = {
                    "type": work.get("type") or "",
                    "abstract": _abstract_from_index(work.get("abstract_inverted_index")),
                }
        time.sleep(0.1)
    print(f"OpenAlex: found {len(records)} of {len(wanted)} articles")
    return records
