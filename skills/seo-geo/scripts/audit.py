#!/usr/bin/env python3
"""audit.py - technical SEO and AI-search (GEO) audit of a live site.

Usage: audit.py URL [--pages N] [--no-bots] [--json]
  URL          the page to audit (usually the home page)
  --pages N    also audit up to N-1 more pages taken from the sitemap (default 1)
  --no-bots    skip fetching the page as each AI crawler
  --json       print the raw findings as JSON instead of the report

What it checks, the way a crawler that does not run JavaScript sees the site:
  site      robots.txt rules for each search and AI crawler (Google's matching
            rules: most specific user-agent group, longest path, Allow wins
            ties), sitemaps and lastmod, llms.txt
  bots      the page fetched with each crawler's user-agent next to a browser's,
            to catch a CDN or WAF (Cloudflare's "Block AI bots", for example)
            answering 403 or a challenge page to bots
  page      status, redirects, X-Robots-Tag and meta robots, canonical, title,
            meta description, lang, hreflang, H1 and heading outline, words of
            text in the raw HTML (a JavaScript-only page shows almost none),
            JSON-LD types and errors, Open Graph, dates, images without alt

Each finding is PASS, WARN or FAIL. A spoofed user-agent comes from this
machine, not from the crawler's IPs, so a bot block seen here is strong
evidence but the CDN's own bot settings are the final word. Read-only.
Python 3.8+ standard library only.
"""

import argparse
import gzip
import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

TIMEOUT = 20
BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36")

# token, what it feeds, user-agent to send (None = robots.txt token only, never fetches)
CRAWLERS = [
    ("Googlebot", "Google Search, AI Overviews, AI Mode",
     "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"),
    ("Google-Extended", "Gemini training and grounding (robots token only)", None),
    ("Bingbot", "Bing, Copilot; Bing's index feeds other assistants",
     "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)"),
    ("OAI-SearchBot", "ChatGPT search results and citations",
     "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; OAI-SearchBot/1.0; +https://openai.com/searchbot"),
    ("ChatGPT-User", "ChatGPT fetching a page a user asked about",
     "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ChatGPT-User/1.0; +https://openai.com/bot"),
    ("GPTBot", "OpenAI model training",
     "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; GPTBot/1.1; +https://openai.com/gptbot"),
    ("Claude-SearchBot", "Claude search results",
     "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; Claude-SearchBot/1.0; +Claude-SearchBot@anthropic.com"),
    ("Claude-User", "Claude fetching a page a user asked about",
     "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; Claude-User/1.0; +Claude-User@anthropic.com"),
    ("ClaudeBot", "Anthropic model training",
     "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ClaudeBot/1.0; +claudebot@anthropic.com"),
    ("PerplexityBot", "Perplexity search index",
     "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)"),
    ("Perplexity-User", "Perplexity fetching a page a user asked about",
     "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Perplexity-User/1.0; +https://perplexity.ai/perplexity-user)"),
    ("Applebot", "Siri, Spotlight, Safari suggestions",
     "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15 (Applebot/0.1; +http://www.apple.com/go/applebot)"),
    ("Applebot-Extended", "Apple Intelligence training (robots token only)", None),
    ("meta-externalagent", "Meta AI",
     "meta-externalagent/1.1 (+https://developers.facebook.com/docs/sharing/webmasters/crawler)"),
    ("CCBot", "Common Crawl, a training source for many models",
     "CCBot/2.0 (https://commoncrawl.org/faq/)"),
]


# ---------------------------------------------------------------- fetching

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


_CTX = ssl.create_default_context()
_OPENER = urllib.request.build_opener(NoRedirect, urllib.request.HTTPSHandler(context=_CTX))


