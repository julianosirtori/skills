#!/bin/bash
# check_domains.sh - bulk domain availability, asked straight to the registries.
#
# Usage: check_domains.sh [-t com,ai,com.br] [-v] [--table] [--no-selftest] [name...]
#   Names come from the arguments or, when there are none, one per line on stdin
#   (blank lines and lines starting with # are skipped). A bare label ("postkite")
#   is checked against every extension in -t; a full domain ("postkite.com.br")
#   is checked as is.
#   -t, --tlds LIST   comma-separated extensions for bare labels (default: com)
#   -v, --variants    also check get<name>, try<name>, use<name>, <name>hq, <name>app
#   --table           one row per name and one column per extension, instead of TSV
#   --no-selftest     skip the per-extension sanity check (not recommended)
#
# Output (TSV): domain <TAB> free|taken|unknown|invalid <TAB> how it was decided
#   free     the registry has no record of it (RDAP 404 or whois "not found").
#            Premium or reserved names also look free: the registrar confirms price.
#   taken    the registry returned a registration record.
#   unknown  timeout, rate limit, odd answer, or the extension failed its self-test.
#            Never read unknown as free; run those again later.
# Before checking an extension, it is asked about a domain that is surely
# registered and a random one. If it gets either wrong, its results are not
# trusted and come out as unknown.
#
# Compatible with the stock macOS bash 3.2. Needs curl; whois and perl for
# extensions without RDAP; jq (optional) to find RDAP servers via IANA.

set -u

TIMEOUT=15
UA="product-naming-skill/1.0 (+https://github.com/julianosirtori/skills)"
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/product-naming"

# ---------------------------------------------------------------- one lookup

rdap_lookup() { # endpoint domain -> "status<TAB>detail"
  local code tries=0 wait=2
  while :; do
    code=$(curl -s -o /dev/null -w '%{http_code}' -m "$TIMEOUT" -A "$UA" \
      -H 'Accept: application/rdap+json' "${1}domain/$2")
    case "$code" in
      200) printf 'taken\trdap 200'; return ;;
      404) printf 'free\trdap 404'; return ;;
      429|000|5??) ;; # rate limit, dropped connection or server error: retry
      *) printf 'unknown\trdap HTTP %s' "$code"; return ;;
    esac
    tries=$((tries + 1))
    if [ "$tries" -ge 4 ]; then
      printf 'unknown\trdap HTTP %s after %d tries' "$code" "$tries"
      return
    fi
    sleep "$wait"
    wait=$((wait * 2))
  done
}

# "Not found" phrases are checked first: some registries (.so) print
# "Domain Name: x" even for names that do not exist.
WHOIS_FREE='no match|not found|no data found|no entries found|does not exist|no object found|status: *(free|available)|is available for'
WHOIS_BUSY='limit exceeded|quota|too many|try again later|rate limit'
WHOIS_TAKEN='^ *(registrar|creation date|created|registered|nserver|nsentry|name server|domain status|registrant)[^:]*:|^ *status: *(connect|active|registered|ok)'

whois_lookup() { # server domain -> "status<TAB>detail"
  local out tries=0 wait=2
  while :; do
    # perl's alarm is the portable timeout: some whois servers never answer.
    out=$(perl -e 'alarm shift; exec @ARGV' "$TIMEOUT" whois -h "$1" "$2" 2>&1 |
      tr '[:upper:]' '[:lower:]')
    if printf '%s\n' "$out" | grep -qE "$WHOIS_FREE"; then
      printf 'free\twhois %s: not found' "$1"; return
    elif printf '%s\n' "$out" | grep -qE "$WHOIS_BUSY"; then
      : # rate limited: retry
    elif printf '%s\n' "$out" | grep -qE "$WHOIS_TAKEN"; then
      printf 'taken\twhois %s: record' "$1"; return
    elif [ -n "$out" ]; then
      printf 'unknown\twhois %s: unrecognized answer' "$1"; return
    fi
    tries=$((tries + 1))
    if [ "$tries" -ge 3 ]; then
      printf 'unknown\twhois %s: no usable answer after %d tries' "$1" "$tries"
      return
    fi
    sleep "$wait"
    wait=$((wait * 2))
  done
}

lookup() { # method endpoint domain
  if [ "$1" = rdap ]; then rdap_lookup "$2" "$3"; else whois_lookup "$2" "$3"; fi
}

# Worker mode, used through xargs: --one METHOD ENDPOINT DELAY DOMAIN
if [ "${1:-}" = "--one" ]; then
  printf '%s\t%s\n' "$5" "$(lookup "$2" "$3" "$5")"
  [ "$4" = 0 ] || sleep "$4"
  exit 0
fi

