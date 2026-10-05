---
name: product-naming
description: Find a brandable name for a product, app, SaaS, startup or company and check that it can really be owned. Generates hundreds of candidates in batches by naming strategy, bulk-checks domains straight from the registries (RDAP/whois for .com, .com.br, .ai, .io, .app and more, self-tested so a broken check never calls a taken domain free), filters names by meaning, sound and spelling in every market language, scores fit and marketing potential, then vets the finalists - who owns a taken .com and whether it is for sale, Google autocomplete and search conflicts, USPTO/INPI/WIPO trademark pre-screen, social handles - and delivers a ranked shortlist. Use this whenever the user wants a name for something they are launching, asks if a domain is free or who owns it, wants alternatives to a taken name, or wants to vet a name they already like, even if they never say "naming" (e.g. "preciso de um nome pro meu app", "esse domínio tá livre?", "acha um nome melhor que esse", "what should I call my startup?").
license: MIT
compatibility: Scripts need bash (stock macOS 3.2 is fine), curl and jq; whois and perl for extensions without RDAP; iconv for the INPI search. Network access required. A browser tool, if available, helps with Google per country and social handles.
metadata:
  author: julianosirtori
  version: "1.0.0"
---

# Product Naming

Find a name that people remember, that feels like the brand, and that the user
can actually own: the domain, the trademark, the handles and the search results.

Names are cheap to generate and expensive to own. In the run this skill was
built from, about 870 candidates were tested. Nearly every single word, obvious
compound and "hey/meet + name" was taken as a .com. Of the few that were free,
many then died on a language or search filter. So generate wide, let the
scripts do the cheap checks in bulk, and spend judgment only on the survivors.

Talk to the user and write the report in the user's language.

## What a good name is here

**The name does not need to say what the product does.** Descriptive names
(PostScheduler, Agência do Bairro) are almost never free. They make weak
trademarks: offices refuse or narrow them. They drown in generic search results,
and the company outgrows them when the product changes. Prefer brandable names,
unless the user asks for a descriptive one:

- arbitrary words: Apple, Slack, Notion
- evocative words: Nike, Patagonia
- invented words: Kodak, Spotify
- unexpected combinations: Mailchimp, Dropbox

What the name needs instead:

- **Fit (aderência).** It feels like the brand. Its sound, rhythm and
  associations match the personality and the promise: calm or energetic,
  premium or playful, expert or friendly. The audience would say it out loud
  without embarrassment. Fit comes from the feeling the name gives, not from a
  description of features.
- **Stickiness.** Heard once, it is remembered the next day and typed correctly.
- **Marketing potential.** You can build a story, a visual identity, a tone of
  voice and campaigns around it. It can become a verb or a name for the
  community. It does not box the company into one feature or one market.

`references/criteria.md` turns these qualities into filters and a scorecard.

## Working folder

Keep the run in `naming/<slug>/` in the current directory. If that directory
is a code repo the user would not want touched, use a temp directory instead.

```text
naming/<slug>/
├── brief.md               # answers from step 2
├── candidates/NN-<strategy>.txt  # one name per line
├── results/NN-<strategy>.tsv     # check_domains.sh TSV output only
├── shortlist.md           # survivors with scores and notes
├── vetting/               # step 7 output: domains.txt, inspect.txt, vet.txt
└── report.md              # the final ranking
```

The files make the run resumable, keep the same name from being checked twice,
and let you measure the yield of each strategy. Keep `results/` for the plain
TSV output, because the dedupe command in `references/generation.md` reads it.
Anything else, such as `--table` output, goes in `vetting/`.

## Workflow

### 1. Understand the product

Read what exists: the landing page, README, pitch, docs. Find out what the
product does, for whom, how it charges, and what it promises.

Do not infer markets or languages from details like the payment method, the
currency or the language of the copy. The run behind this skill assumed the
product was Brazil-only because it had Pix and prices in reais. It was
international, so a whole round of Portuguese names was wasted. Ask instead.

### 2. Brief: ask before generating

Ask everything the material does not answer in one message, with a suggested
default for each question:

1. **Markets and languages.** Where does it sell now, and where in two or three
   years? Every one of these languages, current or future, becomes a meaning
   and sound filter: the name will travel before the product does.
2. **Domain.** Which extension is a must: .com, .com.br, .ai, .app? Is a
   modified .com acceptable (get-, try-, -hq)? Is there a budget to buy a taken
   domain? Aftermarket names cost from a few hundred dollars to tens of
   thousands.