def fetch(url, ua=BROWSER_UA, max_redirects=8, limit=5_000_000):
    """GET with manual redirects. Returns dict(status, url, chain, headers, body, ms, error)."""
    chain, start = [], time.time()
    for _ in range(max_redirects + 1):
        req = urllib.request.Request(url, headers={
            "User-Agent": ua, "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.8,pt-BR;q=0.6", "Accept-Encoding": "gzip"})
        try:
            resp = _OPENER.open(req, timeout=TIMEOUT)
            status, headers, raw = resp.status, resp.headers, resp.read(limit)
        except urllib.error.HTTPError as exc:
            status, headers = exc.code, exc.headers
            try:
                raw = exc.read(limit)
            except Exception:
                raw = b""
        except Exception as exc:
            return {"status": None, "url": url, "chain": chain, "headers": {}, "body": "",
                    "ms": int((time.time() - start) * 1000), "error": str(exc)[:200]}
        if status in (301, 302, 303, 307, 308) and headers.get("Location"):
            chain.append((status, url))
            url = urllib.parse.urljoin(url, headers["Location"])
            continue
        if headers.get("Content-Encoding", "").lower() == "gzip" or raw[:2] == b"\x1f\x8b":
            try:
                raw = gzip.decompress(raw)
            except OSError:
                pass
        charset = headers.get_content_charset() or "utf-8"
        body = raw.decode(charset, errors="replace")
        return {"status": status, "url": url, "chain": chain, "headers": dict(headers.items()),
                "body": body, "ms": int((time.time() - start) * 1000), "error": None}
    return {"status": None, "url": url, "chain": chain, "headers": {}, "body": "",
            "ms": int((time.time() - start) * 1000), "error": "too many redirects"}


# ---------------------------------------------------------------- robots.txt

def parse_robots(text):
    """Groups of (agents, rules). Rules are (allow: bool, pattern)."""
    groups, agents, rules, last_was_agent = [], [], [], False
    sitemaps = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, value = (s.strip() for s in line.split(":", 1))
        key = key.lower()
        if key == "user-agent":
            if not last_was_agent and agents:
                groups.append((agents, rules))
                agents, rules = [], []
            agents.append(value.lower())
            last_was_agent = True
        elif key in ("allow", "disallow"):
            last_was_agent = False
            if agents:
                rules.append((key == "allow", value))
        elif key == "sitemap":
            sitemaps.append(value)
        else:
            last_was_agent = False
    if agents:
        groups.append((agents, rules))
    return groups, sitemaps


def _pattern_re(pattern):
    anchored = pattern.endswith("$")
    body = re.escape(pattern[:-1] if anchored else pattern).replace(r"\*", ".*")
    return re.compile("^" + body + ("$" if anchored else ""))


def robots_verdict(groups, token, path):
    """Google's rules: the group whose user-agent is the longest match of the
    token wins (all groups naming it are merged); '*' only if none match.
    Then the longest matching rule wins, Allow on ties. Returns
    (allowed, matched_group_label, rule)."""
    token = token.lower()
    best_len, chosen = -1, []
    for agents, rules in groups:
        for a in agents:
            if a != "*" and token.startswith(a) or a == token:
                if len(a) > best_len:
                    best_len, chosen = len(a), list(rules)
                elif len(a) == best_len:
                    chosen += rules
    label = token
    if best_len < 0:
        label = "*"
        for agents, rules in groups:
            if "*" in agents:
                chosen += rules
        if not any("*" in agents for agents, _ in groups):
            return True, "none", None
    best = None
    for allow, pattern in chosen:
        if pattern == "":
            continue  # "Disallow:" with no value allows everything
        if _pattern_re(pattern).match(path):
            key = (len(pattern), allow)
            if best is None or key > best[0]:
                best = (key, allow, pattern)
    if best is None:
        return True, label, None
    return best[1], label, ("Allow: " if best[1] else "Disallow: ") + best[2]


# ---------------------------------------------------------------- HTML

