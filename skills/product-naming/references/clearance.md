# Vetting finalists

How to read the output of `inspect_domain.sh` and `vet_name.sh`, and how to
do the checks that can't be scripted. Everything here is a pre-screen: it
catches obvious conflicts early and cheaply. It is not legal clearance.

## Contents

- Taken domains: who holds them
- Search conflicts
- Search volume and SEO for brandable names
- Trademark pre-screen
- Social handles

## Taken domains: who holds them

`inspect_domain.sh name.com` gives one of these verdicts:

| Verdict | What it means | What to tell the user |
|---|---|---|
| FOR SALE via a marketplace (Atom, HugeDomains, BrandBucket, Afternic, Sedo, Dan...) | A domain investor holds it and lists it | It can be bought. The marketplace page shows the price; it ranges from hundreds to tens of thousands of US dollars. Furora.com was on Atom. |
| FOR SALE (page says so) | The owner put up a sale notice | Contact through the page, or use a broker. |
| PARKED | Registered, no real use, ads or placeholder | Probably for sale at the right price. A broker (Afternic, Sedo, GoDaddy's broker service) can ask without revealing who wants it. |
| NO RESPONSE | Registered, no website | Idle. Same as parked; the registration date and the registrar hint at whether the owner is a company or an individual. |
| REDIRECTS | Sends visitors to another brand | That brand uses it. Usually not for sale; check whether the brand is in the same category. |
| ACTIVE SITE | A real site | Open it. Same category: the name is out (a direct competitor, like PostKite.com for a social media tool). Different category: the .com is out, but the name may live on with a modifier or another extension; weigh the confusion risk. |
| UNCLEAR | Error page, or a page with no title | Open it in a browser and decide. |

**Registration date:**

- Registered long ago, with no site: a long-held investment, often for sale.
- Registered in the last year or two, with an active site: possibly a new
  competitor.

Look at what the site does.

## Search conflicts

For each finalist, search the name in quotes in each market. Look for three
problems:

1. **A competitor in the same category.** Examples from the reference run:
   Trend.io, PostKite and Buzz Krew. A company in an unrelated field is
   usually fine, unless it is famous.
2. **Correction to another word.** "Did you mean…", or results for a
   different word.
3. **Generic results that will compete with the name.** If the first page is
   about a common word, the brand will fight for its own name forever.

**Location matters.** Search tools available to agents often run from the
US and are not Google. They are good enough to find conflicts, but not to
judge the competition in Brazil or Europe. With a browser tool, open the
`google <locale>` links that `vet_name.sh` prints: they set the language and
country (`hl` and `gl`). Otherwise, tell the user which links to open and
what to look for.

## Search volume and SEO for brandable names

For a brandable name, the SEO goal is to own the search results for the
name, not to rank for a popular keyword. So low existing search volume for
the name itself is good: there is little to compete with, and every brand
search will land on the user's site.

What to look at:

- **Autocomplete** (in `vet_name.sh`):
  - No suggestions: a clean slate.
  - Suggestions that start with the name and are unrelated: someone already
    owns the term. Furora shows "furora yarns", "furora lighting".
  - Suggestions that steer away: an autocorrect problem.
- **Results for the name in quotes.** Few, unrelated results are good.
  Results dominated by one company mean that company owns the term.
- **Volume for the words inside a compound name** (kiosk, buzz). This is
  only useful if the brand wants to borrow their meaning; it's a side note
  for a brandable name.

There is no free keyless source of search volume. If a keyword tool is
connected (Google Ads Keyword Planner, Semrush, Ahrefs, DataForSEO through an
MCP server or API), use it for the name and its parts. Otherwise, tell the
user the numbers were not measured, and point to Google Trends
(`https://trends.google.com/trends/explore?q=NAME&geo=BR`) as a manual check.

## Trademark pre-screen

### Which classes matter

Trademarks are registered per Nice class: a conflict normally needs a similar
mark in an overlapping class. Pick the classes from the product:

| Product | Classes |
|---|---|
| Software, SaaS | 9 (downloadable software), 42 (SaaS, platforms, software development) |
| Mobile app | 9, 42, plus the class of the service the app delivers |
| Marketing, advertising, social media management | 35, plus 9 and 42 for the platform |
| E-commerce, marketplace | 35 (online retail, marketplace), 9 and 42 (platform), 39 if it delivers |
| Fintech, payments | 36, plus 9 and 42 |
| Online education | 41, plus 9 and 42 |

### Reading `vet_name.sh` output

- **USPTO.** It lists marks spelled like the name or one letter away
  (`postkite` found POSTBITE, live, in classes 9, 35 and 42). What to do with
  each hit:
  - Dead marks don't block.
  - A **live** mark that is identical or one letter away, **in an overlapping
    class**, is a likely blocker. Report it as a serious risk.
  - Live marks in unrelated classes are usually fine, unless the mark is
    famous.
- **INPI (Brazil).** It gives counts for the exact search and the radical
  search, and the first exact hits with status ("Registro", "Arquivado",
  "Extinto") and class. "Extinto" and "Arquivado" don't block. For a
  Brazil-relevant finalist with live hits, open the INPI search (below) and
  read the classes.
- **WIPO Global Brand Database.** The link that `vet_name.sh` prints runs a
  phonetic search across 89 sources, including the USPTO, INPI, EUIPO, UKIPO,
  Madrid, Japan, Korea, Canada, Mexico and Australia. It does not cover China
  or Argentina. Open it in a browser: it uses a bot check, so don't script it.
  Filter by the classes above.

### Manual searches, when needed

- **INPI.** busca.inpi.gov.br/pePI → "Continuar" (no login) → Marca →
  "Pesquisa Básica". "Exata" finds the exact mark. "Radical" finds marks
  containing it, and is much broader.
- **USPTO.** tmsearch.uspto.gov. Wildcards work (`name*`).
- **EUIPO and national EU offices.** TMview (tmdn.org/tmview) or EUIPO
  eSearch plus. Both are already covered by WIPO's database.

### How to report it

For each finalist, write one line: "no similar live marks found in classes 9,
35 or 42 at USPTO, INPI or WIPO", or list each conflict with its office,
status and class. Always add that a trademark attorney or agent should run a
full search in the target classes before the user invests in the brand.

## Social handles

- **GitHub and npm.** `vet_name.sh` checks these through their public APIs.
  GitHub allows 60 unauthenticated lookups per hour.
- **Instagram, TikTok, X, YouTube, LinkedIn.** They block automated checks or
  forbid them in their terms, and plain HTTP status codes don't separate an
  existing profile from a missing one. Open the links that `vet_name.sh`
  prints:
  - with a browser tool, if you have one;
  - otherwise, list the links for the user.

  A profile page that loads with posts is taken. "Sorry, this page isn't
  available" or "Couldn't find this account" means free, or banned and
  unavailable.

When the exact handle is taken (often by an inactive account), list usable
alternatives in the report: `getname`, `name.app`, `nameapp`, `namehq`,
`usename`. Note whether the holder is active and in the same category. For
social and consumer products, the Instagram and TikTok handles weigh as much
as the domain.
