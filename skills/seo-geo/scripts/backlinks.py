#!/usr/bin/env python3
"""backlinks.py - analyze a backlink export and find link gaps with competitors.

Usage: backlinks.py EXPORT.csv [EXPORT2.csv ...] --site example.com
                    [--brand "Example,Exemplo"] [--keywords "booking app,agendamento"]
                    [--competitor name=FILE.csv ...] [--check-targets] [--out DIR] [--json]

  EXPORT.csv        one or more backlink exports for the site: Google Search
                    Console (Links report), Bing Webmaster Tools, Ahrefs
                    (including the free Ahrefs Webmaster Tools), Semrush, Moz,
                    Majestic, or any CSV with source and target URL columns.
                    Referring-domain exports (one row per domain) work too.
  --site            the site's domain, to tell its own pages from others
  --brand           brand names, comma-separated, to classify anchors
  --keywords        money keywords, comma-separated, to spot exact-match anchors
  --competitor      NAME=FILE: a competitor's backlink or referring-domain
                    export; repeat for each competitor. Enables the link gap.
  --check-targets   fetch every linked page of the site and flag the ones that
                    are broken or redirect (links to reclaim)
  --out DIR         also write domains.csv, gap.csv and targets.csv there

What it reports:
  profile    links, referring domains, follow vs nofollow/ugc/sponsored, links
             lost, authority distribution when the export has a metric
  domains    the top referring domains, with link counts
  targets    which pages earn the links (home vs deep pages) and, with
             --check-targets, linked pages that 404 or redirect
  anchors    branded / URL / generic / exact-match / other / empty or image;
             a high share of exact-match anchors is a manipulation pattern
  patterns   site-wide links, one domain with a big share of all links,
             spam-looking domains (worth a look, rarely worth a disavow)
  gap        domains that link to two or more competitors and not to the site

Column names are matched loosely, so exports from different tools can be mixed.
Read-only. Python 3.8+ standard library; imports audit.py for --check-targets.
"""

import argparse
import collections
import csv
import io
import json
import os
import re
import sys
import urllib.parse

csv.field_size_limit(10_000_000)

# Header aliases, most specific first. Matched case-insensitively on the whole header.
COLS = {
    "source": ["referring page url", "source url", "source_url", "url from", "linking page", "source page",
               "referring url", "backlink url", "from url", "source", "url"],
    "target": ["target url", "target_url", "url to", "target page", "linked page", "destination url", "target",
               "to url"],
    "domain": ["referring domain", "referring domains", "domain", "linking site", "site", "root domain",
               "source domain"],
    "anchor": ["anchor text", "anchor", "linking text", "anchortext"],
    "authority": ["domain rating", "dr", "authority score", "page ascore", "domain authority", "da",
                  "trust flow", "citation flow", "domain ascore", "ascore", "ur"],
    "nofollow": ["nofollow", "rel", "link type", "type", "follow", "dofollow"],
    "sponsored": ["sponsored"],
    "ugc": ["ugc"],
    "lost": ["lost", "lost link", "lost date", "link lost", "deleted"],
    "links": ["links to target", "backlinks", "linking pages", "links", "external links", "incoming links"],
    "first_seen": ["first seen", "first_seen", "first indexed", "date found"],
    "sitewide": ["sitewide"],
}
GENERIC = {"click here", "here", "read more", "learn more", "more", "website", "site", "this", "link", "visit",
           "source", "home", "homepage", "this article", "this post", "this page", "official site", "see more",
           "clique aqui", "aqui", "saiba mais", "leia mais", "veja mais", "acesse", "site oficial", "neste link",
           "este link", "mais", "fonte", "confira"}
SPAMMY = re.compile(r"(casino|cassino|bet\d|slot|porn|xxx|viagra|cialis|loan|payday|replica|essay|seo-?link|"
                    r"backlink|linkfarm|directory\d|free-?links)", re.I)


def norm_header(h):
    return re.sub(r"\s+", " ", re.sub(r"[_\-\.]", " ", (h or "").strip().lower().lstrip("﻿")))


def map_columns(headers):
    found = {}
    normed = [norm_header(h) for h in headers]
    for key, aliases in COLS.items():
        for alias in aliases:
            a = norm_header(alias)
            for i, h in enumerate(normed):
                if h == a and i not in found.values():
                    found[key] = i
                    break
            if key in found:
                break
    return found


def read_rows(path):
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    sample = text[:5000]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(io.StringIO(text), dialect))
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not rows:
        return [], {}, []
    return rows[1:], map_columns(rows[0]), [norm_header(h) for h in rows[0]]


def host_of(url_or_domain):
    s = (url_or_domain or "").strip().lower()
    if not s:
        return ""
    if "://" not in s:
        s = "http://" + s
    h = urllib.parse.urlsplit(s).hostname or ""
    return h[4:] if h.startswith("www.") else h


