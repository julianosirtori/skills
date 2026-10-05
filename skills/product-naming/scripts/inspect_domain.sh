#!/bin/bash
# inspect_domain.sh - who holds a taken domain, and can it be bought?
#
# Usage: inspect_domain.sh domain [domain...]
#   For each domain: registration and expiry dates, registrar, nameservers,
#   where the site ends up after redirects, its page title, and a verdict:
#     FOR SALE      lands on (or uses the DNS of) a domain marketplace,
#                   or the page says it is for sale
#     PARKED        parking DNS or a placeholder page: not in use
#     NO RESPONSE   registered but no website answers
#     REDIRECTS     sends visitors to another site (that brand owns it)
#     ACTIVE SITE   a real site: open it and see if it is a competitor
#     UNCLEAR       an error page or no title: open it in a browser
#   The verdict is a strong hint, not proof: confirm by opening the site.
#   Takes a few seconds per domain; meant for finalists, not bulk lists.
#
# Read-only. Needs curl; jq for registration details (falls back to whois).

set -u

TIMEOUT=15
BROWSER_UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
HERE=$(cd "$(dirname "$0")" && pwd)

# Hosts and nameservers of domain marketplaces and parking services.
MARKETS='atom\.com|squadhelp|hugedomains|dan\.com|afternic|sedo\.com|buydomains|brandbucket|brandpa|domainmarket|undeveloped|efty|namecheap\.com/market|godaddy\.com/forsale|spaceship\.com|domainagents|epik\.com'
PARKING='sedoparking|bodis|parkingcrew|above\.com|parklogic|parkingpage|ztomy|voodoo\.com|cashparking'
SALE_TEXT='is for sale|buy this domain|make an offer|domain for sale|this domain may be for sale|está à venda|dominio en venta|purchase this domain'
PARKED_TEXT='parked free|domain parking|coming soon|under construction|this domain is registered|website coming|em construção|related searches'

registration() { # domain -> lines "field<TAB>value"
  local d=$1 ext=${1#*.} method endpoint _rest
  read -r method endpoint _rest <<EOF
$(bash "$HERE/check_domains.sh" --route "$ext")
EOF
  if [ "$method" = rdap ] && command -v jq >/dev/null 2>&1; then
    curl -s -m "$TIMEOUT" -H 'Accept: application/rdap+json' "${endpoint}domain/$d" | jq -r '
      def ev(a): [.events[]? | select(.eventAction == a) | .eventDate][0] // "-";
      "registered\t" + ev("registration"),
      "expires\t" + ev("expiration"),
      "registrar\t" + ([.entities[]? | select(.roles | index("registrar"))
        | .vcardArray[1][]? | select(.[0] == "fn") | .[3]][0] // "-"),
      "status\t" + ((.status // []) | join(", ")),
      "nameservers\t" + ([.nameservers[]?.ldhName] | join(", ") | ascii_downcase)' 2>/dev/null
  elif [ "$method" = whois ]; then
    perl -e 'alarm shift; exec @ARGV' "$TIMEOUT" whois -h "$endpoint" "$d" 2>/dev/null |
      grep -iE '^ *(creation date|created|registered on|registry expiry|expir|registrar:|name server|nserver|status)' |
      sed 's/^ *//' | head -12
  else
    echo "registration	(no jq; run: whois $d)"
  fi
}

probe() { # domain -> "code<TAB>final url<TAB>title<TAB>body-sale<TAB>body-parked"
  local d=$1 body code_url code url title sale=no parked=no
  body=$(mktemp "${TMPDIR:-/tmp}/inspect.XXXXXX")
  code_url=$(curl -sL -m "$TIMEOUT" -A "$BROWSER_UA" -o "$body" -w '%{http_code} %{url_effective}' "http://$d")
  code=${code_url%% *}
  url=${code_url#* }
  if [ "$code" = 000 ]; then
    code_url=$(curl -sL -m "$TIMEOUT" -A "$BROWSER_UA" -o "$body" -w '%{http_code} %{url_effective}' "https://$d")
    code=${code_url%% *}
    url=${code_url#* }
  fi
  title=$(tr '\n\r' '  ' <"$body" | grep -oiE '<title[^>]*>[^<]*' | head -1 | sed -E 's/<title[^>]*>//; s/^ +//; s/ +$//')
  if LC_ALL=C grep -qiE "$SALE_TEXT" "$body"; then sale=yes; fi
  if LC_ALL=C grep -qiE "$PARKED_TEXT" "$body"; then parked=yes; fi
  rm -f "$body"
  printf '%s\t%s\t%s\t%s\t%s\n' "$code" "$url" "${title:--}" "$sale" "$parked"
}

[ $# -gt 0 ] || { sed -n '2,17p' "$0"; exit 2; }

for d in "$@"; do
  d=$(printf '%s' "$d" | tr '[:upper:]' '[:lower:]' | sed -E 's#^(https?://)?(www\.)?##; s#/.*$##')
  echo "== $d"
  reg=$(registration "$d")
  if [ -n "$reg" ]; then
    printf '%s\n' "$reg" | awk -F'\t' 'NF > 1 {printf "  %-12s %s\n", $1, $2; next} {print "  " $0}'
  else
    echo "  (no registration record: the domain may be free; run check_domains.sh)"
  fi
  IFS=$'\t' read -r code url title sale parked <<EOF
$(probe "$d")
EOF
  host=$(printf '%s' "$url" | sed -E 's#^[a-z]+://##; s#/.*$##; s#:[0-9]+$##; s#^www\.##')
  ns=$(printf '%s\n' "$reg" | grep -i 'nameserver\|name server\|nserver' | tr '[:upper:]' '[:lower:]')
  # Page text and parking DNS only count on placeholder-looking pages: real
  # sites can say "coming soon" somewhere, and some hosts' default DNS
  # (Hostinger's dns-parking.com) also serves live sites.
  lower_title=$(printf '%s' "$title" | tr '[:upper:]' '[:lower:]')
  placeholder=no
  case "$lower_title" in
    -|"$d"|"www.$d"|*sale*|*venda*|*parked*|*domain*|*"coming soon"*) placeholder=yes ;;
    *) sale=no; parked=no ;;
  esac
  if printf '%s\n' "$ns" | grep -qiE "$PARKING" && [ "$placeholder" = yes ]; then parked=yes; fi
  echo "  website      HTTP $code -> $url"
  echo "  title        $title"

  if printf '%s %s\n' "$url" "$ns" | grep -qiE "$MARKETS"; then
    market=$(printf '%s %s\n' "$url" "$ns" | grep -oiE "$MARKETS" | head -1)
    verdict="FOR SALE via $market. Check the asking price; aftermarket prices vary a lot."
  elif [ "$sale" = yes ]; then
    verdict="FOR SALE (the page says so). Check the price and the seller."
  elif [ "$parked" = yes ] || [ "$lower_title" = "$d" ] || [ "$lower_title" = "www.$d" ]; then
    verdict="PARKED: registered but not in use. The owner may sell; a broker can ask."
  elif [ "$code" = 000 ]; then
    verdict="NO RESPONSE: registered, no website. Idle; the owner may sell."
  elif [ -n "$host" ] && [ "$host" != "$d" ]; then
    verdict="REDIRECTS to $host: in use by that brand."
  elif [ "$code" -ge 400 ] || [ "$title" = - ]; then
    verdict="UNCLEAR: HTTP $code, title '$title'. Open it in a browser."
  else
    verdict="ACTIVE SITE: open it and check whether it competes in the same category."
  fi
  echo "  verdict      $verdict"
done
