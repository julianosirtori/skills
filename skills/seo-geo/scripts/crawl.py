#!/usr/bin/env python3
"""crawl.py - crawl a whole site and report site-wide SEO problems.

Usage: crawl.py URL [--max-pages 500] [--workers 4] [--rate 4] [--out DIR]
                    [--no-sitemap] [--ignore-robots] [--check-external]
                    [--ua crawler|browser|googlebot] [--json]

  URL               where to start, usually the home page
  --max-pages N     stop after N HTML pages (default 500)
  --workers N       parallel requests (default 4)
  --rate R          at most R requests per second overall (default 4)
  --out DIR         also write pages.csv, links.csv and issues.csv there
  --no-sitemap      don't add sitemap URLs (orphan detection needs them)
  --ignore-robots   crawl paths robots.txt disallows (only on your own site)
  --check-external  also check every external link once (slower)
  --ua              user-agent: an honest crawler string (default), a
                    browser's, or Googlebot's (some CDNs block unknown bots)

It follows internal <a href> links breadth-first from URL, so the depth it
records is the click depth from that page. Then it fetches the sitemap URLs
the links never reached: those are orphans. Like audit.py it reads the raw
HTML and does not run JavaScript, which is how most AI crawlers see the site.

Site-wide findings: broken internal links (with the pages that link to them),
internal links that redirect, redirect chains, links to pages robots.txt
blocks, noindex pages and noindex in the sitemap, canonicals pointing elsewhere
or to broken pages, missing and duplicate titles, descriptions and H1s, thin
and JavaScript-only pages, exact and near-duplicate content, deep pages,
orphans, indexable pages missing from the sitemap, sitemap URLs that are not
200/indexable/canonical, weakly linked pages, slow responses, http links,
hreflang without return links, images without alt, and broken external links
with --check-external.

Read-only. Python 3.8+ standard library; imports audit.py from this folder.
"""

import argparse
import collections
import csv
import hashlib
import json
import os
import re
import sys
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from audit import BROWSER_UA, PageParser, fetch, jsonld_types, parse_robots, robots_verdict  # noqa: E402

UAS = {
    "crawler": "Mozilla/5.0 (compatible; seo-geo-crawler/1.0; +https://github.com/julianosirtori/skills)",
    "browser": BROWSER_UA,
    "googlebot": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
}
SKIP_EXT = re.compile(r"\.(pdf|jpe?g|png|gif|webp|avif|svg|ico|css|js|mjs|json|xml|txt|zip|gz|rar|7z|"
                      r"mp4|webm|mov|mp3|wav|woff2?|ttf|eot|docx?|xlsx?|pptx?|csv|apk|dmg|exe)$", re.I)
TRACKING = re.compile(r"^(utm_|gclid$|fbclid$|mc_|_hs|ref$|ref_src$)", re.I)


# ---------------------------------------------------------------- helpers

def normalize(url, base=None):
    """Absolute URL without fragment or tracking params; None for non-http links."""
    if base:
        url = urllib.parse.urljoin(base, url.strip())
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return None
    host = (parts.hostname or "").lower()
    if parts.port and not ((parts.scheme == "http" and parts.port == 80) or (parts.scheme == "https" and parts.port == 443)):
        host += f":{parts.port}"
    query = urllib.parse.urlencode([(k, v) for k, v in urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
                                    if not TRACKING.match(k)])
    return urllib.parse.urlunsplit((parts.scheme.lower(), host, parts.path or "/", query, ""))


def bare_host(host):
    return host[4:] if host.startswith("www.") else host


class RateLimiter:
    def __init__(self, rate):
        self.interval, self.lock, self.next = 1.0 / max(rate, 0.1), threading.Lock(), 0.0

    def wait(self):
        with self.lock:
            now = time.monotonic()
            delay = self.next - now
            self.next = max(now, self.next) + self.interval
        if delay > 0:
            time.sleep(delay)