# --------------------------------------------------------- extension routing

# Extension -> "method endpoint parallel delay". Limits measured in Oct 2026:
# Verisign takes 8 parallel; registro.br drops connections above 2; Google
# (.app, .dev) answers 429 after ~10 quick queries, so one per second.
# Only servers verified to be authoritative are listed here: Identity Digital's
# server answers .io and .ai correctly but says "not found" for google.co.
tld_config() {
  case "$1" in
    com|net) echo "rdap https://rdap.verisign.com/$1/v1/ 8 0" ;;
    br|*.br) echo "rdap https://rdap.registro.br/ 2 0" ;;
    ai|io|me|sh) echo "rdap https://rdap.identitydigital.services/rdap/ 4 0" ;;
    app|dev|page) echo "rdap https://pubapi.registry.google/rdap/ 1 1" ;;
    org) echo "rdap https://rdap.publicinterestregistry.org/rdap/ 2 0" ;;
    xyz) echo "rdap https://rdap.centralnic.com/xyz/ 2 0" ;;
    *) bootstrap_config "$1" ;;
  esac
}

bootstrap_config() { # any other extension: IANA's RDAP list, else whois
  local tld=$1 last=${1##*.} file="$CACHE_DIR/rdap-dns.json" url server
  if command -v jq >/dev/null 2>&1; then
    mkdir -p "$CACHE_DIR"
    if [ ! -s "$file" ] || [ -n "$(find "$file" -mtime +7 2>/dev/null)" ]; then
      curl -s -m "$TIMEOUT" -o "$file.tmp" https://data.iana.org/rdap/dns.json &&
        mv "$file.tmp" "$file"
    fi
    url=$(jq -r --arg a "$tld" --arg b "$last" \
      '[.services[] | select(.[0] | index($a) or index($b)) | .[1][0]] | first // empty' \
      "$file" 2>/dev/null)
    case "$url" in
      */) ;;
      ?*) url="$url/" ;;
    esac
    if [ -n "$url" ]; then echo "rdap $url 2 1"; return; fi
  fi
  server=$(perl -e 'alarm shift; exec @ARGV' "$TIMEOUT" whois -h whois.iana.org "$last" 2>/dev/null |
    awk '/^whois:/ {print $2; exit}')
  if [ -n "$server" ]; then echo "whois $server 1 1"; else echo "none - 1 0"; fi
}

# Routing mode, used by inspect_domain.sh: --route EXTENSION
if [ "${1:-}" = "--route" ]; then
  tld_config "$2"
  exit 0
fi

selftest() { # method endpoint tld -> prints a reason and fails if not trustworthy
  local known random="zqx${RANDOM}k${RANDOM}v$$" got
  for known in google amazon nic; do
    got=$(lookup "$1" "$2" "$known.$3" | cut -f1)
    [ "$got" = taken ] && break
  done
  if [ "$got" != taken ]; then
    echo "google/amazon/nic.$3 did not come back as taken"; return 1
  fi
  got=$(lookup "$1" "$2" "$random.$3" | cut -f1)
  if [ "$got" != free ]; then
    echo "random name $random.$3 came back as $got"; return 1
  fi
  echo "$known.$3 taken, $random.$3 free"
}

# -------------------------------------------------------------------- main

TLDS=com
VARIANTS=0
TABLE=0
SELFTEST=1
NAMES=()
while [ $# -gt 0 ]; do
  case "$1" in
    -t|--tlds) shift; TLDS="${1:-com}" ;;
    -v|--variants) VARIANTS=1 ;;
    --table) TABLE=1 ;;
    --no-selftest) SELFTEST=0 ;;
    -h|--help) sed -n '2,25p' "$0"; exit 0 ;;
    -*) echo "unknown option: $1" >&2; exit 2 ;;
    *) NAMES+=("$1") ;;
  esac
  shift
done

if ! command -v curl >/dev/null 2>&1; then echo "curl is required" >&2; exit 1; fi

WORK=$(mktemp -d "${TMPDIR:-/tmp}/check_domains.XXXXXX")
trap 'rm -rf "$WORK"' EXIT

