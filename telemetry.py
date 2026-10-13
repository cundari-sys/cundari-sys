#!/usr/bin/env python3
"""
Telemetry generator — builds the neon SVG cards of the profile README
straight from the GitHub GraphQL API. No third-party services involved
(no vercel apps that go down or get rate-limited), stdlib only.

Env:
  GH_USER   GitHub login            (default: cundari-sys)
  GH_TOKEN  token for the API       (GITHUB_TOKEN works; a PAT with read:user
                                     also counts private contributions)
Run without a token to (re)generate the "awaiting first sync" placeholders.
"""
import os, sys, json, math, datetime as dt, urllib.request
from xml.sax.saxutils import escape as esc

BG, CY, MG, PU, GR = "#0A0014", "#00F0FF", "#FF2BD6", "#B026FF", "#39FF14"
TX, DIM = "#C9D1D9", "#8B949E"
MONO = "ui-monospace,'SF Mono','Fira Code',Menlo,Consolas,'DejaVu Sans Mono',monospace"
SANS = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"
USER = os.environ.get("GH_USER", "cundari-sys")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

# ───────────────────────── shared drawing helpers ─────────────────────────
def wrap(w, h, body, defs=""):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" font-family="{MONO}">'
        f"<defs>{defs}"
        '<filter id="glow" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="3" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
        f'<linearGradient id="edge" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{CY}"/>'
        f'<stop offset=".5" stop-color="{PU}"/><stop offset="1" stop-color="{MG}"/></linearGradient>'
        f'<linearGradient id="bgp" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#14002e"/>'
        f'<stop offset="1" stop-color="{BG}"/></linearGradient>'
        f'<linearGradient id="hz" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{CY}"/>'
        f'<stop offset=".5" stop-color="{PU}"/><stop offset="1" stop-color="{MG}"/></linearGradient>'
        "</defs>"
        f"{body}</svg>"
    )

def panel(w, h, title, right="", pending=False):
    s = (
        f'<rect x="1.5" y="1.5" width="{w-3}" height="{h-3}" rx="16" fill="url(#bgp)" stroke="url(#edge)" stroke-width="2"/>'
        f'<rect x="1.5" y="1.5" width="{w-3}" height="{h-3}" rx="16" fill="none" stroke="{CY}" stroke-width="3" '
        f'pathLength="1000" stroke-dasharray="70 930" stroke-linecap="round" filter="url(#glow)">'
        '<animate attributeName="stroke-dashoffset" from="0" to="-1000" dur="8s" repeatCount="indefinite"/></rect>'
        f'<circle cx="30" cy="34" r="5" fill="{GR}"><animate attributeName="opacity" values="1;.25;1" dur="1.6s" repeatCount="indefinite"/></circle>'
        f'<text x="46" y="39" font-size="15" font-weight="700" letter-spacing="3" fill="{CY}">{esc(title)}</text>'
    )
    if right:
        s += f'<text x="{w-28}" y="39" font-size="13" text-anchor="end" fill="{DIM}">{esc(right)}</text>'
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    if pending:
        s += (f'<text x="{w-28}" y="{h-16}" font-size="12" text-anchor="end" fill="{MG}" letter-spacing="1">'
              'AWAITING FIRST SYNC · run the "Telemetry" workflow'
              '<animate attributeName="opacity" values="1;.35;1" dur="2s" repeatCount="indefinite"/></text>')
    else:
        s += f'<text x="{w-28}" y="{h-16}" font-size="11" text-anchor="end" fill="#5b4a78">synced {stamp}</text>'
    return s

def fade(delay):
    return f'<animate attributeName="opacity" from="0" to="1" begin="{delay:.2f}s" dur=".5s" fill="freeze"/>'

def n(v):
    return f"{int(v):,}"