def simhash(text):
    words = re.findall(r"\w+", text.lower())
    shingles = [" ".join(words[i:i + 4]) for i in range(max(1, len(words) - 3))]
    v = [0] * 64
    for sh in shingles:
        h = int.from_bytes(hashlib.md5(sh.encode()).digest()[:8], "big")
        for i in range(64):
            v[i] += 1 if h >> i & 1 else -1
    return sum(1 << i for i in range(64) if v[i] > 0)


# ---------------------------------------------------------------- crawl

class Crawler:
    def __init__(self, args):
        self.args = args
        self.ua = UAS[args.ua]
        self.limiter = RateLimiter(args.rate)
        self.pages = {}            # url -> record
        self.links = []            # (source, target, rel, anchor, internal)
        self.inlinks = collections.defaultdict(set)
        self.blocked = set()
        self.skipped_assets = collections.Counter()
        self.external = collections.defaultdict(set)  # external url -> sources
        self.groups = []
        self.host = None

    def internal(self, url):
        return bare_host(urllib.parse.urlsplit(url).netloc.lower()) == bare_host(self.host)

    def allowed(self, url):
        if self.args.ignore_robots or not self.groups:
            return True
        parts = urllib.parse.urlsplit(url)
        path = parts.path + ("?" + parts.query if parts.query else "")
        return robots_verdict(self.groups, "seo-geo-crawler", path)[0]

    def get(self, url):
        self.limiter.wait()
        return fetch(url, ua=self.ua)

    def visit(self, url, depth, source):
        r = self.get(url)
        rec = {"url": url, "depth": depth, "found": source, "status": r["status"], "error": r["error"],
               "final": r["url"], "hops": len(r["chain"]), "ms": r["ms"],
               "ctype": (r["headers"].get("Content-Type") or "").split(";")[0].strip().lower()}
        out = []
        if r["status"] != 200 or "html" not in rec["ctype"]:
            return rec, out
        p = PageParser()
        try:
            p.feed(r["body"])
        except Exception:
            pass
        metas = {(m.get("name") or m.get("property") or "").lower(): m.get("content", "") for m in p.meta}
        robots = " ".join(v for k, v in metas.items() if k in ("robots", "googlebot")) + " " + \
            r["headers"].get("X-Robots-Tag", "")
        canon = [l.get("href") for l in p.links if "canonical" in l.get("rel", "").lower().split()]
        text = " ".join(" ".join(p.text).split())
        types, _, _ = jsonld_types(p.jsonld)
        rec.update({
            "title": " ".join(p.title.split()),
            "description": metas.get("description", "").strip(),
            "h1": [t for tag, t in p.headings if tag == "h1"],
            "noindex": bool(re.search(r"noindex|\bnone\b", robots, re.I)),
            "canonical": normalize(canon[0], r["url"]) if canon else None,
            "canonicals": len(canon),
            "words": len(text.split()),
            "app_root": bool(p.root_ids),
            "hash": hashlib.md5(text.lower().encode()).hexdigest() if text else None,
            "simhash": simhash(text) if len(text.split()) >= 80 else None,
            "lang": p.lang,
            "hreflang": {l.get("hreflang"): normalize(l.get("href", ""), r["url"])
                         for l in p.links if l.get("hreflang") and "alternate" in l.get("rel", "").lower()},
            "jsonld": sorted(set(map(str, types))),
            "imgs": p.imgs, "imgs_no_alt": p.imgs_no_alt,
            "http_links": 0,
        })
        for href, rel, anchor in p.anchors:
            if href.startswith("#"):
                continue
            target = normalize(href, r["url"])
            if not target:
                continue
            internal = self.internal(target)
            if internal and target.startswith("http://") and r["url"].startswith("https://"):
                rec["http_links"] += 1
            out.append((r["url"], target, rel, anchor, internal))
        return rec, out

    def run(self):
        start = normalize(self.args.url if re.match(r"https?://", self.args.url) else "https://" + self.args.url)
        first = self.get(start)
        if first["status"] is None:
            sys.exit(f"cannot fetch {start}: {first['error']}")
        start_final = normalize(first["url"])
        self.host = urllib.parse.urlsplit(start_final).netloc
        origin = f"{urllib.parse.urlsplit(start_final).scheme}://{self.host}"
        rb = fetch(origin + "/robots.txt", ua=self.ua)
        sitemaps = []
        if rb["status"] == 200 and "<html" not in rb["body"][:500].lower():
            self.groups, sitemaps = parse_robots(rb["body"])

        self.sitemap_urls = set()
        if not self.args.no_sitemap:
            for sm in (sitemaps or [origin + "/sitemap.xml"])[:5]:
                self.read_sitemap(sm, 0)

        seen = {start_final}
        frontier = [(start_final, 0, None)]
        pool = ThreadPoolExecutor(max_workers=self.args.workers)
        self.link_phase_complete = True
        while frontier:
            budget = self.args.max_pages - len(self.pages)
            if budget <= 0:
                self.link_phase_complete = False
                break
            batch, frontier = frontier[:budget], frontier[budget:]
            if frontier:
                self.link_phase_complete = False
            next_frontier = []
            for rec, out in pool.map(lambda t: self.visit(*t), batch):
                self.record(rec)
                for src, tgt, rel, anchor, internal in out:
                    self.links.append((src, tgt, rel, anchor, internal))
                    if not internal:
                        self.external[tgt].add(src)
                        continue
                    self.inlinks[tgt].add(src)
                    if tgt in seen:
                        continue
                    seen.add(tgt)
                    path = urllib.parse.urlsplit(tgt).path
                    if SKIP_EXT.search(path):
                        self.skipped_assets[path.rsplit(".", 1)[-1].lower()] += 1
                        continue
                    if not self.allowed(tgt):
                        self.blocked.add(tgt)
                        continue
                    next_frontier.append((tgt, rec["depth"] + 1, src))
            frontier = next_frontier + frontier
            print(f"  crawled {len(self.pages)} pages, {len(frontier)} queued", file=sys.stderr)

        # Sitemap URLs the links never reached: orphans (when the link phase finished).
        self.orphans = set()
        rest = [u for u in sorted(self.sitemap_urls) if u not in seen and u not in self.finals()]
        budget = self.args.max_pages - len(self.pages)
        batch = [(u, None, "sitemap") for u in rest[:max(budget, 0)]]
        for rec, _ in pool.map(lambda t: self.visit(*t), batch):
            self.record(rec)
            self.orphans.add(rec["url"])
        self.unvisited_sitemap = len(rest) - len(batch)

        if self.args.check_external:
            ext = sorted(self.external)[:2000]
            def check(u):
                self.limiter.wait()
                return u, fetch(u, ua=BROWSER_UA, limit=20000)
            self.external_status = dict((u, r["status"]) for u, r in pool.map(check, ext))
        else:
            self.external_status = {}
        pool.shutdown()
        self.start = start_final

    def finals(self):
        return {p.get("final") and normalize(p["final"]) for p in self.pages.values()}

    def record(self, rec):
        self.pages[rec["url"]] = rec

    def read_sitemap(self, url, depth):
        r = fetch(url, ua=self.ua)
        if r["status"] != 200:
            return
        locs = re.findall(r"<loc>\s*(.*?)\s*</loc>", r["body"], re.S)
        if "<sitemapindex" in r["body"]:
            if depth < 2:
                for child in locs[:50]:
                    self.read_sitemap(child, depth + 1)
            return
        for loc in locs:
            n = normalize(loc.replace("&amp;", "&"))
            if n:
                self.sitemap_urls.add(n)


