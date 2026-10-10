"""Trends page: what this month's articles are about (topics, keywords, organisms, methods, ...).

Counts are numbers of articles. Every run also saves a small snapshot in trends/<date>.json;
once snapshots from about a month earlier exist, the page compares against them ("Rising / falling").
"""
import glob
import html
import json
import math
import os
import re
from datetime import datetime
from urllib.parse import quote

TRENDS_DIR = "trends"
CATEGORIES_FILE = "trend_categories.json"
# keywords that describe nearly every article and say nothing about a trend
GENERIC_KEYWORDS = {
    "brain", "neuron", "human", "animal", "mouse", "mice", "rat", "male", "female", "adult", "aged",
    "middle aged", "child", "adolescent", "young adult", "infant", "aged, 80 and over", "rodent",
    "neuroscience", "cell", "disease", "animals, genetically modified", "mice, inbred c57bl", "disease model, animal",
    "rats, sprague-dawley", "mice, knockout", "cell line", "cells, cultured", "risk factor", "prognosis", "treatment",
}
# rising / falling: compare with snapshots at least this old (the article window is 30 days,
# so younger snapshots mostly contain the same articles)
BASELINE_MIN_DAYS, BASELINE_MAX_DAYS = 25, 120
MIN_COUNT_FOR_CHANGE = 8


def keyword_key(keyword):
    """Merge spelling variants: "Alzheimer Disease" / "Alzheimer's disease" -> "alzheimer", "Neurons" -> "neuron".
    The key is also a valid search query, since the site's search matches substrings."""
    k = keyword.lower().replace("’", "'").replace("'s", "")
    k = re.sub(r"\bdiseases?\b", " ", k)
    words = []
    for w in re.split(r"\s+", k.strip(" .,;:-")):
        if len(w) > 4 and w.endswith("s") and not w.endswith(("ss", "is", "us")):
            w = w[:-1]
        words.append(w)
    return " ".join(w for w in words if w)


def load_categories(filename=CATEGORIES_FILE):
    with open(filename, encoding="utf-8") as f:
        data = json.load(f)
    return {group: {label: re.compile(rx, re.I) for label, rx in entries.items()}
            for group, entries in data.items() if not group.startswith("_")}


def search_term(pattern):
    """A plain search query for a category, when its first alternative is plain text (e.g. 'hippocamp')."""
    first = pattern.pattern.split("|")[0].replace("\\b", "").replace("s?", "")
    return first if re.fullmatch(r"[a-z][a-z' -]*", first) else None


def compute_stats(articles, date):
    """articles: dicts with title, abstract, topic, tags, journal, kind, has_abstract (the articles shown on the page)."""
    categories = load_categories()
    generic = {keyword_key(k) for k in GENERIC_KEYWORDS}
    topics, keywords, labels = {}, {}, {}
    category_counts = {group: {label: 0 for label in entries} for group, entries in categories.items()}
    for a in articles:
        if a["topic"]:
            topics[a["topic"]] = topics.get(a["topic"], 0) + 1
        for key in {keyword_key(t) for t in a["tags"]} - generic - {""}:
            keywords[key] = keywords.get(key, 0) + 1
        for tag in a["tags"]:
            labels.setdefault(keyword_key(tag), {}).setdefault(tag, 0)
            labels[keyword_key(tag)][tag] += 1
        text = f"{a['title']} {a['abstract']}"
        for group, entries in categories.items():
            for label, rx in entries.items():
                if rx.search(text):
                    category_counts[group][label] += 1
    top_keywords = dict(sorted(keywords.items(), key=lambda kv: -kv[1])[:300])
    return {
        "date": date,
        "n_articles": len(articles),
        "n_sources": len({a["journal"] for a in articles}),
        "n_reviews": sum(a["kind"] in ("review", "meta-analysis") for a in articles),
        "n_preprints": sum(a["journal"] == "Biorxiv" for a in articles),
        "n_with_abstract": sum(a["has_abstract"] for a in articles),
        "topics": dict(sorted(topics.items(), key=lambda kv: -kv[1])[:100]),
        "keywords": top_keywords,
        # the most common spelling of each merged keyword, for display
        "keyword_labels": {k: max(labels[k].items(), key=lambda kv: kv[1])[0] for k in top_keywords},
        "categories": category_counts,
    }