class PageParser(HTMLParser):
    SKIP = {"script", "style", "noscript", "template", "svg"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title, self.in_title = "", False
        self.meta, self.links, self.headings = [], [], []
        self.jsonld, self._jsonld_buf, self.in_jsonld = [], [], False
        self.skip_depth, self.text = 0, []
        self.heading_tag, self.heading_buf = None, []
        self.lang = None
        self.imgs = self.imgs_no_alt = 0
        self.scripts = 0
        self.root_ids = []
        self.times = []

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "html":
            self.lang = a.get("lang")
        elif tag == "title":
            self.in_title = True
        elif tag == "meta":
            self.meta.append(a)
        elif tag == "link":
            self.links.append(a)
        elif tag == "img":
            self.imgs += 1
            if "alt" not in a:
                self.imgs_no_alt += 1
        elif tag == "time" and a.get("datetime"):
            self.times.append(a["datetime"])
        elif tag in ("div", "main") and a.get("id") in ("root", "app", "__next", "__nuxt", "svelte"):
            self.root_ids.append(a["id"])
        if tag == "script":
            self.scripts += 1
            if a.get("type", "").lower() == "application/ld+json":
                self.in_jsonld, self._jsonld_buf = True, []
        if tag in self.SKIP:
            self.skip_depth += 1
        if re.fullmatch(r"h[1-6]", tag):
            self.heading_tag, self.heading_buf = tag, []

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag == "script" and self.in_jsonld:
            self.jsonld.append("".join(self._jsonld_buf))
            self.in_jsonld = False
        if tag in self.SKIP and self.skip_depth:
            self.skip_depth -= 1
        if tag == self.heading_tag:
            self.headings.append((tag, " ".join("".join(self.heading_buf).split())))
            self.heading_tag = None

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        if self.in_jsonld:
            self._jsonld_buf.append(data)
            return
        if self.skip_depth:
            return
        self.text.append(data)
        if self.heading_tag:
            self.heading_buf.append(data)


def jsonld_types(blocks):
    types, errors, dates = [], [], {}

    def walk(node):
        if isinstance(node, list):
            for n in node:
                walk(n)
        elif isinstance(node, dict):
            t = node.get("@type")
            if t:
                types.extend(t if isinstance(t, list) else [t])
            for k in ("datePublished", "dateModified"):
                if isinstance(node.get(k), str):
                    dates.setdefault(k, node[k])
            for v in node.values():
                if isinstance(v, (list, dict)):
                    walk(v)

    for raw in blocks:
        try:
            walk(json.loads(raw))
        except ValueError as exc:
            errors.append(str(exc)[:80])
    return types, errors, dates


# ---------------------------------------------------------------- checks

def add(findings, level, area, msg):
    findings.append({"level": level, "area": area, "msg": msg})


def audit_page(url, findings, main=False):
    r = fetch(url)
    info = {"url": url, "status": r["status"], "final_url": r["url"], "ms": r["ms"]}
    if r["error"] or r["status"] is None:
        add(findings, "FAIL", "page", f"{url}: could not fetch ({r['error']})")
        return info, r
    for code, hop in r["chain"]:
        add(findings, "WARN" if code in (302, 303, 307) and main else "PASS", "page",
            f"{hop} -> {code} redirect" + (" (temporary: use 301/308 for permanent moves)" if code in (302, 303, 307) else ""))
    if len(r["chain"]) > 2:
        add(findings, "WARN", "page", f"{len(r['chain'])} redirect hops before {r['url']}")
    if r["status"] != 200:
        add(findings, "FAIL", "page", f"{r['url']}: HTTP {r['status']}")
        return info, r
    ms = "WARN" if r["ms"] > 2500 else "PASS"
    add(findings, ms, "page", f"{r['url']}: HTTP 200 in {r['ms']} ms, {len(r['body']) // 1024} KB HTML")
    if len(r["body"].encode("utf-8", "ignore")) > 2_000_000:
        add(findings, "WARN", "page", "HTML over 2 MB: Googlebot reads only the first 2 MB; keep content and JSON-LD above that")

    xrt = r["headers"].get("X-Robots-Tag", "")
    if re.search(r"noindex|none", xrt, re.I):
        add(findings, "FAIL", "page", f"X-Robots-Tag header blocks indexing: {xrt}")

    p = PageParser()
    try:
        p.feed(r["body"])
    except Exception as exc:  # malformed HTML should not stop the audit
        add(findings, "WARN", "page", f"HTML parse error: {exc}")
    metas = {(m.get("name") or m.get("property") or "").lower(): m.get("content", "") for m in p.meta}

    robots_meta = " ".join(v for k, v in metas.items() if k in ("robots", "googlebot"))
    if re.search(r"noindex|none", robots_meta, re.I):
        add(findings, "FAIL", "page", f"meta robots blocks indexing: {robots_meta}")
    if "data-nosnippet" in r["body"]:
        add(findings, "WARN", "page", "data-nosnippet on some elements: Google will not quote those parts")
    if re.search(r"nosnippet|max-snippet:0", robots_meta + " " + xrt, re.I):
        add(findings, "WARN", "page", "nosnippet/max-snippet:0: Google cannot quote this page in AI Overviews or snippets")

    canon = [l.get("href") for l in p.links if "canonical" in l.get("rel", "").lower().split()]
    if not canon:
        add(findings, "WARN", "page", "no rel=canonical")
    elif len(canon) > 1:
        add(findings, "FAIL", "page", f"{len(canon)} canonical tags: {canon}")
    else:
        c = urllib.parse.urljoin(r["url"], canon[0])
        same = c.rstrip("/") == r["url"].rstrip("/")
        add(findings, "PASS" if same else "WARN", "page",
            f"canonical {'= this URL' if same else '-> ' + c + ' (another URL: this page will not be indexed as itself)'}")

    title = " ".join(p.title.split())
    if not title:
        add(findings, "FAIL", "page", "no <title>")
    else:
        lvl = "PASS" if 15 <= len(title) <= 65 else "WARN"
        add(findings, lvl, "page", f"title ({len(title)} chars): {title}")
    desc = metas.get("description", "").strip()
    if not desc:
        add(findings, "WARN", "page", "no meta description")
    else:
        lvl = "PASS" if 50 <= len(desc) <= 170 else "WARN"
        add(findings, lvl, "page", f"meta description ({len(desc)} chars): {desc[:160]}")

    add(findings, "PASS" if p.lang else "WARN", "page", f"<html lang>: {p.lang or 'missing'}")
    hreflang = [l.get("hreflang") for l in p.links if l.get("hreflang")]
    if hreflang:
        add(findings, "PASS", "page", f"hreflang: {', '.join(sorted(set(hreflang)))}")

    h1 = [t for tag, t in p.headings if tag == "h1"]
    if len(h1) != 1:
        add(findings, "WARN", "page", f"{len(h1)} <h1> in the raw HTML" + (f": {h1[:3]}" if h1 else ""))
    else:
        add(findings, "PASS", "page", f"h1: {h1[0][:100]}")
    outline = [f"{tag}: {t[:70]}" for tag, t in p.headings if tag in ("h2", "h3")][:12]
    question_heads = sum(1 for tag, t in p.headings if t.strip().endswith("?"))

    words = len(" ".join(p.text).split())
    if words < 150 and (p.root_ids or p.scripts > 3):
        add(findings, "FAIL", "page",
            f"only {words} words in the raw HTML and a JS app root ({', '.join(p.root_ids) or 'many scripts'}): "
            "the content is rendered by JavaScript, which most AI crawlers do not run")
    elif words < 150:
        add(findings, "WARN", "page", f"only {words} words of text in the raw HTML")
    else:
        add(findings, "PASS", "page", f"{words} words of text in the raw HTML (no JavaScript needed)")

    types, errs, dates = jsonld_types(p.jsonld)
    for e in errs:
        add(findings, "FAIL", "schema", f"JSON-LD does not parse: {e}")
    if types:
        add(findings, "PASS", "schema", f"JSON-LD types: {', '.join(sorted(set(map(str, types))))}")
    else:
        add(findings, "WARN", "schema", "no JSON-LD in the raw HTML (plugins may inject it with JavaScript: "
            "check the rendered page before reporting it missing)")
    if main and not ({"Organization", "LocalBusiness", "Corporation", "Person", "WebSite"} & set(map(str, types))):
        add(findings, "WARN", "schema", "home page has no Organization/LocalBusiness/WebSite entity")

    og = [k for k in ("og:title", "og:description", "og:image") if metas.get(k)]
    add(findings, "PASS" if len(og) == 3 else "WARN", "page",
        f"Open Graph: {', '.join(og) or 'none'}" + ("" if len(og) == 3 else " (missing some of og:title/description/image)"))

    modified = (dates.get("dateModified") or metas.get("article:modified_time")
                or metas.get("og:updated_time") or (p.times[0] if p.times else None))
    if modified:
        add(findings, "PASS", "page", f"date signal: {modified}")
    if p.imgs:
        lvl = "WARN" if p.imgs_no_alt > p.imgs // 4 else "PASS"
        add(findings, lvl, "page", f"{p.imgs_no_alt}/{p.imgs} images without alt")

    info.update({"title": title, "description": desc, "words": words, "h1": h1, "outline": outline,
                 "question_headings": question_heads, "jsonld_types": sorted(set(map(str, types))),
                 "date": modified, "lang": p.lang})
    return info, r


def audit_bots(url, browser_status, browser_body, findings):
    rows = []
    base_len = len(browser_body)
    for token, feeds, ua in CRAWLERS:
        if ua is None:
            continue
        r = fetch(url, ua=ua)
        st = r["status"]
        body = r["body"] or ""
        challenge = bool(re.search(r"cf-chl|challenge-platform|Just a moment|Attention Required|captcha", body[:20000], re.I))
        note = ""
        if st is None:
            lvl, note = "WARN", f"error: {r['error']}"
        elif st in (401, 403, 429, 503) or challenge:
            lvl, note = ("FAIL", f"HTTP {st}" + (" challenge page" if challenge else "")
                         + " (browser gets " + str(browser_status) + "): a CDN/WAF likely blocks this bot")
        elif st != browser_status:
            lvl, note = "WARN", f"HTTP {st}, browser gets {browser_status}"
        elif base_len and len(body) < base_len * 0.3:
            lvl, note = "WARN", f"HTTP {st} but {len(body)} bytes vs {base_len} for a browser"
        else:
            lvl, note = "PASS", f"HTTP {st}, {len(body) // 1024} KB"
        add(findings, lvl, "bots", f"{token:<18} {note}  [{feeds}]")
        rows.append({"bot": token, "status": st, "note": note})
        time.sleep(0.3)
    return rows


def audit_site(origin, page_path, findings):
    site = {}
    r = fetch(origin + "/robots.txt")
    groups, sitemaps = [], []
    if r["status"] == 200 and "<html" not in r["body"][:500].lower():
        groups, sitemaps = parse_robots(r["body"])
        add(findings, "PASS", "site", f"robots.txt: {len(groups)} user-agent group(s)")
        if re.search(r"BEGIN Cloudflare Managed", r["body"], re.I):
            add(findings, "WARN", "site",
                "robots.txt has a Cloudflare managed block: Cloudflare adds AI-bot rules to the served file "
                "that are not in the site's own robots.txt (see the robots section for their effect)")
        signals = re.findall(r"^\s*Content-Signal:\s*(.+)$", r["body"], re.I | re.M)
        for sig in sorted(set(signals)):
            lvl = "WARN" if re.search(r"(search|ai-input)\s*=\s*no", sig, re.I) else "PASS"
            add(findings, lvl, "site", f"Content-Signal: {sig.strip()}")
    elif r["status"] == 404:
        add(findings, "WARN", "site", "no robots.txt (everything is allowed, but there is no Sitemap line)")
    else:
        add(findings, "FAIL" if r["status"] and r["status"] >= 500 else "WARN", "site",
            f"robots.txt returned HTTP {r['status']}" + (" (5xx makes Google treat the whole site as blocked)" if r["status"] and r["status"] >= 500 else ""))
    site["robots"] = []
    for token, feeds, _ in CRAWLERS:
        allowed_root, label, rule = robots_verdict(groups, token, "/")
        allowed_page, _, rule_page = robots_verdict(groups, token, page_path)
        allowed = allowed_root and allowed_page
        lvl = "PASS" if allowed else "FAIL"
        how = f"group {label}" + (f", {rule or rule_page}" if (rule or rule_page) else "")
        add(findings, lvl, "robots", f"{token:<18} {'allowed' if allowed else 'BLOCKED'} ({how})  [{feeds}]")
        site["robots"].append({"bot": token, "allowed": allowed, "group": label, "rule": rule or rule_page})

    sm_urls = sitemaps or [origin + "/sitemap.xml"]
    locs = []
    for sm in sm_urls[:3]:
        locs += read_sitemap(sm, findings, depth=0)
    site["sitemap_urls"] = len(locs)
    if not sitemaps:
        add(findings, "WARN", "site", "robots.txt has no Sitemap: line")

    lr = fetch(origin + "/llms.txt")
    has_llms = lr["status"] == 200 and "<html" not in lr["body"][:500].lower()
    add(findings, "PASS" if has_llms else "WARN", "site",
        "llms.txt present" if has_llms else "no llms.txt (optional; cheap to add, little proven effect)")
    site["llms_txt"] = has_llms
    return site, locs


def read_sitemap(url, findings, depth):
    r = fetch(url)
    if r["status"] != 200:
        add(findings, "WARN", "site", f"sitemap {url}: HTTP {r['status']}")
        return []
    body = r["body"]
    locs = re.findall(r"<loc>\s*(.*?)\s*</loc>", body, re.S)
    if "<sitemapindex" in body and depth < 1:
        add(findings, "PASS", "site", f"sitemap index {url}: {len(locs)} sitemaps")
        out = []
        for child in locs[:3]:
            out += read_sitemap(child, findings, depth + 1)
        return out
    lastmods = re.findall(r"<lastmod>\s*(.*?)\s*</lastmod>", body, re.S)
    add(findings, "PASS" if locs else "WARN", "site",
        f"sitemap {url}: {len(locs)} URLs, {len(lastmods)} with lastmod")
    if len(locs) > 50000:
        add(findings, "FAIL", "site", f"sitemap {url}: over 50,000 URLs (the per-file limit)")
    if len(lastmods) > 20 and len(set(lastmods)) == 1:
        add(findings, "WARN", "site", f"sitemap {url}: every lastmod is {lastmods[0]}: "
            "a build date, not content dates, so crawlers learn to ignore it")
    hosts = {urllib.parse.urlsplit(l).netloc for l in locs[:500]}
    if any(h.startswith(("localhost", "127.")) or "staging" in h for h in hosts):
        add(findings, "FAIL", "site", f"sitemap {url}: URLs on {', '.join(sorted(hosts))}")
    return locs


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("url")
    ap.add_argument("--pages", type=int, default=1)
    ap.add_argument("--no-bots", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    url = args.url if re.match(r"https?://", args.url) else "https://" + args.url
    findings = []
    page, raw = audit_page(url, findings, main=True)
    final = urllib.parse.urlsplit(raw["url"])
    origin = f"{final.scheme}://{final.netloc}"
    if final.scheme != "https":
        add(findings, "WARN", "site", "page is served over http, not https")
    site, locs = audit_site(origin, final.path or "/", findings)

    bots = []
    if not args.no_bots and raw.get("status") == 200:
        bots = audit_bots(raw["url"], raw["status"], raw["body"], findings)

    pages = [page]
    seen = {raw["url"].rstrip("/"), url.rstrip("/")}
    for loc in locs:
        if len(pages) >= args.pages:
            break
        if loc.rstrip("/") in seen or not loc.startswith(origin):
            continue
        seen.add(loc.rstrip("/"))
        sub = []
        info, _ = audit_page(loc, sub)
        for f in sub:
            f["area"] = "page:" + urllib.parse.urlsplit(loc).path
        findings += sub
        pages.append(info)

    if args.json:
        print(json.dumps({"url": url, "origin": origin, "site": site, "bots": bots,
                          "pages": pages, "findings": findings}, indent=2, ensure_ascii=False))
        return 0

    print(f"# Audit of {url}\n")
    order = {"FAIL": 0, "WARN": 1, "PASS": 2}
    areas = list(dict.fromkeys(f["area"] for f in findings))
    for area in areas:
        print(f"\n## {area}")
        for f in findings:
            if f["area"] == area:
                print(f"  {f['level']:<4}  {f['msg']}")
    if page.get("outline"):
        print("\n## outline (h2/h3 of the main page)")
        for o in page["outline"]:
            print(f"  {o}")
    counts = {k: sum(1 for f in findings if f["level"] == k) for k in order}
    print(f"\n{counts['FAIL']} FAIL, {counts['WARN']} WARN, {counts['PASS']} PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
