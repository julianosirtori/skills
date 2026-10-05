#!/bin/bash
# vet_name.sh - deep pre-screen of finalist names, beyond the domain.
#
# Usage: vet_name.sh [-l pt-BR,en-US] [--quick] name [name...]
#   -l, --locales LIST  markets as language-COUNTRY (default: en-US). Drives the
#                       Google autocomplete check and the search links.
#   --quick             autocomplete only, one line per name and market: a fast
#                       filter for a whole shortlist before full vetting.
#
# For each name it prints:
#   search      Google autocomplete per market. If the suggestions steer to
#               another word ("postencia" -> "potência"), people who hear the
#               name will land somewhere else.
#   trademarks  USPTO marks spelled like it or one letter away (live ones flagged,
#               with Nice classes), and INPI Brazil counts for exact and radical
#               searches. A pre-screen, not legal clearance.
#   handles     GitHub user/org and npm package/scope.
#   links       to check by eye: Google per market, WIPO Global Brand Database
#               (phonetic), Instagram, TikTok, X, YouTube, LinkedIn. Those sites
#               block or forbid automated checks, so open them in a browser.
#
# The USPTO and INPI endpoints are the ones their own search pages use; they
# are undocumented and may change. If a section errors, use the links instead.
# Read-only. Needs curl and jq; iconv for INPI. Meant for a handful of
# finalists: GitHub allows 60 unauthenticated lookups per hour.

set -u

TIMEOUT=20
LOCALES=en-US
QUICK=0
NAMES=()
while [ $# -gt 0 ]; do
  case "$1" in
    -l|--locales) shift; LOCALES="${1:-en-US}" ;;
    --quick) QUICK=1 ;;
    -h|--help) sed -n '2,25p' "$0"; exit 0 ;;
    -*) echo "unknown option: $1" >&2; exit 2 ;;
    *) NAMES+=("$1") ;;
  esac
  shift