# ---------------------------------------------------------------- analysis

def analyze(c):
    issues = []  # (severity, kind, url, detail)

    def add(sev, kind, url, detail=""):
        issues.append((sev, kind, url, detail))

    pages = c.pages
    final_of = {u: normalize(p["final"]) for u, p in pages.items() if p.get("final")}
    by_final = {}
    for u, p in pages.items():
        by_final.setdefault(final_of.get(u, u), p)

    def resolved(url):
        p = pages.get(url)
        return p, (final_of.get(url) if p else None)

    # Broken and redirected internal links
    for tgt, sources in c.inlinks.items():
        p, _ = resolved(tgt)
        if not p:
            continue
        srcs = sorted(sources)
        sample = ", ".join(srcs[:3]) + (f" (+{len(srcs) - 3} more)" if len(srcs) > 3 else "")
        if p["status"] is None:
            add("HIGH", "internal link: fetch error", tgt, f"{p['error']}; linked from {sample}")
        elif p["status"] >= 400:
            add("HIGH", f"internal link: HTTP {p['status']}", tgt, f"linked from {len(srcs)} page(s): {sample}")
        elif p["hops"]:
            add("LOW", "internal link redirects", tgt, f"-> {p['final']} ({p['hops']} hop(s)); linked from {len(srcs)} page(s): {sample}")
        if p.get("hops", 0) > 1:
            add("MEDIUM", "redirect chain", tgt, f"{p['hops']} hops to {p['final']}")
    for tgt in sorted(c.blocked):
        srcs = sorted(c.inlinks.get(tgt, []))
        add("LOW", "linked page blocked by robots.txt", tgt, f"linked from {len(srcs)} page(s)")

    html = {u: p for u, p in pages.items() if p.get("status") == 200 and "title" in p}
    indexable = {}
    for u, p in html.items():
        if p["noindex"]:
            add("MEDIUM" if u in c.sitemap_urls else "INFO", "noindex", u,
                "and listed in the sitemap" if u in c.sitemap_urls else "check it is meant to be hidden")
            continue
        canon = p["canonical"]
        if p["canonicals"] > 1:
            add("HIGH", "several canonical tags", u)
        if canon and canon.rstrip("/") != normalize(p["final"]).rstrip("/"):
            cp = pages.get(canon) or by_final.get(canon)
            detail = f"-> {canon}"
            if cp and (cp.get("status") != 200 or cp.get("hops") or cp.get("noindex")):
                add("HIGH", "canonical to a broken, redirected or noindex URL", u, detail)
            else:
                add("INFO", "canonical points to another URL", u, detail)
            continue
        if not canon:
            add("LOW", "no canonical", u)
        indexable[normalize(p["final"])] = p

    # Titles, descriptions, H1
    titles = collections.defaultdict(list)
    descs = collections.defaultdict(list)
    for u, p in indexable.items():
        if not p["title"]:
            add("HIGH", "missing title", u)
        else:
            titles[p["title"].lower()].append(u)
            if len(p["title"]) > 65:
                add("LOW", "long title", u, f"{len(p['title'])} chars")
        if not p["description"]:
            add("LOW", "missing meta description", u)
        else:
            descs[p["description"].lower()].append(u)
        if not p["h1"]:
            add("MEDIUM", "no H1 in the raw HTML", u)
        if p["words"] < 150:
            if p["app_root"]:
                add("HIGH", "JavaScript-only page", u, f"{p['words']} words in the raw HTML")
            else:
                add("MEDIUM", "thin page", u, f"{p['words']} words")
        if p["ms"] > 2500:
            add("MEDIUM", "slow HTML response", u, f"{p['ms']} ms")
        if p["http_links"]:
            add("LOW", "links to http:// pages", u, f"{p['http_links']} link(s)")
        if p["imgs"] and p["imgs_no_alt"]:
            add("LOW", "images without alt", u, f"{p['imgs_no_alt']}/{p['imgs']}")
        if not p["lang"]:
            add("LOW", "no <html lang>", u)
        if p["depth"] is not None and p["depth"] > 3:
            add("MEDIUM", "deep page", u, f"{p['depth']} clicks from the start page")
        if p["depth"] is not None and p["depth"] > 0 and len(c.inlinks.get(u, ())) == 1:
            add("LOW", "only one internal link points here", u)
    for t, us in titles.items():
        if len(us) > 1:
            add("MEDIUM", "duplicate title", us[0], f"{len(us)} pages: {', '.join(us[:5])}")
    for d, us in descs.items():
        if len(us) > 1:
            add("LOW", "duplicate meta description", us[0], f"{len(us)} pages: {', '.join(us[:5])}")

    # Duplicate content
    hashes = collections.defaultdict(list)
    for u, p in indexable.items():
        if p["hash"] and p["words"] >= 30:
            hashes[p["hash"]].append(u)
    for us in hashes.values():
        if len(us) > 1:
            add("HIGH", "duplicate content", us[0], f"identical text on {len(us)} pages: {', '.join(us[:5])}")
    sims = [(u, p["simhash"]) for u, p in indexable.items() if p["simhash"] is not None]
    exact = {u for us in hashes.values() if len(us) > 1 for u in us}
    if len(sims) <= 4000:
        near = collections.defaultdict(set)
        for i in range(len(sims)):
            for j in range(i + 1, len(sims)):
                if bin(sims[i][1] ^ sims[j][1]).count("1") <= 3 and not (sims[i][0] in exact and sims[j][0] in exact):
                    near[sims[i][0]].add(sims[j][0])
        for u, others in near.items():
            add("MEDIUM", "near-duplicate content", u, f"almost the same text as {len(others)} page(s): {', '.join(sorted(others)[:4])}")

    # Sitemap
    if c.sitemap_urls:
        for u in sorted(c.sitemap_urls):
            p = pages.get(u)
            if not p:
                continue
            if p["status"] != 200:
                add("MEDIUM", "sitemap URL not 200", u, f"HTTP {p['status']}")
            elif p["hops"]:
                add("MEDIUM", "sitemap URL redirects", u, f"-> {p['final']}")
        in_sitemap = c.sitemap_urls | {final_of.get(u) for u in c.sitemap_urls if u in final_of}
        missing = [u for u in indexable if u not in in_sitemap]
        for u in missing[:200]:
            add("LOW", "indexable page not in the sitemap", u)
        if c.link_phase_complete:
            for u in sorted(c.orphans):
                p = pages[u]
                if p.get("status") == 200 and not p.get("noindex"):
                    add("MEDIUM", "orphan page (in the sitemap, no internal links)", u)

    # hreflang return links
    for u, p in indexable.items():
        for lang, alt in (p.get("hreflang") or {}).items():
            ap = pages.get(alt) or by_final.get(alt)
            if not ap or "hreflang" not in ap or alt.rstrip("/") == u.rstrip("/"):
                continue
            back = {v.rstrip("/") for v in (ap.get("hreflang") or {}).values() if v}
            if u.rstrip("/") not in back:
                add("MEDIUM", "hreflang without return link", u, f"{lang} -> {alt} does not link back")

    # External links
    for u, st in sorted(c.external_status.items()):
        if st is None or st >= 400 and st not in (401, 403, 429, 999):
            srcs = sorted(c.external[u])
            add("LOW", f"broken external link (HTTP {st})", u, f"on {len(srcs)} page(s): {', '.join(srcs[:3])}")
    return issues, indexable