# ───────────────────────── data ─────────────────────────
def empty():
    return dict(login=USER, pending=True, stars=0, forks=0, commits=0, prs=0, issues=0, reviews=0,
                repos=0, followers=0, total=0, calendar=[], langs=[],
                cur=0, cur_range="—", best=0, best_range="—", year_range="last 12 months")

QUERY = """query($login:String!){ user(login:$login){
 followers{totalCount} issues{totalCount} pullRequests{totalCount}
 contributionsCollection{ totalCommitContributions totalPullRequestReviewContributions
   contributionCalendar{ totalContributions weeks{ contributionDays{ date contributionCount }}}}
 repositories(ownerAffiliations:OWNER, isFork:false, first:100, privacy:PUBLIC){ totalCount
   nodes{ stargazerCount forkCount languages(first:8, orderBy:{field:SIZE,direction:DESC}){ edges{ size node{ name color }}}}}}}"""

def fetch(token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json", "User-Agent": "telemetry"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        res = json.load(r)
    if "errors" in res or not res.get("data", {}).get("user"):
        raise RuntimeError(json.dumps(res)[:500])
    u = res["data"]["user"]
    cc = u["contributionsCollection"]
    cal = [(d["date"], d["contributionCount"]) for w in cc["contributionCalendar"]["weeks"] for d in w["contributionDays"]]
    cal.sort()
    repos = u["repositories"]["nodes"]
    langs = {}
    for r_ in repos:
        for e in r_["languages"]["edges"]:
            nm = e["node"]["name"]
            langs.setdefault(nm, [0, e["node"]["color"] or CY])
            langs[nm][0] += e["size"]
    ls = sorted(([k, v[1], v[0]] for k, v in langs.items()), key=lambda x: -x[2])
    d = empty()
    d.update(
        pending=False, stars=sum(r_["stargazerCount"] for r_ in repos), forks=sum(r_["forkCount"] for r_ in repos),
        commits=cc["totalCommitContributions"], prs=u["pullRequests"]["totalCount"], issues=u["issues"]["totalCount"],
        reviews=cc["totalPullRequestReviewContributions"], repos=u["repositories"]["totalCount"],
        followers=u["followers"]["totalCount"], total=cc["contributionCalendar"]["totalContributions"],
        calendar=cal, langs=ls,
    )
    streaks(d)
    return d

def streaks(d):
    cal = d["calendar"]
    if not cal:
        return
    today = dt.date.today().isoformat()
    best = cur = 0
    best_end = best_start = None
    run_start = None
    runs = []
    for day, c in cal:
        if day > today:
            continue
        if c > 0:
            if cur == 0:
                run_start = day
            cur += 1
            runs.append((cur, run_start, day))
        else:
            cur = 0
    if runs:
        b = max(runs, key=lambda r: r[0])
        best, best_start, best_end = b
    yday = (dt.date.today() - dt.timedelta(days=1)).isoformat()
    curr = [r for r in runs if r[2] in (today, yday)]
    c = max(curr, key=lambda r: r[1], default=None)
    fmt = lambda s: dt.date.fromisoformat(s).strftime("%b %d, %Y").replace(" 0", " ")
    d["best"] = best
    d["best_range"] = f"{fmt(best_start)} – {fmt(best_end)}" if best else "—"
    if c:
        end = c[2]
        full = max((r for r in runs if r[2] == end), key=lambda r: r[0])
        d["cur"] = full[0]
        d["cur_range"] = f"{fmt(full[1])} – {fmt(full[2])}"
    else:
        d["cur"], d["cur_range"] = 0, "—"
    d["year_range"] = f"{fmt(cal[0][0])} – {fmt(cal[-1][0])}"

# ───────────────────────── cards ─────────────────────────
def grade(score):
    for t, g in [(2000, "S"), (1000, "A+"), (500, "A"), (250, "B+"), (120, "B"), (50, "C+")]:
        if score >= t:
            return g
    return "C"

def render_stats(d):
    W, H = 600, 310
    score = d["commits"] + 3 * d["prs"] + 2 * d["reviews"] + d["issues"] + 4 * d["stars"] + 2 * d["followers"] + d["repos"]
    g = grade(score)
    frac = min(1, score / 2000) * 100
    rows = [("STARS EARNED", d["stars"], MG), ("COMMITS / 12 MO", d["commits"], CY), ("PULL REQUESTS", d["prs"], PU),
            ("ISSUES OPENED", d["issues"], GR), ("CODE REVIEWS", d["reviews"], CY), ("PUBLIC REPOS", d["repos"], MG),
            ("FOLLOWERS", d["followers"], PU)]
    b = panel(W, H, "TELEMETRY", "@" + d["login"], d["pending"])
    for i, (lab, val, col) in enumerate(rows):
        y = 92 + i * 29
        b += (f'<g opacity="0">{fade(0.15 * i)}<rect x="30" y="{y-11}" width="8" height="8" rx="2" fill="{col}" filter="url(#glow)"/>'
              f'<text x="50" y="{y-3}" font-size="14" fill="{TX}" letter-spacing="1">{lab}</text>'
              f'<text x="330" y="{y-3}" font-size="16" font-weight="700" text-anchor="end" fill="{col}">{n(val)}</text>'
              f'<line x1="50" y1="{y+7}" x2="330" y2="{y+7}" stroke="#2a1245" stroke-width="1"/></g>')
    cx, cy, r = 468, 168, 66
    b += (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#24103f" stroke-width="12"/>'
          f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="url(#edge)" stroke-width="12" stroke-linecap="round" '
          f'pathLength="100" stroke-dasharray="0 100" transform="rotate(-90 {cx} {cy})" filter="url(#glow)">'
          f'<animate attributeName="stroke-dasharray" from="0 100" to="{frac:.1f} 100" dur="1.8s" fill="freeze" calcMode="spline" keySplines=".2 .8 .2 1" keyTimes="0;1"/></circle>'
          f'<text x="{cx}" y="{cy+16}" font-size="46" font-weight="800" text-anchor="middle" fill="url(#hz)" font-family="{SANS}">{g}</text>'
          f'<text x="{cx}" y="{cy-26}" font-size="11" letter-spacing="3" text-anchor="middle" fill="{DIM}">RANK</text>'
          f'<text x="{cx}" y="{cy+r+30}" font-size="12" letter-spacing="2" text-anchor="middle" fill="{DIM}">SCORE {n(score)}</text>')
    return wrap(W, H, b)

def render_langs(d):
    W, H = 600, 310
    b = panel(W, H, "LANGUAGE MATRIX", "by code size", d["pending"])
    langs = d["langs"][:]
    total = sum(x[2] for x in langs) or 1
    top = langs[:6]
    rest = sum(x[2] for x in langs[6:])
    if rest:
        top.append(["Other", DIM, rest])
    x0, bw = 30, 540
    clip = (f'<clipPath id="lb"><rect x="{x0}" y="70" width="{bw}" height="16" rx="8"/></clipPath>'
            f'<clipPath id="lr"><rect x="{x0}" y="60" width="0" height="36"><animate attributeName="width" from="0" to="{bw}" dur="1.4s" fill="freeze" calcMode="spline" keySplines=".2 .8 .2 1" keyTimes="0;1"/></rect></clipPath>')
    if not langs:
        b += f'<rect x="{x0}" y="70" width="{bw}" height="16" rx="8" fill="#24103f"/>'
        b += f'<text x="{x0}" y="130" font-size="14" fill="{DIM}">No data yet — pushed code will show up here.</text>'
        return wrap(W, H, b, clip)
    b += f'<g clip-path="url(#lr)"><g clip-path="url(#lb)">'
    x = x0
    for nm, col, sz in top:
        w = bw * sz / total
        b += f'<rect x="{x:.1f}" y="70" width="{w+0.6:.1f}" height="16" fill="{col}"/>'
        x += w
    b += "</g></g>"
    for i, (nm, col, sz) in enumerate(top):
        cx_ = x0 if i % 2 == 0 else 320
        y = 128 + (i // 2) * 52
        pct = 100 * sz / total
        b += (f'<g opacity="0">{fade(0.2 + 0.12 * i)}<circle cx="{cx_+6}" cy="{y-5}" r="6" fill="{col}" filter="url(#glow)"/>'
              f'<text x="{cx_+22}" y="{y}" font-size="15" fill="{TX}" font-weight="700">{esc(nm)}</text>'
              f'<text x="{cx_+250}" y="{y}" font-size="15" text-anchor="end" fill="{col}">{pct:.1f}%</text>'
              f'<rect x="{cx_}" y="{y+10}" width="250" height="5" rx="2.5" fill="#24103f"/>'
              f'<rect x="{cx_}" y="{y+10}" width="0" height="5" rx="2.5" fill="{col}"><animate attributeName="width" from="0" to="{max(3, 250*pct/100):.1f}" begin="{0.2+0.12*i:.2f}s" dur="1s" fill="freeze"/></rect></g>')
    return wrap(W, H, b, clip)

def render_streak(d):
    W, H = 1200, 250
    b = panel(W, H, "CONTRIBUTION STREAK", d["year_range"], d["pending"])
    cols = [(200, d["total"], "CONTRIBUTIONS", "last 12 months", CY),
            (600, d["cur"], "CURRENT STREAK", d["cur_range"], MG),
            (1000, d["best"], "LONGEST STREAK", d["best_range"], GR)]
    for x in (400, 800):
        b += f'<line x1="{x}" y1="70" x2="{x}" y2="205" stroke="#2a1245" stroke-width="2" stroke-dasharray="3 7"/>'
    for i, (cx, val, lab, sub, col) in enumerate(cols):
        if i == 1:
            r = 58
            frac = 0 if not d["best"] else min(1, d["cur"] / d["best"]) * 100
            b += (f'<circle cx="{cx}" cy="128" r="{r}" fill="none" stroke="#24103f" stroke-width="9"/>'
                  f'<circle cx="{cx}" cy="128" r="{r}" fill="none" stroke="{col}" stroke-width="9" stroke-linecap="round" pathLength="100" '
                  f'stroke-dasharray="0 100" transform="rotate(-90 {cx} 128)" filter="url(#glow)">'
                  f'<animate attributeName="stroke-dasharray" from="0 100" to="{frac:.1f} 100" dur="1.8s" fill="freeze"/></circle>'
                  f'<text x="{cx}" y="{128+16}" font-size="46" font-weight="800" text-anchor="middle" fill="{col}" font-family="{SANS}">{n(val)}</text>'
                  f'<text x="{cx}" y="{128-24}" font-size="11" letter-spacing="3" text-anchor="middle" fill="{DIM}">DAYS</text>')
            b += f'<text x="{cx}" y="214" font-size="13" letter-spacing="3" text-anchor="middle" fill="{col}" font-weight="700">{lab}</text>'
            b += f'<text x="{cx}" y="232" font-size="12" text-anchor="middle" fill="{DIM}">{esc(sub)}</text>'
        else:
            b += (f'<text x="{cx}" y="150" font-size="64" font-weight="800" text-anchor="middle" fill="{col}" font-family="{SANS}" filter="url(#glow)" opacity="0">{n(val)}{fade(0.3*i)}</text>'
                  f'<text x="{cx}" y="190" font-size="13" letter-spacing="3" text-anchor="middle" fill="{col}" font-weight="700">{lab}</text>'
                  f'<text x="{cx}" y="212" font-size="12" text-anchor="middle" fill="{DIM}">{esc(sub)}</text>')
    return wrap(W, H, b)

def smooth(pts, ytop, ybase, t=0.17):
    d_ = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
    cl = lambda y: max(ytop, min(ybase, y))
    for i in range(len(pts) - 1):
        p0 = pts[i - 1] if i else pts[i]
        p1, p2 = pts[i], pts[i + 1]
        p3 = pts[i + 2] if i + 2 < len(pts) else p2
        c1 = (p1[0] + (p2[0] - p0[0]) * t, cl(p1[1] + (p2[1] - p0[1]) * t))
        c2 = (p2[0] - (p3[0] - p1[0]) * t, cl(p2[1] - (p3[1] - p1[1]) * t))
        d_ += f" C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}"
    return d_

def render_activity(d):
    W, H = 1200, 300
    days = [c for _, c in d["calendar"][-120:]] or [0] * 120
    dates = [x for x, _ in d["calendar"][-120:]]
    b = panel(W, H, "ACTIVITY WAVEFORM", f"last {len(days)} days · {n(sum(days))} contributions", d["pending"])
    x0, x1, yt, yb = 56, 1146, 84, 244
    mx = max(max(days), 4)
    step = -(-mx // 4)
    mx = step * 4
    for k in range(5):
        y = yb - (yb - yt) * k / 4
        b += (f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" stroke="#24103f" stroke-width="1"/>'
              f'<text x="{x0-10}" y="{y+4:.1f}" font-size="11" text-anchor="end" fill="{DIM}">{step*k}</text>')
    pts = [(x0 + (x1 - x0) * i / max(1, len(days) - 1), yb - (yb - yt) * v / mx) for i, v in enumerate(days)]
    line = smooth(pts, yt, yb)
    area = f"{line} L{pts[-1][0]:.1f},{yb} L{pts[0][0]:.1f},{yb} Z"
    seen = set()
    for i, dd in enumerate(dates):
        m = dd[:7]
        if m not in seen and dd[8:10] <= "07":
            seen.add(m)
            lab = dt.date.fromisoformat(dd).strftime("%b").upper()
            b += f'<text x="{pts[i][0]:.1f}" y="{yb+22}" font-size="11" text-anchor="middle" fill="{DIM}" letter-spacing="1">{lab}</text>'
    defs = (f'<linearGradient id="ar" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{MG}" stop-opacity=".55"/>'
            f'<stop offset=".6" stop-color="{PU}" stop-opacity=".18"/><stop offset="1" stop-color="{PU}" stop-opacity="0"/></linearGradient>'
            f'<clipPath id="rv"><rect x="{x0-4}" y="60" width="0" height="220"><animate attributeName="width" from="0" to="{x1-x0+12}" dur="2.2s" fill="freeze" calcMode="spline" keySplines=".3 .7 .2 1" keyTimes="0;1"/></rect></clipPath>')
    b += (f'<g clip-path="url(#rv)"><path d="{area}" fill="url(#ar)"/></g>'
          f'<path d="{line}" fill="none" stroke="url(#hz)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" pathLength="1000" '
          f'stroke-dasharray="1000" stroke-dashoffset="1000" filter="url(#glow)"><animate attributeName="stroke-dashoffset" from="1000" to="0" dur="2.2s" fill="freeze" calcMode="spline" keySplines=".3 .7 .2 1" keyTimes="0;1"/></path>'
          f'<circle cx="{pts[-1][0]:.1f}" cy="{pts[-1][1]:.1f}" r="5" fill="{GR}" filter="url(#glow)" opacity="0">{fade(2.2)}</circle>'
          f'<circle cx="{pts[-1][0]:.1f}" cy="{pts[-1][1]:.1f}" r="5" fill="none" stroke="{GR}" stroke-width="2"><animate attributeName="r" values="5;18" dur="1.8s" begin="2.2s" repeatCount="indefinite"/>'
          f'<animate attributeName="opacity" values=".9;0" dur="1.8s" begin="2.2s" repeatCount="indefinite"/></circle>')
    return wrap(W, H, b, defs)

TIERS = [("LOCKED", "#3a2a52"), ("BRONZE", "#d98b4a"), ("SILVER", "#d5dde8"), ("GOLD", "#ffd23f"), ("PLATINUM", CY)]

def render_trophies(d):
    W, H = 1200, 250
    items = [("STARS", d["stars"], [1, 10, 50, 200]), ("COMMITS", d["commits"], [50, 200, 500, 1000]),
             ("PULL REQ", d["prs"], [1, 10, 50, 150]), ("REPOS", d["repos"], [3, 10, 25, 50]),
             ("FOLLOWERS", d["followers"], [1, 10, 50, 200]), ("STREAK", d["best"], [3, 7, 30, 100]),
             ("ISSUES", d["issues"], [1, 10, 40, 100])]
    b = panel(W, H, "TROPHY ROOM", "tiers unlock as numbers grow", d["pending"])
    defs = ""
    gap = W / len(items)
    for i, (lab, val, th) in enumerate(items):
        tier = sum(val >= t for t in th)
        name, col = TIERS[tier]
        cx, cy, r = gap * (i + .5), 118, 46
        pts = " ".join(f"{cx + r*math.cos(math.radians(60*k-90)):.1f},{cy + r*math.sin(math.radians(60*k-90)):.1f}" for k in range(6))
        defs += (f'<clipPath id="hx{i}"><polygon points="{pts}"/></clipPath>'
                 f'<linearGradient id="tg{i}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{col}" stop-opacity="{.95 if tier else .35}"/>'
                 f'<stop offset="1" stop-color="{col}" stop-opacity="{.35 if tier else .15}"/></linearGradient>')
        nxt = th[tier] if tier < 4 else None
        glow = ' filter="url(#glow)"' if tier else ""
        nxt_txt = "" if nxt is None else f" · next {n(nxt)}"
        b += (f'<g><animateTransform attributeName="transform" type="translate" values="0,0;0,-6;0,0" dur="{3+i*.35:.2f}s" repeatCount="indefinite" calcMode="spline" keyTimes="0;.5;1" keySplines=".4 0 .6 1;.4 0 .6 1"/>'
              f'<polygon points="{pts}" fill="url(#tg{i})" stroke="{col}" stroke-width="3" stroke-linejoin="round"{glow}/>'
              f'<g clip-path="url(#hx{i})"><rect x="{cx-90}" y="{cy-70}" width="22" height="140" fill="#fff" opacity="{.28 if tier else .08}" transform="rotate(20 {cx} {cy})">'
              f'<animate attributeName="x" values="{cx-120};{cx+120};{cx+120}" keyTimes="0;.35;1" dur="{4+i*.4:.1f}s" repeatCount="indefinite"/></rect></g>'
              f'<text x="{cx}" y="{cy+9}" font-size="26" font-weight="800" text-anchor="middle" fill="{"#0A0014" if tier >= 2 else TX}" font-family="{SANS}">{n(val)}</text></g>'
              f'<text x="{cx}" y="{cy+r+32}" font-size="13" letter-spacing="3" text-anchor="middle" fill="{TX}" font-weight="700">{lab}</text>'
              f'<text x="{cx}" y="{cy+r+50}" font-size="11" letter-spacing="2" text-anchor="middle" fill="{col}">{name}{nxt_txt}</text>')
    return wrap(W, H, b, defs)

def render_all(d, out=OUT):
    os.makedirs(out, exist_ok=True)
    for name, fn in [("stats", render_stats), ("langs", render_langs), ("streak", render_streak),
                     ("activity", render_activity), ("trophies", render_trophies)]:
        with open(os.path.join(out, f"{name}.svg"), "w", encoding="utf-8") as f:
            f.write(fn(d))
        print("wrote", name + ".svg")

if __name__ == "__main__":
    tok = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not tok:
        print("no token → writing placeholders")
        render_all(empty())
        sys.exit(0)
    render_all(fetch(tok))