done
[ ${#NAMES[@]} -gt 0 ] || { sed -n '2,25p' "$0"; exit 2; }
command -v jq >/dev/null 2>&1 || { echo "jq is required (brew install jq)" >&2; exit 1; }

uri() { jq -rn --arg s "$1" '$s | @uri'; }

autocomplete() { # name locale
  local hl=$2 gl
  gl=$(printf '%s' "${2#*-}" | tr '[:upper:]' '[:lower:]')
  curl -s -m "$TIMEOUT" "https://suggestqueries.google.com/complete/search?client=chrome&ie=utf-8&oe=utf-8&hl=$hl&gl=$gl&q=$(uri "$1")" |
    jq -r --arg n "$1" '
      (.[1] // []) as $s
      | ($n | ascii_downcase | gsub(" "; "")) as $k
      | (($s[0] // "") | ascii_downcase) as $first
      | ($first | split(" ")[0]) as $word
      | if ($s | length) == 0 then "no suggestions (nobody searches it yet: clean slate)"
        elif ($first | gsub(" "; "") | startswith($k)) then
          "starts with the name: " + ($s[0:6] | join(" | "))
        elif ($word | length) >= 3 and ($k | startswith($word)) then
          "completes only \"" + $word + "...\" (nobody searches the full name yet; minor): " + ($s[0:4] | join(" | "))
        else "STEERS AWAY to \"" + $s[0] + "\": " + ($s[0:6] | join(" | ")) end' 2>/dev/null ||
    echo "no answer (try the Google link below)"
}

uspto() { # name -> similar marks
  local q
  q="wordmark:$1* OR wordmark:$1~1"
  curl -s -m "$TIMEOUT" -X POST -H 'Content-Type: application/json' \
    -d "{\"query\":{\"query_string\":{\"query\":$(jq -n --arg q "$q" '$q')}},\"size\":12,\"_source\":[\"wordmark\",\"alive\",\"internationalClass\",\"ownerName\"]}" \
    https://tmsearch.uspto.gov/prod-stage-v1-0-0/tmsearch |
    jq -r '
      if .hits == null then "no answer (use the WIPO link)" else
      ([.hits.hits[] | select(.source.alive)] | length) as $live
      | "top 12 of \(.hits.totalValue) loose matches (same start or one letter away), \($live) live:",
        (.hits.hits[] | .source
          | "    \(if .alive then "LIVE" else "dead" end)  \(.wordmark)  [\((.internationalClass // []) | join(", "))]  \((.ownerName // ["?"])[0])")
      end' 2>/dev/null || echo "no answer (use the WIPO link)"
}

inpi() { # name -> counts for exact and radical searches, first exact hits
  local jar mode out
  jar=$(mktemp "${TMPDIR:-/tmp}/inpi.XXXXXX")
  curl -s -m "$TIMEOUT" -c "$jar" -o /dev/null "https://busca.inpi.gov.br/pePI/servlet/LoginController?action=login"
  for mode in sim nao; do
    out=$(curl -s -m "$TIMEOUT" -b "$jar" -e "https://busca.inpi.gov.br/pePI/jsp/marcas/Pesquisa_classe_basica.jsp" \
      --data "buscaExata=$mode&txt=&Action=searchMarca&tipoPesquisa=BY_MARCA_CLASSIF_BASICA&marca=$(uri "$1")&classeInter=&registerPerPage=20" \
      https://busca.inpi.gov.br/pePI/servlet/MarcasServletController | iconv -f ISO-8859-1 -t UTF-8 2>/dev/null)
    label=$([ "$mode" = sim ] && echo exact || echo radical)
    if printf '%s' "$out" | grep -q 'Nenhum resultado'; then
      echo "$label: no marks"
    elif printf '%s' "$out" | grep -q 'Foram encontrados'; then
      echo "$label: $(printf '%s' "$out" | tr '\n\r' '  ' | grep -o 'Foram encontrados.\{0,120\}' |
        sed 's/<[^>]*>//g' | grep -o '[0-9][0-9]*' | head -1) marks"
      if [ "$mode" = sim ]; then
        printf '%s' "$out" | tr '\n\r' '  ' | sed 's/<tr/\
<tr/g' | grep 'CodPedido' | head -8 |
          sed -e 's/<[^>]*>/ /g' -e 's/&nbsp;/ /g' | tr -s ' \t' ' ' | sed 's/^ */    /'
      fi
    else
      echo "$label: no answer (search by hand at busca.inpi.gov.br)"
    fi
  done
  rm -f "$jar"
}

exists() { # url -> taken|free|unknown (HTTP 200 / 404)
  case "$(curl -s -o /dev/null -w '%{http_code}' -m "$TIMEOUT" "$1")" in
    200) echo taken ;;
    404) echo free ;;
    *) echo unknown ;;
  esac
}

if [ "$QUICK" = 1 ]; then
  for raw in "${NAMES[@]}"; do
    name=$(printf '%s' "$raw" | tr '[:upper:]' '[:lower:]' | sed 's/[[:space:]]//g')
    for loc in $(printf '%s' "$LOCALES" | tr ',' ' '); do
      printf '%-16s %-6s %s\n' "$name" "$loc" "$(autocomplete "$name" "$loc")"
    done
  done
  exit 0
fi

for raw in "${NAMES[@]}"; do
  name=$(printf '%s' "$raw" | tr '[:upper:]' '[:lower:]' | sed 's/[[:space:]]//g')
  echo "=================== $raw"

  echo "search"
  for loc in $(printf '%s' "$LOCALES" | tr ',' ' '); do
    printf '  %-7s %s\n' "$loc" "$(autocomplete "$name" "$loc")"
  done

  echo "trademarks"
  printf '  USPTO   '; uspto "$name" | sed '2,$s/^/  /'
  inpi "$name" | sed 's/^/  INPI    /; s/^  INPI        /          /'

  echo "handles"
  echo "  github  $(exists "https://api.github.com/users/$name")   npm $(exists "https://registry.npmjs.org/$name")   npm @scope $(exists "https://registry.npmjs.org/-/org/$name/package")"

  echo "links (check by eye)"
  for loc in $(printf '%s' "$LOCALES" | tr ',' ' '); do
    gl=$(printf '%s' "${loc#*-}" | tr '[:upper:]' '[:lower:]')
    echo "  google $loc  https://www.google.com/search?q=%22$(uri "$raw")%22&hl=$loc&gl=$gl"
  done
  echo "  wipo     https://branddb.wipo.int/en/similarname/results?sort=score%20desc&start=0&rows=30&asStructure=%7B%22_id%22:%221%22,%22boolean%22:%22AND%22,%22bricks%22:%5B%7B%22_id%22:%222%22,%22key%22:%22brandName%22,%22value%22:%22$(uri "$name")%22,%22strategy%22:%22Phonetic%22%7D%5D%7D"
  echo "  instagram https://www.instagram.com/$name/"
  echo "  tiktok   https://www.tiktok.com/@$name"
  echo "  x        https://x.com/$name"
  echo "  youtube  https://www.youtube.com/@$name"
  echo "  linkedin https://www.linkedin.com/company/$name"
done