# ---------------------------------------------------------------- output

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("url")
    ap.add_argument("--max-pages", type=int, default=500)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--rate", type=float, default=4.0)
    ap.add_argument("--out")
    ap.add_argument("--no-sitemap", action="store_true")
    ap.add_argument("--ignore-robots", action="store_true")
    ap.add_argument("--check-external", action="store_true")
    ap.add_argument("--ua", choices=sorted(UAS), default="crawler")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    c = Crawler(args)
    t0 = time.time()
    c.run()
    issues, indexable = analyze(c)
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "INFO": 3}
    issues.sort(key=lambda i: (order[i[0]], i[1], i[2]))

    statuses = collections.Counter(str(p["status"]) for p in c.pages.values())
    depths = collections.Counter(p["depth"] for p in indexable.values() if p["depth"] is not None)
    summary = {
        "start": c.start, "pages_fetched": len(c.pages), "indexable": len(indexable),
        "statuses": dict(statuses), "sitemap_urls": len(c.sitemap_urls),
        "orphans_checked": c.link_phase_complete, "unvisited_sitemap_urls": c.unvisited_sitemap,
        "blocked_by_robots": len(c.blocked), "assets_skipped": dict(c.skipped_assets),
        "internal_links": sum(1 for l in c.links if l[4]), "external_links": len(c.external),
        "click_depth": dict(sorted(depths.items())), "seconds": round(time.time() - t0, 1),
        "complete": c.link_phase_complete and c.unvisited_sitemap == 0,
    }

    if args.out:
        os.makedirs(args.out, exist_ok=True)
        with open(os.path.join(args.out, "pages.csv"), "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["url", "status", "final", "depth", "found_via", "inlinks", "noindex", "canonical",
                        "title", "description", "h1", "words", "ms", "jsonld", "lang", "in_sitemap"])
            for u, p in sorted(c.pages.items()):
                w.writerow([u, p["status"], p["final"], p["depth"], p["found"], len(c.inlinks.get(u, ())),
                            p.get("noindex"), p.get("canonical"), p.get("title"), p.get("description"),
                            " | ".join(p.get("h1") or []), p.get("words"), p["ms"], " ".join(p.get("jsonld") or []),
                            p.get("lang"), u in c.sitemap_urls])
        with open(os.path.join(args.out, "links.csv"), "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["source", "target", "internal", "rel", "anchor", "target_status"])
            for src, tgt, rel, anchor, internal in c.links:
                st = (c.pages.get(tgt) or {}).get("status") if internal else c.external_status.get(tgt, "")
                w.writerow([src, tgt, internal, rel, anchor, st])
        with open(os.path.join(args.out, "issues.csv"), "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["severity", "issue", "url", "detail"])
            w.writerows(issues)

    if args.json:
        print(json.dumps({"summary": summary, "issues": [dict(zip(("severity", "issue", "url", "detail"), i))
                                                          for i in issues]}, indent=2, ensure_ascii=False))
        return 0

    print(f"# Crawl of {c.start}\n")
    print(f"{summary['pages_fetched']} URLs fetched in {summary['seconds']} s, {summary['indexable']} indexable HTML pages, "
          f"{summary['internal_links']} internal links, {summary['external_links']} external URLs")
    print(f"status codes: {', '.join(f'{k}: {v}' for k, v in sorted(statuses.items()))}")
    print(f"click depth of indexable pages: {', '.join(f'{k}: {v}' for k, v in summary['click_depth'].items())}")
    print(f"sitemap: {summary['sitemap_urls']} URLs; robots-blocked links: {summary['blocked_by_robots']}")
    if not summary["complete"]:
        print(f"\nINCOMPLETE: hit --max-pages {args.max_pages} before the end "
              f"({'links not exhausted, orphans not reported' if not c.link_phase_complete else ''}"
              f"{'; ' if not c.link_phase_complete and c.unvisited_sitemap else ''}"
              f"{str(c.unvisited_sitemap) + ' sitemap URLs not fetched' if c.unvisited_sitemap else ''}). "
              "Raise --max-pages for a full picture.")
    kinds = collections.Counter((i[0], i[1]) for i in issues)
    print("\n## Issues by type")
    for (sev, kind), n in sorted(kinds.items(), key=lambda x: (order[x[0][0]], -x[1])):
        print(f"  {sev:<6} {n:>5}  {kind}")
    print("\n## Details (up to 10 per type; all of them in issues.csv with --out)")
    shown = collections.Counter()
    for sev, kind, url, detail in issues:
        if sev == "INFO" or shown[kind] >= 10:
            continue
        shown[kind] += 1
        print(f"  {sev:<6} {kind}: {url}" + (f"  {detail}" if detail else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
