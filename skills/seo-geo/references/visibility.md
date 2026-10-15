# Visibility reference

How to measure presence in AI answers and in search, how to read the results,
and how to grow presence off the site. Sections:

1. The prompt portfolio
2. Running the prompts
3. What to record
4. The claim ledger
5. Cited sources and off-site plan
6. Search Console
7. Keyword research without paid tools
8. Attribution
9. Re-measuring and changes over time

## 1. The prompt portfolio

Write 15–30 prompts for a first run (more for large sites). Draw them from
the user's answer to "what would a buyer ask", sales and support questions,
reviews, Search Console queries and People Also Ask.

**Intent families.** Cover the ones that lead to revenue:

| Family | Example |
|---|---|
| Discovery | "melhor app de agendamento para barbearia" |
| Problem | "como reduzir faltas de clientes na barbearia" |
| Best for | "best booking app for a barbershop with 3 chairs" |
| Comparison | "Example vs Booksy", "alternatives to Booksy" |
| Trust | "is Example reliable", "does Example have LGPD compliance" |
| Price and compatibility | "how much does Example cost", "does Example work with WhatsApp" |
| Implementation | "how to set up online booking for a barbershop" |
| Brand | "what is Example" |

Write them the way people type into a chat: full sentences, context ("I have
a small barbershop in São Paulo..."), in each market language.

**Three cohorts:**

- **Core** (most prompts): stable and versioned. This is what gets reported
  over time. Only compare periods that used the same core version.
- **Exploratory:** rotates. It tests new angles and promotes good ones to the
  core.
- **Controls:**
  - prompts where the brand should always appear ("what is Example")
  - prompts where it should never appear (an unrelated category)

  If the controls move, the engine or the method changed, not the site.

**Multi-turn journeys.** For the 2–3 most valuable discovery prompts, add 2–3
follow-ups that mirror a purchase: shortlist → compare → validate → choose.
Record the turn where the brand falls off the shortlist; that turn shows the
content gap.

Save the portfolio in `prompts.md` with a version number.

## 2. Running the prompts

Engines, in order of usual importance (adjust to the market): ChatGPT (with
search), Google AI Overviews and AI Mode, Gemini, Perplexity, Copilot, Claude.

- **Run fresh.** Use a new chat for each prompt, logged out or with memory
  off where possible, and note the locale.
- **Run each core prompt 3–5 times per engine.** Report a rate with the
  sample size ("mentioned in 3/5"), not a yes or no. Answers vary between
  runs.
- **How to collect the answers:**
  1. With a browser tool, use the user's logged-in sessions only after they
     agree.
  2. Use APIs with web search (OpenAI Responses with web search, Perplexity
     Sonar, Gemini with Google Search grounding) when the user has keys and
     agrees to the cost. API answers differ from the consumer apps; label
     them.
  3. Otherwise, give the user the list as a checklist and fill the table
     from what they paste back.
- **Your own web search tool is a proxy.** It shows which pages rank and get
  cited, not what ChatGPT says. Label proxy results "Proxy".
- **ChatGPT fan-out.** With a browser, open DevTools → Network on a ChatGPT
  answer and search the conversation payload for `queries`. That shows the
  searches ChatGPT actually ran. If they look like `site:g2.com ...`, the
  brand's profiles on those sites matter more than a new page.

## 3. What to record

One row per prompt × engine × run:

| Field | Values |
|---|---|
| prompt id, cohort, engine, date, locale | |
| ladder | not present / retrieved (in sources, not in text) / cited / mentioned / recommended / recommended against |
| position | the order among the brands named |
| framing | favorable / neutral / hedged / negative |
| cited URLs | own and third-party |
| competitors | named and recommended |
| wrong or stale claims | go to the claim ledger |

Report the ladder per engine ("cited in 4/20 core prompts on Perplexity,
recommended in 1/20"), never one blended "AI visibility score": a single
number hides which fix matters and invites tracking noise. When a number is
shown, label its kind: **Measured** (you ran it), **User-provided**,
**Estimated**, **Proxy** or **Unknown**.

## 4. The claim ledger

Wrong facts in AI answers cost sales and show which sources the assistants
trust. Keep one row per claim:

| Engine | Date | Prompt | Claim | Verdict | Likely source | Severity | Fix | Owner |
|---|---|---|---|---|---|---|---|---|

Verdicts:

- accurate
- incomplete
- ambiguous
- stale
- false
- opinion stated as fact
- unverifiable

Severity is impact (price, availability, safety and compliance are high)
times how often the claim appears.

Fix in this order:

1. The owned source: the page, the schema, the pricing.
2. Owned profiles: Google Business Profile, G2/Capterra, Crunchbase,
   LinkedIn, app stores, marketplaces.
3. Third parties: ask for factual corrections only, with evidence.

Retest after 4–8 weeks.

## 5. Cited sources and off-site plan

Classify every cited domain:

- **Owned:** the brand's own site.
- **Competitor:** a competitor's site.
- **Earned editorial:** independent media, reviews, listicles.
- **Institutional:** government, universities, standards bodies.
- **PR wire.**
- **Community:** Reddit, forums, YouTube, social.
- **Marketplace or review platform:** G2, Capterra, Trustpilot, Reclame Aqui,
  app stores, Google Maps.

Split the counts by engine; engines differ a lot in how much they cite brand
sites. The domains cited across many prompts are the off-site targets.

What to do there:

- **Consistent entity everywhere.** Every profile describes the brand the way
  its About page does: name, category, what it does, price range, location.
  Fill `sameAs` with them.
- **Review platforms** where the category's buyers look. Ask real customers
  for reviews, all customers and not only happy ones. Answer reviews.
- **Earned mentions.** Pitch the editors of the listicles and comparisons
  the engines cite, with facts and access to the product. Publish original
  data worth citing.
- **Community.** Take part openly as the brand or as a disclosed employee.
  Answer questions well, including when the answer is not your product.
  Never use fake accounts, seeded threads or paid undisclosed posts.
- **Video.** YouTube demos and comparisons are cited for how-to and
  comparison prompts.
- **Wikipedia and Wikidata** only if the brand meets the notability rules.
  Never write your own Wikipedia article; a Wikidata item with accurate facts
  is fine.
- **Local businesses:** a complete Google Business Profile (categories,
  hours, photos, services, products), the same name, address and phone
  everywhere, and the directories of the trade.

## 6. Search Console

With access to Search Console (an export or the API), its data is the best
classic-SEO input there is. Pull 3–16 months by query and page.

- **Opportunity buckets by average position:**
  - **1–3, low CTR.** Compare with the site's own CTR curve (the 75th
    percentile CTR per position bucket). Rewrite the title and description.
  - **4–10.** Quick wins: improve the page, add internal links.
  - **11–20, page two.** Rank by impressions × clamp((21 − position) / 10,
    0.1, 1), keeping only queries with at least 50 impressions. These need
    content work.
- **AI Overview pressure.** Look for queries where CTR fell more than 20%
  while impressions held (last 28 days vs the previous 28). Check each one:
  does an AI Overview cite the site, cite a competitor, or not appear? Fix
  the ones where a competitor is cited. Check again at 7, 14 and 28 days.
- **Content decay.** Split a page's drop into lost impressions (ranking or
  demand) and lost CTR (the results page changed).