if [ ${#NAMES[@]} -gt 0 ]; then
  printf '%s\n' "${NAMES[@]}" >"$WORK/input"
else
  cat >"$WORK/input"
fi

# Normalize: lowercase, strip scheme, www. and paths, drop comments and blanks.
TLD_LIST=$(printf '%s' "$TLDS" | tr '[:upper:]' '[:lower:]' | tr ',' '\n' | sed 's/^ *\.*//; s/ *$//' | grep -v '^$' | tr '\n' ' ')

sed 's/#.*//' "$WORK/input" | tr '[:upper:]' '[:lower:]' |
  sed -E 's#^[[:space:]]*(https?://)?(www\.)?##; s#/.*$##; s/[[:space:]]+//g' | grep -v '^$' |
  while IFS= read -r entry; do
    case "$entry" in
      *.*) label=${entry%%.*}; exts=${entry#*.} ;;
      *) label=$entry; exts=$TLD_LIST ;;
    esac
    labels=$label
    [ "$VARIANTS" = 1 ] && labels="$label get$label try$label use$label ${label}hq ${label}app"
    for l in $labels; do
      for ext in $exts; do printf '%s\t%s\n' "$l" "$ext"; done
    done
  done | awk -F'\t' '!seen[$0]++' >"$WORK/pairs"

if [ ! -s "$WORK/pairs" ]; then echo "no names given" >&2; exit 2; fi

mark_unknown() { # reason -> every domain in todo is reported as unknown
  awk -v r="$1" '{printf "%s\tunknown\t%s\n", $0, r}' "$WORK/todo" >>"$WORK/results"
}

: >"$WORK/results"
LABEL_RE='^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$'
awk -F'\t' '!seen[$2]++ {print $2}' "$WORK/pairs" >"$WORK/exts"

while IFS= read -r ext; do
  awk -F'\t' -v e="$ext" '$2 == e {print $1 "." $2}' "$WORK/pairs" >"$WORK/all"
  : >"$WORK/todo"
  while IFS= read -r domain; do
    if printf '%s\n' "${domain%%.*}" | grep -qE "$LABEL_RE"; then
      echo "$domain" >>"$WORK/todo"
    else
      printf '%s\tinvalid\tASCII letters, digits and inner hyphens only (no accents), up to 63 chars\n' "$domain" >>"$WORK/results"
    fi
  done <"$WORK/all"
  [ -s "$WORK/todo" ] || continue

  read -r method endpoint parallel delay <<EOF
$(tld_config "$ext")
EOF
  count=$(wc -l <"$WORK/todo" | tr -d ' ')
  if [ "$method" = none ]; then
    echo ".$ext: no RDAP or whois server found; $count marked unknown" >&2
    mark_unknown "no RDAP or whois server for .$ext"
    continue
  fi
  if [ "$method" = whois ] && ! command -v whois >/dev/null 2>&1; then
    echo ".$ext: needs the whois command; $count marked unknown" >&2
    mark_unknown "whois command not installed"
    continue
  fi
  if [ "$SELFTEST" = 1 ]; then
    if ! reason=$(selftest "$method" "$endpoint" "$ext"); then
      echo ".$ext: self-test FAILED ($reason); $count marked unknown" >&2
      mark_unknown ".$ext failed self-test: $reason"
      continue
    fi
    echo ".$ext: self-test ok ($reason)" >&2
  fi
  echo ".$ext: checking $count via $method ($endpoint), $parallel at a time" >&2
  xargs -P "$parallel" -n 1 bash "$0" --one "$method" "$endpoint" "$delay" <"$WORK/todo" >>"$WORK/results"
done <"$WORK/exts"

# Summary on stderr, results on stdout.
awk -F'\t' '{split($1, p, "."); e = substr($1, length(p[1]) + 2); n[e "\t" $2]++; t[e]++}
  END {for (e in t) printf ".%s: %d free, %d taken, %d unknown, %d invalid\n", e,
    n[e "\tfree"], n[e "\ttaken"], n[e "\tunknown"], n[e "\tinvalid"]}' "$WORK/results" | sort >&2
if grep -q '	unknown	' "$WORK/results"; then
  echo "unknown is not free: re-run those names later; if an extension failed its self-test, check it another way" >&2
fi

if [ "$TABLE" = 1 ]; then
  awk -F'\t' -v order="$(tr '\n' ' ' <"$WORK/exts")" '
    NR == FNR {split($1, p, "."); l = p[1]; e = substr($1, length(l) + 2)
      s = ($2 == "free") ? "FREE" : ($2 == "taken") ? "taken" : "?"
      cell[l, e] = s; next}
    !seen[$1]++ {rows[++n] = $1}
    END {m = split(order, cols, " "); w = 4
      for (i = 1; i <= n; i++) if (length(rows[i]) > w) w = length(rows[i])
      printf "%-" w "s", "name"; for (j = 1; j <= m; j++) printf "  %-8s", "." cols[j]; print ""
      for (i = 1; i <= n; i++) {printf "%-" w "s", rows[i]
        for (j = 1; j <= m; j++) {c = cell[rows[i], cols[j]]; printf "  %-8s", (c == "" ? "" : c)}
        print ""}}' "$WORK/results" "$WORK/pairs"
else
  sort "$WORK/results"
fi
