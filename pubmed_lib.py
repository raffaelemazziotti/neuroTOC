import os
import time
import requests
import xml.etree.ElementTree as ET

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
# Without an API key NCBI allows 3 requests/second; with NCBI_API_KEY, 10/second
API_KEY = os.environ.get("NCBI_API_KEY")
DELAY = 0.12 if API_KEY else 0.4
BATCH = 100


def _post(endpoint, data, retries=4):
    """POST to E-utilities, retrying on rate limits / server errors. Returns None on failure."""
    data = {**data, "tool": "neuroTOC"}
    if API_KEY:
        data["api_key"] = API_KEY
    for attempt in range(retries):
        try:
            r = requests.post(f"{EUTILS}/{endpoint}", data=data, timeout=60)
            if r.status_code == 200:
                time.sleep(DELAY)
                return r
        except requests.RequestException:
            pass
        time.sleep(2 * (attempt + 1))
    return None


def normalize_doi(doi):
    doi = (doi or "").strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "http://dx.doi.org/", "https://dx.doi.org/"):
        if doi.startswith(prefix):
            return doi[len(prefix):]
    return doi


def _parse_article(art):
    """Extract publication types, abstract, MeSH terms and author keywords from a PubmedArticle."""
    mc = art.find("MedlineCitation")
    # structured abstracts come in labelled sections (BACKGROUND, METHODS, ...)
    sections = []
    for t in mc.iter("AbstractText"):
        text = " ".join("".join(t.itertext()).split())
        label = t.get("Label")
        if text:
            sections.append(f"{label.capitalize()}: {text}" if label else text)
    abstract = " ".join(sections)
    mesh = []
    for heading in mc.iter("MeshHeading"):
        name = heading.find("DescriptorName")
        major = name.get("MajorTopicYN") == "Y" or any(q.get("MajorTopicYN") == "Y" for q in heading.findall("QualifierName"))
        mesh.append((name.text, major))
    return {
        "types": [t.text for t in mc.iter("PublicationType") if t.text],
        "abstract": abstract,
        "mesh_major": [m for m, major in mesh if major],
        "keywords": [k.text.strip() for k in mc.iter("Keyword") if k.text and k.text.strip()],
    }


def get_pubmed_records(dois):
    """Look up DOIs in PubMed. Returns {normalized doi: record} for the DOIs found.
    Articles not (yet) indexed in PubMed are simply missing from the result."""
    wanted = sorted({normalize_doi(d) for d in dois if d and d != "N/A"})
    records = {}
    for i in range(0, len(wanted), BATCH):
        batch = wanted[i:i + BATCH]
        term = " OR ".join(f'"{d}"[doi]' for d in batch)
        r = _post("esearch.fcgi", {"db": "pubmed", "term": term, "retmax": BATCH * 2, "retmode": "json"})
        if r is None:
            print(f"PubMed search failed for batch {i // BATCH + 1}")
            continue
        try:
            ids = r.json()["esearchresult"]["idlist"]
        except (ValueError, KeyError):
            continue
        if not ids:
            continue
        r = _post("efetch.fcgi", {"db": "pubmed", "id": ",".join(ids), "retmode": "xml"})
        if r is None:
            print(f"PubMed fetch failed for batch {i // BATCH + 1}")
            continue
        try:
            root = ET.fromstring(r.content)
        except ET.ParseError:
            continue
        for art in root.iter("PubmedArticle"):
            # only the article's own ids, not the DOIs in its reference list
            id_list = art.find("PubmedData/ArticleIdList")
            if id_list is None:
                continue
            record = _parse_article(art)
            for article_id in id_list:
                if article_id.get("IdType") == "doi" and article_id.text:
                    records[normalize_doi(article_id.text)] = record
    print(f"PubMed: found {len(records)} of {len(wanted)} articles")
    return records


if __name__ == "__main__":
    recs = get_pubmed_records(["10.1016/j.neuron.2026.08.032", "10.1038/s41593-026-02133-6"])
    for doi, rec in recs.items():
        print(doi, rec["types"], rec["mesh_major"][:5], rec["keywords"][:5], len(rec["abstract"]))
