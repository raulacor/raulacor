#!/usr/bin/env python3
"""Render a stock-ticker style SVG card from a GitHub user's contributions.

price  = contributions in the trailing 30 days
candle = one week: open/close = price at week start/end, high/low = extremes
volume = contributions that week

Usage:
  GITHUB_TOKEN=... python scripts/stock_card.py raulacor assets/stock.svg
  python scripts/stock_card.py raulacor assets/stock.svg --demo   # fake data, no token
"""
import base64, datetime as dt, html, json, os, random, sys, urllib.request

WEEKS = 26

QUERY = """
query($login: String!) {
  user(login: $login) {
    name login avatarUrl(size: 96)
    contributionsCollection {
      contributionCalendar { weeks { contributionDays { date contributionCount } } }
    }
    repositories(first: 6, ownerAffiliations: OWNER, isFork: false,
                 orderBy: {field: PUSHED_AT, direction: DESC}) {
      nodes { name stargazerCount primaryLanguage { name color } }
    }
  }
}"""


def fetch(login, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    data = json.load(urllib.request.urlopen(req))
    if "errors" in data:
        sys.exit(f"GraphQL error: {data['errors']}")
    u = data["data"]["user"]
    days = [(d["date"], d["contributionCount"])
            for w in u["contributionsCollection"]["contributionCalendar"]["weeks"]
            for d in w["contributionDays"]]
    repos = [(r["name"], r["stargazerCount"],
              (r["primaryLanguage"] or {}).get("name"), (r["primaryLanguage"] or {}).get("color"))
             for r in u["repositories"]["nodes"] if r["name"].lower() != u["login"].lower()][:5]
    try:
        avatar = load_avatar(u["avatarUrl"])
    except Exception:
        avatar = None
    return u["name"] or u["login"], u["login"], days, repos, avatar


def load_avatar(url):
    r = urllib.request.urlopen(url)
    mime = r.headers.get_content_type() or "image/png"
    return f"data:{mime};base64," + base64.b64encode(r.read()).decode()


def demo(login):
    random.seed(7)
    today = dt.date.today()
    days = [((today - dt.timedelta(days=i)).isoformat(),
             max(0, int(random.gauss(2, 2.5)) if (i // 20) % 3 else int(random.gauss(5, 3))))
            for i in range(364, -1, -1)]
    repos = [("CP05-CTP-WebCrawler", 0, "Python", "#3572A5"), ("CP04-WebDev", 1, "JavaScript", "#f1e05a"),
             ("challenge-fiap-2026-SecDen", 0, "TypeScript", "#3178c6"), ("UkrAid", 2, "Python", "#3572A5"),
             ("portfolio", 0, "HTML", "#e34c26")][:5]
    try:
        avatar = load_avatar(f"https://github.com/{login}.png?size=96")
    except Exception:
        avatar = None
    return "Raul Azzi Corsi", login, days, repos, avatar


def build(name, login, days, repos, avatar):
    counts = [c for _, c in days]
    price = [sum(counts[max(0, i - 29):i + 1]) for i in range(len(counts))]
    # align to the end so the last candle is the current (possibly partial) week
    n = WEEKS * 7
    p, c = price[-n:], counts[-n:]
    candles = []
    for w in range(WEEKS):
        seg = p[w * 7:(w + 1) * 7]
        prev = p[w * 7 - 1] if w else price[-n - 1]
        candles.append((prev, seg[-1], max(seg + [prev]), min(seg + [prev]), sum(c[w * 7:(w + 1) * 7])))

    now, ago = price[-1], price[-29]
    pct = (now - ago) / ago * 100 if ago else (100.0 if now else 0.0)
    up = pct >= 0
    langs = {}
    for _, _, lang, col in repos:
        if lang:
            langs[lang] = (langs.get(lang, (0, col))[0] + 1, col)
    sector = max(langs, key=lambda k: langs[k][0]) if langs else "Code"

    W, H = 760, 380
    G, R, MUTED, FG, GRID = "#3fb950", "#f85149", "#8b949e", "#e6edf3", "#21262d"
    cx0, cx1, cy0, cy1 = 32, W - 32, 86, 246
    vy0, vy1 = 256, 296
    hi = max(x[2] for x in candles) or 1
    lo = min(x[3] for x in candles)
    span = (hi - lo) or 1
    Y = lambda v: cy1 - (v - lo) / span * (cy1 - cy0)
    step = (cx1 - cx0) / WEEKS
    bw = step * 0.6
    vmax = max(x[4] for x in candles) or 1

    out = []
    for k in range(5):
        y = cy0 + k * (cy1 - cy0) / 4
        out.append(f'<line x1="{cx0}" x2="{cx1}" y1="{y:.1f}" y2="{y:.1f}" stroke="{GRID}"/>')
    for i, (o, cl, h, l, v) in enumerate(candles):
        x = cx0 + i * step + step / 2
        col = G if cl >= o else R
        top, bot = Y(max(o, cl)), Y(min(o, cl))
        d = 0.04 * i
        out.append(f'<g class="c" style="animation-delay:{d:.2f}s">'
                   f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{Y(h):.1f}" y2="{Y(l):.1f}" stroke="{col}" stroke-width="1.5"/>'
                   f'<rect x="{x - bw / 2:.1f}" y="{top:.1f}" width="{bw:.1f}" height="{max(bot - top, 2):.1f}" rx="1.5" fill="{col}"/></g>')
        vh = v / vmax * (vy1 - vy0)
        if v:
            out.append(f'<rect class="c" style="animation-delay:{d:.2f}s" x="{x - bw / 2:.1f}" y="{vy1 - vh:.1f}" '
                       f'width="{bw:.1f}" height="{vh:.1f}" rx="1.5" fill="#30363d"/>')

    items, xpos = [], 0
    for rname, stars, lang, col in repos:
        label = html.escape(rname.upper()[:22])
        items.append(f'<rect x="{xpos}" y="-8" width="10" height="10" rx="2" fill="none" stroke="{col or MUTED}" stroke-width="2"/>'
                     f'<text x="{xpos + 18}" y="1" fill="{FG}">{label} <tspan fill="{MUTED}">★{stars}</tspan></text>')
        xpos += 18 + len(label) * 8 + 70
    track = "".join(items)

    av = (f'<clipPath id="av"><circle cx="54" cy="46" r="20"/></clipPath>'
          f'<image href="{avatar}" x="34" y="26" width="40" height="40" preserveAspectRatio="xMidYMid slice" clip-path="url(#av)"/>'
          if avatar else f'<circle cx="54" cy="46" r="20" fill="#30363d"/>')
    arrow = "▲" if up else "▼"
    updated = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<style>
text{{font-family:"JetBrains Mono",ui-monospace,SFMono-Regular,Consolas,monospace}}
.c{{opacity:0;animation:in .4s ease-out forwards}}
@keyframes in{{from{{opacity:0;transform:translateY(6px)}}to{{opacity:1;transform:none}}}}
.tk{{animation:tk {max(xpos / 40, 10):.0f}s linear infinite}}
@keyframes tk{{to{{transform:translateX(-{xpos}px)}}}}
.pulse{{animation:pulse 2s ease-in-out infinite}}
@keyframes pulse{{50%{{opacity:.3}}}}
</style>
<rect width="{W}" height="{H}" rx="14" fill="#0d1117" stroke="#30363d"/>
{av}
<text x="86" y="40" fill="{FG}" font-size="17" font-weight="700">{html.escape(name)}</text>
<text x="86" y="60" fill="{MUTED}" font-size="12">@{html.escape(login)} · contributions / 30 days</text>
<text x="{W - 32}" y="44" text-anchor="end"><tspan fill="{FG}" font-size="28" font-weight="700">{now}</tspan></text>
<text x="{W - 32}" y="64" font-size="12" text-anchor="end" fill="{G if up else R}">{arrow} {abs(pct):.0f}%</text>
{"".join(out)}
<text x="{cx0}" y="312" fill="{MUTED}" font-size="10">each candle = 1 week · bars = contributions that week · last {WEEKS} weeks</text>
<text x="{cx1}" y="312" fill="{MUTED}" font-size="10" text-anchor="end">updated {updated}</text>
<line x1="1" x2="{W - 1}" y1="328" y2="328" stroke="{GRID}"/>
<svg x="0" y="328" width="{W}" height="50"><g font-size="12" font-weight="600" transform="translate(32,29)">
<g class="tk">{"".join(f'<g transform="translate({k * xpos},0)">{track}</g>' for k in range(-(-W // max(xpos,1)) + 1))}</g></g></svg>
</svg>'''


if __name__ == "__main__":
    login, path = sys.argv[1], sys.argv[2]
    data = demo(login) if "--demo" in sys.argv else fetch(login, os.environ["GITHUB_TOKEN"])
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    open(path, "w").write(build(*data))
    print(f"wrote {path}")
