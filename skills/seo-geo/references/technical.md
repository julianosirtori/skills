# Technical reference

How to read each `audit.py` finding and fix it. Sections:

1. Crawlers: which bot decides what
2. robots.txt policies
3. CDN and WAF bot blocking
4. JavaScript rendering
5. Indexability and Google's AI features
6. Metadata, headings, links
7. Structured data
8. Sitemaps and index submission
9. International sites
10. Core Web Vitals
11. llms.txt and Markdown for agents
12. Framework recipes

## 1. Crawlers: which bot decides what

Each claim maps to one bot. Mixing them up is the most common error in SEO
advice about AI: blocking GPTBot does **not** remove a site from ChatGPT
search (OAI-SearchBot decides that), and blocking Google-Extended does **not**
remove it from AI Overviews (Googlebot decides that).

| Token | Owner | Decides | Honors robots.txt |
|---|---|---|---|
| Googlebot | Google | Google Search, AI Overviews, AI Mode | yes |
| Google-Extended | Google | robots token only: Gemini apps' training and grounding. Not a crawler; no effect on Search or AI Overviews | yes |
| Bingbot | Microsoft | Bing, Copilot; Bing's index also feeds other assistants | yes |
| OAI-SearchBot | OpenAI | ChatGPT search results and citations | yes |
| ChatGPT-User | OpenAI | fetching a page a ChatGPT user or GPT asked for | OpenAI says it may not apply |
| GPTBot | OpenAI | training only | yes |
| Claude-SearchBot | Anthropic | Claude search | yes |
| Claude-User | Anthropic | fetching a page a Claude user asked for | yes (Anthropic docs) |
| ClaudeBot | Anthropic | training only | yes |
| PerplexityBot | Perplexity | Perplexity index and citations | yes |
| Perplexity-User | Perplexity | fetching on a user's request | generally not |
| Applebot | Apple | Siri, Spotlight, Safari suggestions | yes |
| Applebot-Extended | Apple | robots token only: Apple's training opt-out; not a crawler | yes |
| meta-externalagent | Meta | Meta AI | yes |
| CCBot | Common Crawl | open crawl many models train on | yes |

Google also has user-triggered fetchers (Google-Agent, Google-GeminiNotebook,
Google Messages link previews) that ignore robots.txt. Privacy needs
authentication, never robots.txt. Brave Search does not crawl what Googlebot
is not allowed to crawl, so blocking Googlebot also hides the site from
assistants that use Brave's index.

The vendors publish their bots and IP ranges: platform.openai.com/docs/bots,
Anthropic's help article on its crawlers, docs.perplexity.ai,
developers.google.com/search/docs/crawling-indexing/google-common-crawlers.
The bot list changes every few months; check those pages before stating a
fact about a bot as current.

## 2. robots.txt policies

