# Backlinks reference

How to get link data, read it with `scripts/backlinks.py`, and earn better
links. Sections:

1. Why links matter here
2. Where the data comes from
3. Running the analysis
4. Reading the results
5. Earning links
6. What not to do, and disavow

## 1. Why links matter here

Links from other sites are still one of the main ways Google finds pages and
judges which ones to rank. Because ChatGPT, Copilot, Perplexity and AI
Overviews retrieve from search indexes, pages that rank also get retrieved and
quoted more. The sites that link to a brand are also often the sites the
assistants cite when they talk about it.

So the link plan and the off-site plan in `references/visibility.md` are one
list. A domain that is both in the link gap and among the domains the
assistants cite for the user's prompts is the top target.

What counts is relevant, editorial links from real sites: the number of
distinct referring domains, not the raw link count, and how well the topic
matches. Tool metrics (Domain Rating, Authority Score, Domain Authority) are
each vendor's own estimate. Use them to sort, not as a goal, and never as
Google's numbers.

## 2. Where the data comes from

No single source is complete, and every tool sees a different part of the
web. Use what the user has; the script reads them all and merges them.

**The site's own links, free:**

| Source | What it gives | Notes |
|---|---|---|
| Google Search Console → Links | top linking sites, top linked pages, top linking text | Domain-level exports, a sample. No per-link anchor or rel. Needs a verified property. |
| Bing Webmaster Tools → Backlinks | source URL, anchor, target | Per-link rows. Needs a verified site (it can import from Search Console). |
| Ahrefs Webmaster Tools | full Ahrefs backlink data for verified sites | Free with verification. Export the backlinks or referring domains. |

**Competitors' links** usually need a paid tool (Ahrefs, Semrush, Moz,
Majestic) or their limited free versions. Ahrefs' free backlink checker shows
the top links of any domain, enough for a first gap. Ask whether the user
has access to one of these before suggesting they pay.

**Exports to ask for:**

- **The site:** the backlinks export (one row per link, with anchor and
  nofollow), plus the referring domains export if the backlinks one is
  capped.
- **Each competitor:** the referring domains export.
- **Search Console:** the "Top linking sites" CSV.

Ask the user to drop the files in `.seo/<domain>/links/`.

## 3. Running the analysis

```bash
python3 <skill-dir>/scripts/backlinks.py links/ahrefs-backlinks.csv links/gsc-top-linking-sites.csv \
  --site example.com --brand "Example,Exemplo" --keywords "app de agendamento,booking app" \
  --competitor booksy=links/booksy-rd.csv --competitor trinks=links/trinks-rd.csv \
  --check-targets --out .seo/<domain>/links > .seo/<domain>/backlinks.txt
```

- **Columns are matched loosely.** Exports from different tools can be mixed:
  the same link found by two tools is counted once. Domain-level rows (Search
  Console, referring-domain exports) are never added to the URL-level rows
  for the same domain. The larger count wins.
- **`--brand` and `--keywords` drive the anchor classes.** Pass the brand's
  names and spellings, and the commercial terms the site wants to rank for.
- **`--check-targets`** fetches every linked page of the site, up to 300, and
  lists the ones that 404 or redirect more than once.
- **`--out`** writes `domains.csv`, `targets.csv` and `gap.csv` for the
  report and for outreach.

## 4. Reading the results

- **Referring domains** over time is the core number. Compare with
  competitors' referring-domain counts from the same tool, never across tools.
- **Follow vs nofollow/ugc/sponsored.** A healthy profile has both. Nofollow
  links from cited sites (Reddit, Wikipedia, news) still matter for
  discovery and for AI answers.
- **Pages that earn links.**
  - If almost every link points to the home page, the deep pages (pricing,
    guides, tools) have no authority of their own. Internal links from the
    home page to them help.
  - Pages with links that are weak in search should be improved, not moved.
- **Links to reclaim.** Linked pages that 404 or redirect in chains are the
  fastest win in link building. Give each one a single 301 to the most
  relevant live page; never redirect them all to the home page, which Google
  treats as a soft 404. Restore the page if it still has a purpose.
- **Lost links.** Check the high-value ones: a moved page, a redesign or an
  expired partnership can often be recovered with one email.
- **Anchors.** Natural profiles are mostly branded, URL and generic anchors.
  A large share of exact-match commercial anchors ("app de agendamento") is
  the pattern Google's link spam systems look for. If the user built those
  links, stop. Don't "fix" the ratio by building more links.
- **Patterns.**
  - Site-wide footer or blogroll links, and one domain owning a big share of
    all links: fine when editorial (a partner, a sister company), a risk when
    paid.
  - Spam-looking domains: usually noise that Google ignores (see section 6).
- **The gap.** Domains that link to two or more competitors but not to the
  site have already shown they link to this category. Rank them by:
  1. Relevance: would the user's customers read that site?
  2. Whether the assistants cite it (`prompts.md`).
  3. The tool's authority metric.

  For each target, find out *why* it links to the competitors: a review, a
  listicle, an integration directory, a guest post, a news story, a
  sponsorship. That tells you what kind of page or pitch would earn the same
  link.

## 5. Earning links

In order of effort:

1. **Reclaim.** Fix the broken and chained targets from the analysis. Ask
   for lost links back where the page still exists.
2. **Unlinked mentions.** Search for the brand without its site
   (`"Example" -site:example.com`, Google Alerts, the social listening the
   user already has). Ask the authors to link to the right page and, while
   at it, to fix any wrong facts (feed the claim ledger in
   `references/visibility.md`).
3. **Owned relationships.**
   - Integration partners' app directories and marketplaces.
   - Suppliers and customers who show the tools they use (case studies,
     "powered by").
   - Associations, chambers of commerce, universities, events the business
     already takes part in.
4. **The gap list.** Pitch the editors of the reviews, comparisons and
   directories that cover the competitors. Bring facts, access to the
   product, and something the current piece lacks. Keep emails personal and
   short, and accept a "no".
5. **Linkable assets.**
   - Original data: a yearly survey, a pricing index, a benchmark from
     anonymized product data.
   - Free tools, calculators, templates.
   - Definitive guides on the problems the prompts revealed.

   These earn links and citations at the same time.
6. **Digital PR and expert commentary.**
   - Answer journalists' requests on topics the user really knows.
   - Comment on news in the niche.
   - Appear on podcasts.
7. **Broken link building.** Find resource pages in the niche that link to
   dead pages, and offer the user's page when it really replaces the dead
   one.

Write each outreach target into the report as: site, page, why it matters
(gap, cited for prompt N, authority), angle, contact, status.

## 6. What not to do, and disavow

Against Google's spam policies, and risky for the brand:

- buying or selling links that pass ranking credit
- link exchanges at scale
- private blog networks
- guest posting at scale with keyword anchors
- widgets or themes with hidden links
- automated comments and profiles
- paid links that are not marked `rel="sponsored"`

Google's systems mostly neutralize these links, so they waste money at best
and bring a manual action at worst. The same goes for fake accounts or seeded
threads on Reddit and forums.

**Disavow** is rarely needed. Google already ignores most spammy links that
point at a site. Recommend the disavow file only when:

- Search Console shows a manual action for unnatural links, or
- the user knows someone bought or built manipulative links for the site.

Disavowing good links by mistake can hurt rankings. Never recommend it just
because a tool rates a domain "toxic".
