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


def get_openalex_records(dois, min_score=0.6):
    """Look up DOIs in OpenAlex. Returns {normalized doi: {'type', 'abstract', 'topic', 'keywords'}}.
    OpenAlex picks up new CrossRef records within days, so it covers articles PubMed has not indexed
    yet and preprints; topic and keywords are machine-assigned, only confident ones are kept."""
    wanted = sorted({normalize_doi(d) for d in dois if d and d != "N/A"})
    records = {}
    for i in range(0, len(wanted), BATCH):
        batch = wanted[i:i + BATCH]
        for attempt in range(3):
            try:
                r = requests.get("https://api.openalex.org/works", timeout=60, params={
                    "filter": "doi:" + "|".join(batch),
                    "per-page": BATCH,
                    "select": "doi,type,abstract_inverted_index,primary_topic,keywords",
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
                topic = work.get("primary_topic") or {}
                keywords = sorted(work.get("keywords") or [], key=lambda k: -k.get("score", 0))
                records[normalize_doi(work["doi"])] = {
                    "type": work.get("type") or "",
                    "abstract": _abstract_from_index(work.get("abstract_inverted_index")),
                    "topic": topic.get("display_name", "") if topic.get("score", 0) >= min_score else "",
                    "keywords": [k["display_name"] for k in keywords if k.get("score", 0) >= min_score],
                }
        time.sleep(0.1)
    print(f"OpenAlex: found {len(records)} of {len(wanted)} articles")
    return records