def save_snapshot(stats):
    os.makedirs(TRENDS_DIR, exist_ok=True)
    with open(os.path.join(TRENDS_DIR, f"{stats['date']}.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=1)


def load_baseline(date):
    """Snapshots 25-120 days older than `date`."""
    now = datetime.strptime(date, "%Y-%m-%d")
    snapshots, oldest = [], None
    for path in sorted(glob.glob(os.path.join(TRENDS_DIR, "*.json"))):
        try:
            d = datetime.strptime(os.path.basename(path)[:-5], "%Y-%m-%d")
        except ValueError:
            continue
        oldest = oldest or d
        if BASELINE_MIN_DAYS <= (now - d).days <= BASELINE_MAX_DAYS:
            with open(path, encoding="utf-8") as f:
                snapshots.append(json.load(f))
    return snapshots, oldest


def compute_changes(stats, baseline):
    """Share of articles now vs the average share in the baseline snapshots, for keywords, topics and categories."""
    def items(s):
        out = {("keyword", k): v for k, v in s["keywords"].items()}
        out.update({("topic", k): v for k, v in s["topics"].items()})
        for group, entries in s["categories"].items():
            out.update({(group, k): v for k, v in entries.items()})
        return out

    now = items(stats)
    past = [(items(b), b["n_articles"]) for b in baseline]
    changes = []
    for key in set(now) | {k for p, _ in past for k in p}:
        count = now.get(key, 0)
        past_count = sum(p.get(key, 0) for p, _ in past) / len(past)
        if max(count, past_count) < MIN_COUNT_FOR_CHANGE:
            continue
        share = count / stats["n_articles"]
        past_share = sum(p.get(key, 0) / n for p, n in past) / len(past)
        # +1 smoothing so a jump from 0 to 8 articles is not "infinitely" rising
        ratio = (share * stats["n_articles"] + 1) / (past_share * stats["n_articles"] + 1)
        changes.append((math.log(ratio), key, count, past_share))
    changes.sort()
    falling = [c for c in changes if c[0] < 0][:8]
    rising = [c for c in reversed(changes) if c[0] > 0][:8]
    return rising, falling


def _bar_list(rows, total, link_fn=None):
    """rows: [(label, count)] -> horizontal bars, value written at the tip of each bar."""
    if not rows:
        return '<p class="viz-empty">No data yet.</p>'
    top = max(count for _, count in rows) or 1
    out = '<ul class="bar-list">'
    for label, count in rows:
        share = count / total if total else 0
        href = link_fn(label) if link_fn else None
        name = html.escape(label)
        name_html = f'<a href="{html.escape(href)}">{name}</a>' if href else name
        out += (
            f'<li class="bar-row" title="{name}: {count} articles ({share:.1%})">'
            f'<span class="bar-label">{name_html}</span>'
            f'<span class="bar-track"><span class="bar" style="width:{max(count / top * 100, 1):.1f}%"></span></span>'
            f'<span class="bar-value">{count}<span class="bar-share"> · {share:.0%}</span></span></li>'
        )
    return out + "</ul>"


def _change_list(changes, stats, direction):
    if not changes:
        return '<p class="viz-empty">Nothing stands out.</p>'
    biggest = max(abs(c[0]) for c in changes) or 1
    out = f'<ul class="bar-list change-list {direction}">'
    for log_ratio, (kind, key), count, past_share in changes:
        label = stats["keyword_labels"].get(key, key) if kind == "keyword" else key
        pct = (math.exp(log_ratio) - 1) * 100
        kind_label = "" if kind == "keyword" else f'<span class="change-kind">{html.escape(kind)}</span>'
        out += (
            f'<li class="bar-row" title="{html.escape(label)}: {count} articles now, {past_share:.1%} of articles before">'
            f'<span class="bar-label">{html.escape(label)}{kind_label}</span>'
            f'<span class="bar-track"><span class="bar" style="width:{abs(log_ratio) / biggest * 100:.1f}%"></span></span>'
            f'<span class="bar-value">{pct:+.0f}%</span></li>'
        )
    return out + "</ul>"


def _render_view(view_id, stats, rising, falling, history_since, journal=None):
    """One view of the page (all articles, or preprints only). `journal` restricts the search links."""
    n = stats["n_articles"]
    preprints = view_id == "preprints"

    def search(q):
        return f"index.html?q={quote(q)}" + (f"&journal={journal}" if journal else "")

    categories = load_categories()
    if preprints:
        tiles = [
            ("Preprints", f"{n:,}"),
            ("Period", "last 7 days"),
            ("With abstract", f"{stats['n_with_abstract'] / n:.0%}" if n else "–"),
        ]
        intro = (f"What the {n:,} neuroscience preprints posted on bioRxiv in the last 7 days are about: the newest work, "
                 "before peer review. Counts are numbers of preprints; percentages are shares of all preprints.")
    else:
        tiles = [
            ("Articles", f"{n:,}"),
            ("Journals + bioRxiv", f"{stats['n_sources']}"),
            ("Preprints", f"{stats['n_preprints']:,}"),
            ("Reviews", f"{stats['n_reviews']:,}"),
            ("With abstract", f"{stats['n_with_abstract'] / n:.0%}" if n else "–"),
        ]
        intro = (f"What the {n:,} articles published in the last 30 days are about. Counts are numbers of articles; "
                 "percentages are shares of all articles.")
    keyword_source = ("OpenAlex keywords (preprints are not in PubMed)" if preprints
                      else "MeSH terms and author keywords from PubMed, or OpenAlex keywords")
    tiles_html = "".join(
        f'<div class="stat-tile"><span class="stat-label">{label}</span><span class="stat-value">{value}</span></div>'
        for label, value in tiles
    )

    chips = "".join(
        f'<a class="chip" href="{html.escape(search(key))}">{html.escape(stats["keyword_labels"].get(key, key))}'
        f'<span class="chip-count">{count}</span></a>'
        for key, count in list(stats["keywords"].items())[:40]
    )

    cards = [("Research topics", "Main OpenAlex topic of each article",
              _bar_list(list(stats["topics"].items())[:12], n, link_fn=lambda t: search(t.lower())))]
    for group, counts in stats["categories"].items():
        rows = sorted(((label, c) for label, c in counts.items() if c), key=lambda r: -r[1])
        patterns = categories.get(group, {})
        cards.append((group, "Mentioned in title or abstract",
                      _bar_list(rows, n, link_fn=lambda label, p=patterns: search(search_term(p[label])) if label in p and search_term(p[label]) else None)))
    cards_html = "".join(
        f'<section class="viz-card"><h2>{html.escape(title)}</h2><p class="viz-sub">{html.escape(sub)}</p>{body}</section>'
        for title, sub, body in cards
    )

    if rising or falling:
        changes_html = (
            '<div class="change-grid">'
            f'<div><h3>Rising</h3>{_change_list(rising, stats, "up")}</div>'
            f'<div><h3>Falling</h3>{_change_list(falling, stats, "down")}</div>'
            '</div>'
        )
    else:
        since = history_since.strftime("%d %b %Y") if history_since else stats["date"]
        changes_html = (
            f'<p class="viz-empty">Collecting history since {html.escape(since)}. Each weekly update saves a snapshot; '
            'once there is one from about a month earlier, this section shows which keywords, topics, methods and '
            'disorders are appearing more or less often than before.</p>'
        )

    return f"""
    <div class="trends-view" id="view-{view_id}" role="tabpanel" aria-labelledby="tab-{view_id}"{' hidden' if preprints else ''}>
    <p class="trends-intro">{intro} Click a keyword or a bar label to see the matching {'preprints' if preprints else 'articles'}.</p>

    <div class="stat-row">{tiles_html}</div>

    <section class="viz-card viz-wide">
      <h2>Most frequent keywords</h2>
      <p class="viz-sub">{keyword_source}; spelling variants merged</p>
      <div class="chips">{chips or '<p class="viz-empty">No keywords yet.</p>'}</div>
    </section>

    <section class="viz-card viz-wide">
      <h2>Rising and falling</h2>
      <p class="viz-sub">Share of {'preprints' if preprints else 'articles'} now compared with about a month earlier</p>
      {changes_html}
    </section>

    <div class="viz-grid">{cards_html}</div>
    </div>
"""


def render_page(views, date, html_file="trends.html"):
    """views: [(view id, switch label, page heading, view html)]; the first one is shown by default."""
    switch = "".join(
        f'<button type="button" role="tab" class="nav-pill{" active" if i == 0 else ""}" id="tab-{view_id}" '
        f'data-view="{view_id}" data-title="{html.escape(heading)}" aria-controls="view-{view_id}" '
        f'aria-selected="{"true" if i == 0 else "false"}">{html.escape(label)}</button>'
        for i, (view_id, label, heading, _) in enumerate(views)
    )
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="color-scheme" content="dark light">
  <link rel="icon" type="image/svg+xml" href="logo.svg">
  <title>NeuroTOC – Trends</title>
  <link rel="stylesheet" type="text/css" href="style.css">
</head>
<body class="trends-page">
  <header class="topbar">
    <div class="topbar-inner">
      <a class="brand" href="index.html" aria-label="NeuroTOC articles">
        <img src="logo.svg" alt="" width="32" height="32">
        <span class="brand-text">NeuroTOC</span>
      </a>
      <span class="updated">Updated {html.escape(date)}</span>
      <nav class="topnav"><a class="nav-pill" href="index.html">Articles</a><a class="nav-pill active" href="trends.html" aria-current="page">Trends</a></nav>
    </div>
  </header>

  <main class="trends-main">
    <div class="trends-head">
      <h1 class="trends-title" id="trendsTitle">{html.escape(views[0][2])}</h1>
      <div class="view-switch" role="tablist" aria-label="Which articles to analyse">{switch}</div>
    </div>
    {"".join(view_html for _, _, _, view_html in views)}

    <p class="trends-note">Large journals weigh more: Scientific Reports alone publishes about a quarter of the articles.
      Topics and keywords come from PubMed and OpenAlex and are partly machine-assigned. Categories are searched in titles
      and abstracts (list in <code>trend_categories.json</code>).</p>
  </main>
  <script>
    // switch between views; the choice is kept in the URL (trends.html#preprints) so it can be linked
    const tabs = document.querySelectorAll('.view-switch [data-view]');
    function showView(id) {{
      if (!document.getElementById('view-' + id)) return;
      tabs.forEach(tab => {{
        const on = tab.dataset.view === id;
        tab.classList.toggle('active', on);
        tab.setAttribute('aria-selected', on);
        document.getElementById('view-' + tab.dataset.view).hidden = !on;
        if (on) document.getElementById('trendsTitle').textContent = tab.dataset.title;
      }});
    }}
    tabs.forEach(tab => tab.addEventListener('click', () => {{
      showView(tab.dataset.view);
      history.replaceState(null, '', tab.dataset.view === tabs[0].dataset.view ? location.pathname : '#' + tab.dataset.view);
    }}));
    if (location.hash) showView(location.hash.slice(1));
    window.addEventListener('hashchange', () => showView(location.hash.slice(1) || tabs[0].dataset.view));
  </script>
</body>
</html>
"""
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"Trends page saved to {html_file}")


def build_trends(articles, date):
    """All articles, plus the bioRxiv preprints on their own (saved in the same snapshot)."""
    stats = compute_stats(articles, date)
    stats["preprints"] = compute_stats([a for a in articles if a["journal"] == "Biorxiv"], date)
    save_snapshot(stats)
    baseline, history_since = load_baseline(date)

    views = []
    for view_id, label, heading, view_stats, past, journal in [
        ("all", "All articles", "This month in neuroscience", stats, baseline, None),
        ("preprints", "Preprints only", "This week on bioRxiv", stats["preprints"],
         [b["preprints"] for b in baseline if "preprints" in b], "biorxiv"),
    ]:
        rising, falling = compute_changes(view_stats, past) if past else ([], [])
        views.append((view_id, label, heading, _render_view(view_id, view_stats, rising, falling, history_since, journal)))
    render_page(views, date)