Rules (RFC 9309 and Google's implementation): a crawler obeys only the most
specific group that names it and does not also read `*`. The longest matching
path wins, and `Allow` wins ties. So a `User-agent: GPTBot` group that only
says `Disallow: /private` lets GPTBot crawl everything else, even when `*`
disallows more.

**Visibility first (the default):**

```text
User-agent: *
Allow: /
Disallow: /admin/
Disallow: /api/

Sitemap: https://example.com/sitemap.xml
```

**Be cited, stay out of training:**

```text
User-agent: GPTBot
User-agent: ClaudeBot
User-agent: Google-Extended
User-agent: Applebot-Extended
User-agent: CCBot
User-agent: meta-externalagent
Disallow: /

User-agent: *
Allow: /
Disallow: /admin/

Sitemap: https://example.com/sitemap.xml
```

Common accidents:

- `Disallow: /` left over from staging.
- An "AI blocker" template or security plugin that lists OAI-SearchBot,
  Claude-SearchBot and PerplexityBot along with the training bots.
- Blocking `/_next/`, `/static/` or the CSS/JS that Google needs to render.
- robots.txt answering 5xx, which makes Google treat the whole site as
  disallowed, or redirecting to a login page.
- **A Cloudflare managed block.** `audit.py` flags `# BEGIN Cloudflare
  Managed content`. Cloudflare adds it to the served file, so it is not in the
  owner's repo, and it disallows GPTBot, ClaudeBot, Google-Extended,
  Applebot-Extended, CCBot and others. It is critical when the owner meant to
  allow them.
- **`Content-Signal:` lines** (Cloudflare's content signals policy):
  `search=`, `ai-input=` (use in answers, grounding) and `ai-train=`. They
  state preferences; robots rules still decide access. `search=no` or
  `ai-input=no` work against being cited.

robots.txt controls crawling, not indexing. To keep a page out of results,
let it be crawled and serve `noindex`. A disallowed URL can still be indexed
from links, just without its content.

## 3. CDN and WAF bot blocking

When `audit.py` shows a bot getting 403/429/503 or a challenge page while the
browser gets 200, look at the edge before the code:

- **Cloudflare.** Since mid-2025 new zones block AI crawlers by default.
  Check AI Crawl Control ("Block AI bots"), Bot Fight Mode and Super Bot Fight
  Mode, managed robots.txt, WAF custom rules and rate limits. Verified bots
  can be allowed by category.
- **Vercel, Netlify, AWS WAF, Akamai, Fastly, Sucuri.** Bot protection,
  attack challenge modes, rate limiting.
- **WordPress.** Security plugins (Wordfence and others) and host firewalls.

The script spoofs the user-agent from this machine. A CDN that verifies bots by
IP (or by Web Bot Auth signatures, RFC 9421) may block the spoof and let the
real bot in, or the other way round. Report it as "likely blocked, confirm in
<CDN> settings", then confirm in the server or CDN logs: filter by bot name
and status code. The logs also show whether the bots come at all and which
pages they read.

## 4. JavaScript rendering

Most AI crawlers download the HTML and do not run JavaScript. Googlebot renders
JS in a second pass, later and with limits. If `audit.py` reports few words
and an app root (`#root`, `#__next`, `#app`), the public pages must render on
the server.

Google's JavaScript rules (Search Central, updated December 2025):

- If the canonical in the raw HTML differs from the one JavaScript sets,
  Google may use either. Put the right one in the raw HTML.
- A `noindex` in the raw HTML may be honored even if JavaScript removes it.
- Google does not render pages that return a status other than 200.
- Structured data injected by JavaScript may be processed late.

With a browser tool, compare the raw HTML (`view-source:` or `curl`) with the
rendered DOM for title, canonical, meta robots, H1 and JSON-LD. A difference
in any of these is a finding.

Fixes:

- **Next.js.** App Router pages are server components by default. The usual
  culprits are `"use client"` at the top of a page, data fetched in
  `useEffect`, and `dynamic(..., { ssr: false })`. Fetch on the server.
- **Vite or CRA single-page apps.** Move the public pages to a framework with
  SSR or SSG (Next.js, Astro, React Router/Remix, Nuxt, SvelteKit), or
  pre-render them at build time. Keep the logged-in app as an SPA.
- **Tabs, accordions and "load more".** Their content must be in the HTML,
  not fetched on click.
- **Check.** `curl -sA "GPTBot" <url> | grep -c "<a key phrase>"`, or
  view-source, never the inspector.

## 5. Indexability and Google's AI features

- **Status.** 200 for real pages. 404/410 for gone ones: a 200 "not found" page
  is a soft 404. 301/308 for permanent moves, at most one hop. Fix internal
  links to point at the final URL.
- **noindex.** In `<meta name="robots">` or the `X-Robots-Tag` header, it
  removes the page. Frameworks often add it outside production; check that the
  production build does not.
- **Canonical.** One absolute URL, self-referencing unless the page is a
  deliberate duplicate. Typical bugs: every page canonical to the home page,
  http or staging hosts, query strings, a trailing slash that disagrees with
  the redirects.
- **One host.** http → https, and non-www ↔ www to a single host.
- **First 2 MB.** Googlebot reads only the first 2 MB of an HTML file (64 MB
  for PDFs). Keep the content and the JSON-LD above that.
- **Pagination.** Google has ignored rel=next/prev since 2019. Give every page
  of a series a self-referencing canonical and plain `<a href>` links.
- **Google AI Overviews and AI Mode** use only pages that are indexed and
  eligible for a snippet. `nosnippet`, `max-snippet` and `data-nosnippet`
  limit what they can quote. Search Console reports on these surfaces and,
  from 2026, has settings for generative AI features. Read Google's current
  docs before advising on them: they are new and move fast.

## 6. Metadata, headings, links

- **Title.** Unique per page. About 50–60 characters, or roughly 580 px wide.
  What is searched for first, brand last:
  `Agendamento online para barbearias | Marca`. Look at the current top
  results for the query and match the pattern that wins. Google rewrites
  titles that are stuffed, boilerplate, or don't match the H1.
- **Meta description.** About 140–160 characters, specific, with a reason to
  click. Google rewrites it often. Watch for templated descriptions (all
  starting with the title, all ending with the same CTA).
- **H1.** One H1 that says what the page is. A few extra H1s from a theme are
  not a problem worth reporting.
- **H2 and H3.** An outline someone could skim. Phrase H2s as the question the
  section answers where that reads naturally.
- **lang.** On `<html>`, matching the content.
- **Open Graph.** `og:title`, `og:description` and a 1200×630 `og:image`, for
  link previews in chats and social.
- **Dates.** Show "Updated <date>" on content that ages, and keep
  `dateModified` honest. Assistants favor fresh sources for time-sensitive
  questions. Bumping dates without changing anything is a manipulation
  signal.
- **Images.** A descriptive `alt`, real filenames, `width`/`height` set.
- **Internal links.**
  - Every important page within 3 clicks of home.
  - No orphan pages: in the sitemap but linked from nowhere.
  - Descriptive anchor text.
  - A new page launches with links from at least 3 relevant existing pages.
- **URLs.** Short, lowercase, hyphenated and stable. Flag URLs over about
  100 characters.

## 7. Structured data

Use JSON-LD in a `<script type="application/ld+json">`. Mark up only what is
visible on the page and true. Schema that describes hidden or invented content
(ratings with no reviews shown) is spam.

Validate with the Rich Results Test (Google features) and validator.schema.org
(syntax). Before reporting "no schema", check the rendered page: WordPress SEO
plugins and tag managers often inject JSON-LD with JavaScript, which a raw
fetch misses.

**Valid schema.org markup is not the same as a Google rich result.** Google has
retired many rich results:

| Feature | Status |
|---|---|
| FAQ rich results | gone for all sites since May 7, 2026 (limited to government and health sites from 2023) |
| HowTo | retired September 2023 |
| Sitelinks search box | retired November 2024; WebSite markup still sets the site name |
| CourseInfo, EstimatedSalary, LearningVideo, ClaimReview, VehicleListing | retired June 2025 |
| SpecialAnnouncement | retired July 2025 |

Keep existing FAQPage markup: it is harmless, and other parsers read it. Report
it as information, not as a problem. Use QAPage for real user Q&A. Recommend
schema for clear entity facts, not as a promised rich result or AI ranking
boost: no published evidence shows that schema by itself raises AI citations.

**Organization (home page).** `sameAs` ties the brand to its profiles and
connects the entity across the web:

```json
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "@id": "https://example.com/#org",
  "name": "Example",
  "url": "https://example.com/",
  "logo": "https://example.com/logo.png",
  "description": "One factual sentence: what it is, for whom.",
  "foundingDate": "2021",
  "sameAs": [
    "https://www.linkedin.com/company/example",
    "https://www.instagram.com/example",
    "https://github.com/example",
    "https://www.wikidata.org/wiki/Q000000"
  ],
  "contactPoint": {"@type": "ContactPoint", "contactType": "customer support", "email": "help@example.com"}
}
```

**WebSite.** `@id` `/#website`, `name`, `url`, and `publisher` pointing to the
Organization. It sets the site name shown in results.

**SoftwareApplication (SaaS and apps):**

```json
{
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "Example",
  "applicationCategory": "BusinessApplication",
  "operatingSystem": "Web, iOS, Android",
  "offers": {"@type": "Offer", "price": "49.00", "priceCurrency": "BRL"},
  "publisher": {"@id": "https://example.com/#org"}
}
```

**Product (physical goods).** `name`, `image`, `description`, `sku`, `brand`
and `offers` (`price`, `priceCurrency`, `availability`). Merchant listings
also want shipping details and `hasMerchantReturnPolicy`, where
`returnPolicyCountry` has been required since March 2025. Add
`aggregateRating` and `review` only when the reviews are shown on the page.

**LocalBusiness**, or a subtype such as `Dentist` or `HairSalon`. `name`,
`address`, `geo`, `telephone`, `openingHoursSpecification`, `areaServed` and
`priceRange`. Use exactly the same name, address and phone as the Google
Business Profile.

**Article and BlogPosting.** `headline`, `author` (a `Person` with `url` and
`sameAs`), `datePublished`, `dateModified`, `image` and `publisher`.

**BreadcrumbList** on deep pages.

## 8. Sitemaps and index submission

**Sitemap rules:**

- Only canonical, indexable URLs that return 200.
- At most 50,000 URLs or 50 MB uncompressed per file; use a sitemap index
  for more.
- `lastmod` changes only when the content does. `audit.py` flags a sitemap
  where every `lastmod` is the same, which is a build date. Google ignores
  `priority` and `changefreq`.
- Reference the sitemap in robots.txt.
- Compare it with the internal links to find orphan pages.

**Submission:**

- Verify **Google Search Console**. Use the Page indexing reasons and URL
  Inspection with the rendered HTML.
- Verify **Bing Webmaster Tools**. Bing's index feeds Copilot and other
  assistants. It can import the Search Console setup.
- **IndexNow** pings Bing, Yandex, Naver, Seznam and others when URLs change.
  Many CMSs and CDNs support it natively. Google does not use it.
- **Google's Indexing API** is only for JobPosting and BroadcastEvent pages.
  Don't use it for ordinary pages.

## 9. International sites

- One URL per language (`/pt-br/`, `/en/`). Never switch language by cookie,
  IP or Accept-Language alone: crawlers mostly come from the US and would see
  one version.
- `hreflang` on every version, listing all versions **including itself**,
  with matching return links. A page whose canonical is not in its own
  hreflang set has all its hreflang ignored.
- Valid codes: `pt-BR`, `en-GB` (never `en-UK`). `x-default` is recommended.
- Never point a canonical from one locale to another.
- Next.js `alternates.languages` does not add the self-reference; add it.
- Translate titles, descriptions, slugs where reasonable, and the schema.

## 10. Core Web Vitals

Field data (CrUX, real users) at the 75th percentile is what counts. Lighthouse
lab data is for debugging. Check the phone numbers separately: the
all-devices view can hide a mobile failure.

| Metric | Good | Poor |
|---|---|---|
| LCP | ≤ 2.5 s | > 4.0 s |
| INP (replaced FID, March 2024) | ≤ 200 ms | > 500 ms |
| CLS | ≤ 0.1 | > 0.25 |
| TTFB (diagnostic) | ≤ 0.8 s | |

Split LCP into its four parts: TTFB, load delay, load duration and render
delay. Then fix the biggest one:

- **LCP image.** Use `fetchpriority="high"` and never lazy-load it. Preload
  it only when a trace shows it is discovered late.
- **Server.** Cache it.

For crawlers, the HTML response time is what matters most: slow pages get
fetched less, and AI user-fetch bots give up quickly.

## 11. llms.txt and Markdown for agents

`/llms.txt` was proposed in 2024 (llmstxt.org). It is Markdown:

- an H1 with the name
- a blockquote summary
- sections of links to the most useful pages, one line each

`/llms-full.txt` can hold the full text of the docs.

Google's Search Central changelog (June 15, 2026) says it is not needed for
Google Search and has no effect either way. Log studies find almost no AI bot
requests for it. It does help coding agents and tools that read docs. So:

- Give it no weight in any score.
- Add it when the user wants it or the product has developer docs.
- Say plainly what it does not do.

```markdown
# Example

> Example is an online booking tool for barbershops in Brazil. Plans from
> R$ 49/month. Integrates with WhatsApp and Google Calendar.

## Product
- [Features](https://example.com/features): what it does, with screenshots
- [Pricing](https://example.com/pricing): plans and limits

## Docs
- [Getting started](https://example.com/docs/start): setup in 10 minutes
```

**Markdown for agents** is optional and suits docs-heavy and developer
products. There are two ways to do it:

- Return Markdown when a request sends `Accept: text/markdown`, with
  `Vary: Accept`.
- Publish Markdown copies of key pages (`/pricing.md`) and point to them with
  a `Link` header or `<link rel="alternate" type="text/markdown">`.

## 12. Framework recipes

**Next.js (App Router).**

- Metadata per route with `export const metadata` or `generateMetadata`:
  `title`, `description`, `alternates.canonical`, `openGraph`, `robots`.
  Set `metadataBase` so URLs are absolute.
- Add `app/robots.ts` and `app/sitemap.ts`.
- Put JSON-LD in the page:
  `<script type="application/ld+json" dangerouslySetInnerHTML={{__html: JSON.stringify(data)}} />`.

**Astro.** Pages are static HTML by default. Use `@astrojs/sitemap`, and put
the metadata in the layout's `<head>` from frontmatter props.

**Nuxt.** `useSeoMeta`, `@nuxtjs/sitemap` and `@nuxtjs/robots`. Keep
`ssr: true`.

**SvelteKit.** `<svelte:head>`, and `prerender = true` for marketing pages.

**WordPress.** An SEO plugin (Yoast, Rank Math) handles titles, canonicals,
sitemaps and schema. Check its robots.txt editor and any security plugin that
blocks bots.

**Shopify, Wix, Webflow, Squarespace.**

- The platform manages robots.txt and the sitemap. Shopify allows
  `robots.txt.liquid`.
- Edit titles, descriptions and alt text in the admin.
- Add JSON-LD through the theme or custom code.

When you can't edit the site yourself, give the user exact steps.
