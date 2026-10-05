# Filters and scorecard

Run every free name through the filters first; one failure is enough to drop
it. Then score what is left.

## Contents

- Language and memory filters, with real names they eliminated
- Scorecard: fit, stickiness and marketing potential
- Trademark strength

## Language and memory filters

Each filter below eliminated at least one real name in the reference run.

### 1. Bad meaning in a market language

Read the name, and its parts, in every market language (current and future)
and in slang. Say it aloud too: sound-alikes count, not just exact spelling.

- **Buzzeta** sounds like a Brazilian swear word.
- **Feedaria** can be read as "fedaria" ("would stink").

When unsure, search the name or its syllables with "gíria", "slang" or
"meaning", in each language.

### 2. Autocorrect and search steering

If search engines or phone keyboards "fix" the name, people who hear it land
somewhere else.

- **Postência** becomes "potência".
- **Famelo** becomes "Famileo" (and "pamelor" in Brazilian autocomplete).

Check the whole list at once with
`vet_name.sh --quick -l pt-BR,en-US <names>`. Its verdicts don't all weigh
the same:

| Verdict | Example | Weight |
|---|---|---|
| no suggestions | | Clean slate: good. |
| starts with the name | plazaparrot → "plaza parrot" | Fine. If the suggestions belong to one company, that company owns the term (see clearance.md). |
| completes only the first part | toucantown → "toucan battle" (pt-BR) | Minor: nobody searches the full name yet, and Google completes the part it knows. |
| STEERS AWAY, in a main market, to a real word or a known brand | postencia → "potência"; toucantown → "touchtown" (en-US) | Search the name on Google for that market. If it shows "Did you mean" or "Showing results for", **drop the name**. If it doesn't, keep the name but take a point off sound/spelling and distinctiveness, and list it as a risk. |
| STEERS AWAY, to noise or in a minor market | | A note in the risks. |

Also read past the first suggestion. Famelo starts with "famelok", but the
rest is all "pamelor".

### 3. A word from a forbidden language

If the brief rules out a language (for example, no Portuguese words for an
international product), a real word in it fails, even when it sounds good.

- **Aclama** is a Portuguese word ("acclaims").

### 4. Radio test

Say the name to someone who has never seen it. Can they type it correctly
on the first try? Can they say it after reading it?

The test fails on ambiguous spellings (c/k, s/z, i/y), doubled or silent
letters, numbers, hyphens, and spellings that differ from how the word
sounds in a market language.

### 5. Expression too common

A phrase people already use can't stand out in search and can't be
registered as a trademark.

- **Agência do Bairro** ("neighborhood agency").

The same goes for single generic words in the product's category.

### 6. Sounds like a competitor

The name must not be confusable with a player in the same category: same
start, same rhythm, one letter apart. It confuses customers, and the
trademark office applies the same test.

**Search by root, before scoring.** Take each word that repeats across the
survivors and run one web search per root with the category, for example
`"kite" social media app` or `"chirp" AI marketing small business`. One
same-category competitor drops every name built on that root:

- PostKite eliminated all the -kite names.
- Chirpy (an AI social media tool for small businesses) eliminated Chirpbell.

Ten searches here save vetting names that were never viable.

## Scorecard

Score the 8–12 most promising survivors from 1 to 5 on each criterion. The
total is out of 40. The rest get one line saying why they rank lower: a full
scorecard for 20+ names costs more than it tells.

| Criterion | 5 means | 1 means |
|---|---|---|
| **Fit (aderência)** | Feels like the brand's personality and promise; the audience would say it proudly | Wrong tone (childish for a bank, stiff for a game) or neutral |
| **Memory** | Heard once, remembered the next day; vivid image or sound | Forgettable, or like many others |
| **Sound and spelling** | Easy to say in every market language, passes the radio test, 2–3 syllables | Stumbles, has several possible spellings, or sounds different across markets |
| **Distinctiveness** | Unlike competitors' names; owns its search results | Close to a competitor, or buried under generic results |
| **Story** | A one-sentence story behind it; suggests a visual identity and tone; can become a verb or community name | Nothing to say about it |
| **Range** | Survives new features, new markets, a pivot | Tied to one feature, one channel or one country |
| **Trademark** | Invented, arbitrary or suggestive; no live conflicts in the classes found | Descriptive, or live similar marks in the same classes |
| **Availability** | Required domain free (or cheap), main handles free | Required domain taken and not for sale, or handles taken by active accounts |

A total of 32 or more is strong. Below 24, the name rarely beats the
alternatives.

Treat fit and memory as the heart of the score. A name that scores 5 on
availability but 2 on fit is a free domain, not a brand. When two names are
close, prefer the one with the better story: that is what the marketing will
use every day.

Write one line of justification next to each score in `shortlist.md`. The
user will want to know why, and numbers alone hide the judgment.

## Trademark strength

Trademark offices and courts rank names on a spectrum. Stronger names are
easier to register and to defend:

1. **Fanciful (invented):** Kodak, Xerox. Strongest.
2. **Arbitrary (real word, unrelated meaning):** Apple for computers, Slack.
3. **Suggestive (hints, requires imagination):** Netflix, Airbnb, Coinbase.
4. **Descriptive (describes the product):** usually refused or weak until it
   becomes famous.
5. **Generic (the name of the thing itself):** can never be registered.

A brandable name is also the stronger trademark. When a user asks for a name
that "says what it does", explain this trade-off and offer suggestive names
as the middle ground.