3. **Personality.** Three adjectives, and the feeling the name should leave.
   Brands they admire, from any category.
4. **Freedom.** Brandable (the default), or should the name hint at the
   category? Are there languages whose words must be avoided, such as no
   Portuguese words for a global product?
5. **Constraints.** Maximum length, sounds to avoid, names they already like
   or rejected (and why), and competitors to stay away from.
6. **Handles that matter.** Instagram and TikTok for consumer and social
   products; GitHub and npm for developer tools.

Save the answers to `brief.md`. If the user says "just go", use the defaults
and state them in one line.

### 3. Generate in batches by strategy

`references/generation.md` has the strategies, how to work each one, and the
yields measured in the reference run. Read it before the first batch.

- **Batch size.** Write 40–80 names per batch, one strategy per batch, to
  `candidates/NN-<strategy>.txt`. Use one name per line, ASCII lowercase. Put
  the intended spelling in a comment if it differs:
  `postencia  # Postência`.
- **Start where the yield is.** Unusual combinations of two known words left
  about 40% of .com domains free; most other strategies left almost none. If a
  non-.com extension is acceptable, invented and arbitrary words come back
  into play.
- **Check each batch before generating the next, and record its yield.**
  When a strategy drops below about 5% free, switch to another. Switching
  groups was the most useful move in the reference run.
- **Mine around winners.** When a name looks promising, try the same pattern
  with other words.
- **Drop the obvious failures as you write.** Cut names that are
  unpronounceable, that are a word in a forbidden language, or that sound like
  a competitor. Don't deliberate over names before knowing they are free: the
  domain check costs seconds, judgment costs much more.

After the first one or two batches, show the user a sample of 8–12 free names
across strategies and ask which directions feel right. It is the cheapest way
to calibrate taste before generating hundreds more. Skip this only if they
asked for an end-to-end run.

Stop generating when about 15–30 free names have passed the filters in step 5.
A typical run tests 300–900 candidates.

### 4. Check domains in bulk

```bash
bash <skill-dir>/scripts/check_domains.sh -t com < candidates/03-combos.txt > results/03-combos.tsv
bash <skill-dir>/scripts/check_domains.sh -t com,com.br,ai --table plazabuzz kioskbuzz
```

- **Output.** One line per domain: `domain<TAB>free|taken|unknown|invalid<TAB>how`.
  With `--table`, one row per name. `-v` adds the get-, try-, use-, -hq and
  -app variants.
- **Unknown is never free.** It means a timeout, a rate limit or a failed
  self-test. Run those names again later.
- **Free means not registered.** Premium or reserved names also look free;
  the registrar shows the real price.
- **Self-test.** Before each extension, the script checks a domain that is
  surely registered and a random one. If either answer is wrong, that
  extension's results come out unknown. In the reference run, a hand-written
  .io check reported registered domains as free. In testing this script, a
  wrong RDAP server called google.co free.
- **Speed.** The script asks the registries directly and throttles itself for
  each one. Rough speeds: .com 150 names in about 12 s, .com.br about 4 per
  second, .app/.dev about 1 per second, whois-only extensions about 1 per
  second.
- **Order.** Check the must-have extension on every candidate first, and the
  other extensions only on the survivors.

### 5. Filter the survivors

Run every free name through the filters in `references/criteria.md`:

- a bad meaning in any market language
- autocorrect pulling it toward another word
- a word from a forbidden language
- the radio test (people who hear it can't spell it)
- an expression too common to stand out
- sounding like a competitor

Each of these eliminated at least one real name in the reference run. Two of
them are cheap to run on the whole list, so do them here rather than leaving
them to vetting:

- **Autocorrect:** `bash <skill-dir>/scripts/vet_name.sh --quick -l <locales> <names>`
  gives one line per name and market.
- **Competitors by root:** take the words that repeat across the survivors
  (kite, plaza, chirp) and run one web search per root with the category:
  `"<root>" social media app`, `"<root>" AI marketing`. In the end-to-end
  test of this skill, the finalist Chirpbell died at vetting because Chirpy,
  an AI social media tool for small businesses, already existed. A search
  per root would have dropped every chirp- name before scoring.

### 6. Score and shortlist

Give the 8–12 most promising survivors the full scorecard from
`references/criteria.md`, with one line of justification per criterion. The
rest get a single line saying why they rank lower. Write it all to
`shortlist.md`, and take the best 5–8 to vetting.

### 7. Vet the finalists

For each finalist, saving the outputs in `vetting/`:

1. **Every relevant extension:**
   `check_domains.sh --table -t com,com.br,ai,io,app <names>`. Add `-v` only
   for names whose plain .com is taken: it checks six times as many domains,
   and .app runs at one per second.
2. **Who holds a taken .com:** `inspect_domain.sh name.com`. It shows the
   registration date, registrar, nameservers and where the site lands, then
   gives a verdict: FOR SALE (and on which marketplace), PARKED, NO RESPONSE,
   REDIRECTS, ACTIVE SITE or UNCLEAR. An active site in the same category is
   a red flag. PostKite.com, for example, was registered in 2025 for an AI
   tool to grow on Twitter: a direct competitor for a social media product.
3. **Search, trademarks and handles:**
   `vet_name.sh -l pt-BR,en-US <names>`, with one locale per current market
   plus one for each future region. It reports:
   - autocomplete that steers away from the name (for example "postencia" →
     "potência"); `references/criteria.md` says how much each case weighs
   - similar USPTO marks, live or dead, with their classes
   - INPI counts for exact and radical searches
   - GitHub and npm availability
   - links for everything that must be checked by eye
4. **Search conflicts.** Search the name in quotes for each market. Look for
   a company in the same category, autocorrect to another word, or generic
   results that would outrank the brand. Agents' web search tools often run
   from the US: good for spotting conflicts, not for judging competition in
   another country. If you have a browser tool, open the Google links from
   `vet_name.sh`, which set the country.
5. **Trademark pre-screen and handles.** `references/clearance.md` explains
   which classes matter, how to read the hits, when a hit is a blocker, and
   how to check Instagram, TikTok and other handles.

If something the user said matters can't be checked, say so up front instead
of burying it. This happens, for example, with Instagram and TikTok when no
browser tool is available. The report then opens with a "Pending checks"
line, and the ranking is provisional until those checks are done.

`references/clearance.md` also covers search volume and the SEO logic for
brandable names.

### 8. Report

Write `report.md` and show it in the conversation. If you can't write files
(some subagent setups block it), put the full report in your reply instead.

```markdown
# Names for <product>

**Brief:** markets · required domain · personality · style
**Search:** N candidates in K strategies → F names with .<tld> free (+G only as get-/try-) → S passed the filters → V vetted
**Pending checks:** (only if any) e.g. Instagram/TikTok handles not verified; ranking provisional until then

## Ranking

### 1. Name (how to say it)
- **Domains:** name.com free · name.com.br free · name.ai taken (for sale on Atom) · getname.com free
- **Why it fits:** the association or story, and how it connects to the brand's promise
- **Marketing potential:** memorability, visual and tone ideas, verb or community use, search (distinct, no autocorrect)
- **Risks:** trademark hits in the relevant classes, similar names, pronunciation in market X, handles taken
- **Score:** fit 5 · memory 4 · sound 5 · distinct 4 · story 4 · range 5 · trademark 4 · availability 5 = 36/40
- **Next steps:** what to register or buy today, which trademark classes to file in, which handles to claim

### 2. ...

## Also considered
| Name | Why it was dropped |
|---|---|

## Before you register
- Availability changes fast: run check_domains.sh again right before buying.
- This is a trademark pre-screen, not clearance. For the final pick, have a trademark attorney or agent search the target classes before investing in branding.
- Register the main domain, the defensive ones (.com.br, an obvious typo) and the handles on the same day.
```

Rank by the scorecard, but explain the trade-offs. "Best name, but the .com
costs US$ 4,000" and "free everywhere, but less memorable" are different
recommendations, and the user should see both.

### If the user already has a name

Go straight to step 7 for that name and its close variations. If it fails,
explain why and offer to search for alternatives in the same spirit, starting
the brief from what they liked about it.

## Pitfalls

- **Untested checks.** Never trust an availability check you haven't seen fail
  correctly. The scripts test themselves. If you write an ad-hoc check, try it
  on a domain you know is registered and on a random string first.
- **Raw whois output.** Don't parse it by eye. Some registries print
  "Domain Name: x" even for names that don't exist (.so), and some never
  answer (.es). `check_domains.sh` handles both.
- **zsh loops.** zsh does not split an unquoted `$list` into words, so
  `for n in $names` runs once with every name. Feed names from a file or
  stdin, or run loops with `bash`.
- **Availability changes.** Re-check before registering. Never register, buy
  or contact an owner on the user's behalf without asking.
- **Legal advice.** A pre-screen finds obvious conflicts; it does not clear a
  mark. Say so in the report.