- **Cannibalization.** Several pages getting impressions for the same query.
  Merge them or make each target its own intent before editing either.
- **API quirk.** The API has no position filter: pull a large `rowLimit` and
  filter locally.

## 7. Keyword research without paid tools

- **Expand seeds** with Google autocomplete (per locale), People Also Ask,
  related searches, and modifiers: best, vs, alternatives, price, for
  <audience>, near me, how to.
- **Cluster by results-page overlap.** Count how many of the top-10 URLs two
  keywords share:

  | Shared top-10 URLs | Meaning |
  |---|---|
  | 7–10 | same page |
  | 4–6 | same cluster |
  | 2–3 | separate pages that link to each other |
  | 0–1 | separate topics |

- **Demand without a paid tool.** Search Console impressions are Measured.
  Autocomplete presence, Google Trends and Wikipedia pageviews are Proxy;
  never quote them as search volume.
- **Priority:** volume × intent value ÷ difficulty. Do the bottom-of-funnel
  terms (price, vs, alternatives, for <use case>) first when the goal is
  revenue.

## 8. Attribution

AI traffic is mostly invisible in analytics. Two vendor studies (Profound,
2026; SimilarWeb) found that most visits after an AI recommendation carry no
AI referrer and arrive later as direct or branded search. So:

- **Group AI referrers** into one analytics channel: chatgpt.com,
  perplexity.ai, gemini.google.com, copilot.microsoft.com, claude.ai, and
  `utm_source=chatgpt.com`.
- **Watch branded search and direct visits** in 1-hour, 24-hour and 7-day
  windows after changes or campaigns.
- **Ask.** Add "Where did you hear about us? (ChatGPT, Google...)" or "What
  did you ask the AI?" to sign-up and contact forms. It is the most reliable
  signal there is.
- **Log analysis.** Server or CDN logs show which pages the AI bots read,
  and how often.

## 9. Re-measuring and changes over time

- Save the baseline (`prompts.md`, `audit.txt`, a Search Console export)
  before changing anything.
- Re-run the core prompts and the audit 4–6 weeks after the fixes ship.
  Indexing and assistant caches lag; 30 days is the earliest anything shows.
- Compare like with like: the same prompt version, engines, locale and number
  of runs. A Google update or a model change in the same window is a
  confounder, not a cause; say so.
- Change one major thing per page at a time where possible. For each
  recommendation, write down the leading indicator (crawled, indexed, cited)
  and how you would know it failed.
- **For a site migration or redesign:**
  - Before the switch: crawl the old site, keep a 1:1 redirect map, keep the
    old metadata and schema, and confirm there is no `Disallow: /` and no
    staging `noindex`.
  - After the switch: diff against the old site at T+1, T+7 and T+30 days.
    Flag pages that drop more than 30% at T+7, and roll back if more than 5%
    of old URLs return 404.