def registrable(host):
    """Rough registrable domain: last two labels, or three for ccSLDs like .com.br / .co.uk."""
    parts = host.split(".")
    if len(parts) >= 3 and (parts[-2] in ("com", "co", "org", "net", "gov", "edu", "ac", "gob") or len(parts[-2]) <= 2):
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def truthy(v):
    return str(v).strip().lower() in ("true", "yes", "1", "y", "sim", "x")


def to_num(v):
    try:
        return float(str(v).replace(",", ".").strip())
    except ValueError:
        return None


def load(path, site):
    rows, cols, headers = read_rows(path)
    links = []
    rel_header = headers[cols["nofollow"]] if "nofollow" in cols else ""
    if not rows:
        return links, cols
    if "source" not in cols and "domain" not in cols:
        sys.exit(f"{path}: no source URL or domain column found in the header")

    def cell(r, key):
        i = cols.get(key)
        return r[i].strip() if i is not None and i < len(r) else ""

    for r in rows:
        src = cell(r, "source")
        dom = host_of(cell(r, "domain") or src)
        if not dom or dom == host_of(site) or registrable(dom) == registrable(host_of(site)):
            continue
        relraw = cell(r, "nofollow").lower()
        if rel_header == "nofollow":
            rel = "nofollow" if truthy(relraw) else "follow"
        elif rel_header == "dofollow":
            rel = "follow" if truthy(relraw) or not relraw else "nofollow"
        elif "dofollow" in relraw or relraw == "follow":
            rel = "follow"
        elif "nofollow" in relraw:
            rel = "nofollow"
        else:
            rel = "follow" if relraw in ("", "text", "image", "redirect", "frame", "href") else relraw
        if truthy(cell(r, "sponsored")) or "sponsored" in relraw:
            rel = "sponsored"
        elif truthy(cell(r, "ugc")) or "ugc" in relraw:
            rel = "ugc"
        lost_raw = cell(r, "lost")
        links.append({
            "source": src, "domain": dom, "rd": registrable(dom), "target": norm_target(cell(r, "target")),
            "anchor": cell(r, "anchor"), "has_anchor": "anchor" in cols, "url_level": "source" in cols, "authority": to_num(cell(r, "authority")), "rel": rel,
            "lost": bool(lost_raw) and lost_raw.lower() not in ("false", "0", "no", "-", ""),
            "count": int(to_num(cell(r, "links")) or 1) if "source" not in cols else 1,
            "sitewide": truthy(cell(r, "sitewide")), "first_seen": cell(r, "first_seen"),
        })
    return links, cols


def norm_target(t):
    """example.com/pricing for http(s)://(www.)example.com/pricing/ - so tools and hosts merge."""
    t = (t or "").strip().split("#")[0]
    if not t:
        return ""
    parts = urllib.parse.urlsplit(t if "://" in t else "http://" + t)
    host = (parts.hostname or "").lower()
    host = host[4:] if host.startswith("www.") else host
    path = parts.path.rstrip("/")
    return host + path + ("?" + parts.query if parts.query else "")


def classify_anchor(anchor, brands, keywords, site):
    a = " ".join(anchor.lower().split())
    if not a or a in ("[image]", "image", "img", "<img>", "-"):
        return "empty/image"
    if re.match(r"^(https?://|www\.)", a) or host_of(site) in a:
        return "url"
    if any(b and b in a for b in brands):
        return "branded"
    if a in GENERIC:
        return "generic"
    if any(k and k == a for k in keywords):
        return "exact-match"
    if any(k and k in a for k in keywords):
        return "partial-match"
    return "other"


