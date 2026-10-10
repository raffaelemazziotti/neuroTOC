import os
import time
import requests

from pubmed_lib import normalize_doi

BATCH = 50
# Without a key OpenAlex allows a small free daily budget per IP address, shared with everyone on that IP
# (GitHub's runners included); a free personal key has its own budget. https://openalex.org/settings/api
API_KEY = os.environ.get("OPENALEX_API_KEY")


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
    """Look up DOIs in OpenAlex. Returns {normalized doi: {'type', 'abstract', 'topic', 'keywords', 'topic_fields'}}.
    OpenAlex picks up new CrossRef records within days, so it covers articles PubMed has not indexed
    yet and preprints; topic and keywords are machine-assigned, only confident ones are kept."""
    wanted = sorted({normalize_doi(d) for d in dois if d and d != "N/A"})
    records = {}
    headers = {"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}
    for i in range(0, len(wanted), BATCH):
        batch = wanted[i:i + BATCH]
        r = None
        for attempt in range(3):
            try:
                r = requests.get("https://api.openalex.org/works", timeout=60, headers=headers, params={
                    "filter": "doi:" + "|".join(batch),
                    "per-page": BATCH,
                    "select": "doi,type,abstract_inverted_index,primary_topic,topics,keywords",
                })
                if r.status_code in (200, 429):
                    break
            except requests.RequestException:
                pass
            time.sleep(2 * (attempt + 1))
        if r is not None and r.status_code == 429:
            # daily budget used up: retrying will not help until it resets
            print(f"OpenAlex daily budget exhausted ({'with' if API_KEY else 'without'} API key): {r.text[:200]}")
            break
        if r is None or r.status_code != 200:
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
                    # top 3 topics as 'field > subfield > topic', used to tell neuroscience papers apart
                    "topic_fields": [
                        f"{t['field']['display_name']} > {t['subfield']['display_name']} > {t['display_name']}"
                        for t in (work.get("topics") or [])[:3]
                    ],
                }
        time.sleep(0.1)
    print(f"OpenAlex: found {len(records)} of {len(wanted)} articles")
    return records