def pct(n, d):
    return f"{100 * n / d:.0f}%" if d else "-"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("exports", nargs="+")
    ap.add_argument("--site", required=True)
    ap.add_argument("--brand", default="")
    ap.add_argument("--keywords", default="")
    ap.add_argument("--competitor", action="append", default=[])
    ap.add_argument("--check-targets", action="store_true")
    ap.add_argument("--out")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    site = host_of(args.site)
    brands = [b.strip().lower() for b in args.brand.split(",") if b.strip()] or [site.split(".")[0]]
    keywords = [k.strip().lower() for k in args.keywords.split(",") if k.strip()]

    links, mapped = [], {}
    for path in args.exports:
        got, cols = load(path, site)
        links += got
        mapped[path] = sorted(cols)
    if not links:
        sys.exit("no external links found in the exports (check --site and the columns)")

    has_urls = any(l["source"] for l in links)
    # Deduplicate the same source -> target across exports.
    seen, uniq = set(), []
    for l in links:
        key = (l["source"].lower().rstrip("/"), l["target"].lower().rstrip("/")) if has_urls and l["source"] else (l["rd"], l["target"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(l)
    links = uniq
    live = [l for l in links if not l["lost"]]

    by_rd = collections.defaultdict(lambda: {"links": 0, "follow": 0, "authority": None, "anchors": collections.Counter(),
                                             "targets": set(), "lost": 0, "url_links": 0, "agg_links": 0})
    for l in links:
        d = by_rd[l["rd"]]
        if l["lost"]:
            d["lost"] += 1
            continue
        if l["url_level"]:
            d["url_links"] += 1
            d["follow"] += 1 if l["rel"] == "follow" else 0
        else:
            d["agg_links"] = max(d["agg_links"], l["count"])
        d["links"] = max(d["url_links"], d["agg_links"])
        if l["authority"] is not None:
            d["authority"] = max(d["authority"] or 0, l["authority"])
        if l["anchor"]:
            d["anchors"][l["anchor"]] += 1
        if l["target"]:
            d["targets"].add(l["target"])
    live_rds = {k: v for k, v in by_rd.items() if v["links"]}
    total = sum(v["links"] for v in live_rds.values())
    url_live = [l for l in live if l["url_level"]]
    rels = collections.Counter(l["rel"] for l in url_live)
    rel_total = sum(rels.values())

    anchors = collections.Counter()
    anchor_examples = collections.defaultdict(collections.Counter)
    if any(l["has_anchor"] for l in live):
        for l in (l for l in live if l["has_anchor"]):
            c = classify_anchor(l["anchor"], brands, keywords, site)
            anchors[c] += 1
            anchor_examples[c][l["anchor"][:60]] += 1

    targets = collections.Counter()
    target_rds = collections.defaultdict(set)
    for l in live:
        if l["target"]:
            t = l["target"].split("#")[0]
            targets[t] += 1
            target_rds[t].add(l["rd"])
    home_like = sum(n for t, n in targets.items() if "/" not in t)

    findings = []
    if total and live_rds:
        top_rd, top = max(live_rds.items(), key=lambda kv: kv[1]["links"])
        if top["links"] / total > 0.3 and len(live_rds) > 5:
            findings.append(f"{top_rd} accounts for {pct(top['links'], total)} of all links (site-wide footer or blogroll?)")
    flagged = {l["rd"] for l in live if l["sitewide"]}
    sitewide = sorted(flagged | {rd for rd, v in live_rds.items() if v["links"] >= 50 and len(v["targets"]) <= 3})
    if sitewide:
        findings.append(f"{len(sitewide)} site-wide domain(s) (flagged by the tool, or 50+ links to 3 or fewer pages): "
                        f"{', '.join(sitewide[:8])}. Footer and blogroll links count little; fine if editorial, a risk if paid")
    em = anchors["exact-match"] + anchors["partial-match"]
    if anchors and keywords and em / sum(anchors.values()) > 0.2:
        findings.append(f"{pct(em, sum(anchors.values()))} of anchors contain money keywords: a pattern Google's link spam "
                        "systems look for; earned links are mostly branded or URL anchors")
    spam = sorted(rd for rd in live_rds if SPAMMY.search(rd))
    if spam:
        findings.append(f"{len(spam)} spam-looking domain(s): {', '.join(spam[:10])}. Google ignores most of these; "
                        "disavow only with a manual action or links someone bought")
    lost = sum(1 for l in links if l["lost"])
    if lost:
        findings.append(f"{lost} lost link(s) in the export; check the domains below for ones worth reclaiming")

    # Link gap
    gap = []
    comp_sets = {}
    for spec in args.competitor:
        if "=" not in spec:
            sys.exit(f"--competitor expects NAME=FILE, got {spec}")
        name, path = spec.split("=", 1)
        clinks, _ = load(path, name if "." in name else "")
        comp_sets[name] = {l["rd"]: l["authority"] for l in clinks if not l["lost"]}
    if comp_sets:
        ours = set(live_rds)
        counter = collections.defaultdict(list)
        for name, rds in comp_sets.items():
            for rd in rds:
                if rd not in ours and rd != registrable(site):
                    counter[rd].append(name)
        for rd, names in counter.items():
            if len(names) >= min(2, len(comp_sets)):
                auth = max((comp_sets[n].get(rd) or 0) for n in names)
                gap.append({"domain": rd, "competitors": sorted(names), "authority": auth or None})
        gap.sort(key=lambda g: (-len(g["competitors"]), -(g["authority"] or 0), g["domain"]))

    # Reclaim: linked pages that are broken or redirect
    reclaim = []
    if args.check_targets and targets:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from audit import fetch  # noqa: E402
        for t in sorted(targets, key=lambda t: -len(target_rds[t]))[:300]:
            url = "https://" + t if "/" in t else "https://" + t + "/"
            r = fetch(url, limit=20000)
            if r["status"] is None or r["status"] >= 400:
                reclaim.append({"target": t, "status": r["status"], "rds": len(target_rds[t]), "fix": "301 to the best live page"})
            elif r["chain"] and len(r["chain"]) > 1:
                reclaim.append({"target": t, "status": f"{len(r['chain'])} redirects", "rds": len(target_rds[t]),
                                "fix": "point the redirect straight at the final URL"})

    summary = {
        "exports": mapped, "links_live": total, "links_lost": lost, "referring_domains": len(live_rds),
        "follow_share": pct(rels["follow"], rel_total), "rel": dict(rels),
        "home_share": pct(home_like, sum(targets.values())) if targets else "-",
        "anchors": dict(anchors), "findings": findings,
    }
    top_domains = sorted(live_rds.items(), key=lambda kv: (-(kv[1]["authority"] or 0), -kv[1]["links"]))

    if args.out:
        os.makedirs(args.out, exist_ok=True)
        with open(os.path.join(args.out, "domains.csv"), "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["domain", "links", "follow_links", "authority", "pages_linked", "top_anchor", "lost_links"])
            for rd, v in top_domains:
                top_anchor = v["anchors"].most_common(1)[0][0] if v["anchors"] else ""
                w.writerow([rd, v["links"], v["follow"], v["authority"], len(v["targets"]), top_anchor, v["lost"]])
        with open(os.path.join(args.out, "targets.csv"), "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["target", "links", "referring_domains"])
            for t, n in targets.most_common():
                w.writerow([t, n, len(target_rds[t])])
        if gap:
            with open(os.path.join(args.out, "gap.csv"), "w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["domain", "links_to_competitors", "competitors", "authority"])
                for g in gap:
                    w.writerow([g["domain"], len(g["competitors"]), " ".join(g["competitors"]), g["authority"]])

    if args.json:
        print(json.dumps({"summary": summary, "top_domains": [{"domain": rd, "links": v["links"], "authority": v["authority"]}
                                                               for rd, v in top_domains[:100]],
                          "targets": targets.most_common(100), "gap": gap[:300], "reclaim": reclaim},
                         indent=2, ensure_ascii=False, default=list))
        return 0

    print(f"# Backlinks of {site}\n")
    for path, cols in mapped.items():
        print(f"read {path}: columns {', '.join(cols)}")
    print(f"\n## Profile\n  {total} live links from {len(live_rds)} referring domains"
          f"{f', {lost} lost' if lost else ''}")
    if rel_total:
        print(f"  rel (of {rel_total} URL-level links): " + ", ".join(f"{k} {pct(v, rel_total)}" for k, v in rels.most_common()))
    auths = sorted(v["authority"] for v in live_rds.values() if v["authority"] is not None)
    if auths:
        q = lambda p: auths[min(len(auths) - 1, int(p * len(auths)))]
        print(f"  authority of referring domains (tool's own metric): median {q(0.5):g}, top 10% above {q(0.9):g}")
    if targets:
        print(f"  {pct(home_like, sum(targets.values()))} of links point to the home page; {len(targets)} pages earn links")

    print("\n## Top referring domains")
    for rd, v in top_domains[:20]:
        a = f" auth {v['authority']:g}" if v["authority"] is not None else ""
        anchor = v["anchors"].most_common(1)[0][0][:40] if v["anchors"] else ""
        print(f"  {rd:<35} {v['links']:>5} link(s){a}  {anchor}")

    if targets:
        print("\n## Pages that earn links (by referring domains)")
        for t, _ in sorted(targets.items(), key=lambda kv: -len(target_rds[kv[0]]))[:15]:
            print(f"  {len(target_rds[t]):>4} domains  {t}")

    if anchors:
        n = sum(anchors.values())
        print("\n## Anchors")
        for k, v in anchors.most_common():
            ex = ", ".join(f'"{a}"' for a, _ in anchor_examples[k].most_common(3))
            print(f"  {k:<14} {pct(v, n):>4}  e.g. {ex}")

    if findings:
        print("\n## Patterns")
        for f in findings:
            print(f"  - {f}")

    if reclaim:
        print("\n## Links to reclaim (linked pages that are broken or redirect)")
        for r in reclaim[:30]:
            print(f"  {r['rds']:>4} domains  {r['target']}  ({r['status']}) -> {r['fix']}")
    elif args.check_targets:
        print("\n## Links to reclaim\n  none: every linked page answers 200 or redirects once")

    if comp_sets:
        print(f"\n## Link gap: domains linking to {'2+ of ' if len(comp_sets) > 1 else ''}"
              f"{', '.join(comp_sets)} but not to {site}")
        if not gap:
            print("  none found")
        for g in gap[:30]:
            a = f" auth {g['authority']:g}" if g["authority"] else ""
            print(f"  {g['domain']:<35} {', '.join(g['competitors'])}{a}")
        if len(gap) > 30:
            print(f"  ... {len(gap) - 30} more (gap.csv with --out)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
