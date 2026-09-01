#!/usr/bin/env python3
"""Regenerates dark_mode.svg / light_mode.svg — the ASCII profile card.

Proportions follow reference/dark_mode.svg: a square ASCII portrait filling the
left half, profile facts on the right. Numbers are fetched live, so rerun this
whenever they should be refreshed:

    curl -sL -o avatar.png https://github.com/pavanlost56.png   # only if the avatar changed
    python3 card.py
"""
from PIL import Image, ImageOps, ImageFilter
from collections import Counter
from datetime import datetime, timezone
from html import escape
import json, os, re, subprocess, sys

COLS, ROWS = 120, 60               # portrait grid, same as the reference card
RAMP = " .:-=+*#"                  # sky drops out entirely; 7 levels for the subject
SKY = 0.45                         # anything brighter than this is background -> blank
FS = 8                             # ascii font-size; cell = 0.6*FS wide, 1.2*FS tall
CW, LH = FS * 0.6, FS * 1.2

MONO = "'Geist Mono','JetBrains Mono',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"
SANS = "'Geist','Geist Sans',ui-sans-serif,-apple-system,'Segoe UI',Inter,sans-serif"

USER = "pavanlost56"
LEETCODE = "pavanlost56"
NAME = "Pavan Kumar Ajmeera"
TAGLINE = "Builds AI models, backend systems, and automation tools."
STACK = ["Python", "Go", "TypeScript", "PyTorch", "AWS"]
TOOLS = {"Codex": "openai", "opencode": "opencode", "Claude Code": "claudecode",
         "VS Code": "visualstudiocode", "git": "git", "Ollama": "ollama", "Docker": "docker"}
# simple-icons pinned per mark: the newest release dropped the OpenAI and VS Code marks,
# so those two come from the last release that still carries them. Never use @latest here —
# jsDelivr resolves it to a build where half these files are 404.
ICON_PIN = {"openai": "11.14.0", "visualstudiocode": "11.14.0"}
ICON_VERSION = "16.29.0"
STATUS = "open to collaborating"

THEMES = {
    "dark":  dict(bg="#09090b", border="#27272a", fg="#fafafa", muted="#a1a1aa",
                  faint="#52525b", chip="#18181b", accent="#4ade80", top="#d4d4d8", bot="#232326"),
    "light": dict(bg="#ffffff", border="#e4e4e7", fg="#09090b", muted="#71717a",
                  faint="#a1a1aa", chip="#fafafa", accent="#16a34a", top="#18181b", bot="#dcdce0"),
}


def fetch(url, data=None):
    cmd = ["curl", "-sS", "-m", "25", url]
    token = os.environ.get("GITHUB_TOKEN")            # CI: 5000 calls/hour, not 60
    if token and "api.github.com" in url:
        cmd += ["-H", f"Authorization: Bearer {token}"]
    if data:
        cmd += ["-H", "Content-Type: application/json", "-H", "Referer: https://leetcode.com",
                "-d", data]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        sys.exit(f"{url}: unexpected response {out[:160]}")


def leetcode(user):
    """Solved counts, straight from LeetCode's public GraphQL API."""
    q = ('{"query":"query($u:String!){matchedUser(username:$u){submitStatsGlobal'
         '{acSubmissionNum{difficulty count}}}}","variables":{"u":"%s"}}' % user)
    data = (fetch("https://leetcode.com/graphql", q).get("data") or {}).get("matchedUser")
    if not data:
        sys.exit(f"leetcode: no stats for {user}")
    return {d["difficulty"]: d["count"] for d in data["submitStatsGlobal"]["acSubmissionNum"]}


def github(user):
    """The same facts the reference card showed: uptime, location, languages, counts."""
    u = fetch(f"https://api.github.com/users/{user}")
    repos = fetch(f"https://api.github.com/users/{user}/repos?per_page=100")
    if "created_at" not in u or not isinstance(repos, list):
        sys.exit(f"github: unexpected payload for {user} (rate limited?)")
    born = datetime.fromisoformat(u["created_at"].replace("Z", "+00:00"))
    months = (datetime.now(timezone.utc) - born).days // 30
    langs = Counter(r["language"] for r in repos if r["language"])
    return dict(
        uptime=f"{months // 12} years, {months % 12} months",
        location=u.get("location") or "—",
        langs=" · ".join(l.replace("Jupyter Notebook", "Jupyter") for l, _ in langs.most_common(5)),
        repos=u["public_repos"], followers=u["followers"],
        stars=sum(r["stargazers_count"] for r in repos),
    )


def icons(slugs):
    """Brand marks from simple-icons, inlined as paths — the card must stay self-contained."""
    out = {}
    for slug in slugs:
        svg = subprocess.run(
            ["curl", "-sSL", "-m", "20",
             f"https://cdn.jsdelivr.net/npm/simple-icons@{ICON_PIN.get(slug, ICON_VERSION)}"
             f"/icons/{slug}.svg"],
            capture_output=True, text=True).stdout
        d = re.findall(r'\sd="([^"]+)"', svg)
        if not d:
            sys.exit(f"icon: could not read {slug}")
        out[slug] = d
    return out


def ascii_art():
    """The whole photo, not just its silhouette: every cell gets a character for its
    density and an opacity for its tone, so the sky stays a faint texture and the
    subject carries the contrast. Returns rows of (chars, opacity) runs."""
    im = Image.open("avatar.png").convert("L")
    im = im.filter(ImageFilter.MedianFilter(3))
    im = ImageOps.autocontrast(im, cutoff=1)
    im = im.resize((COLS, ROWS), Image.LANCZOS)
    px, n = im.load(), len(RAMP) - 1
    rows = []
    for r in range(ROWS):
        runs, chars, alpha = [], "", None
        for c in range(COLS):
            d = 1 - px[c, r] / 255                                # darkness
            a = round(d ** 1.6 * 7) / 7                           # 8 tonal steps, background pushed back
            ch = " " if a == 0 else RAMP[round(d * n)]
            if a != alpha:
                if chars:
                    runs.append((chars, alpha))
                chars, alpha = ch, a
            else:
                chars += ch
        runs.append((chars, alpha))
        while runs and not runs[-1][0].strip():                   # trim trailing blanks
            runs.pop()
        rows.append(runs)
    return rows


def mix(a, b, t):
    a, b = [int(a[i:i+2], 16) for i in (1, 3, 5)], [int(b[i:i+2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(a, b))


# SMIL, not CSS — CSS animation does not run inside an <img>-embedded SVG in Chrome.
# Nothing fades in from nothing: a background tab keeps the timeline at t=0, so anything
# that starts invisible stays invisible until the tab is focused.
SWEEP = 5.0          # seconds per pass of the scanline down the portrait


def scanline(i, hot, cold):
    """A light band travels down the portrait, forever. Base fill is the resting
    colour, so a viewer that ignores SMIL still sees the finished portrait."""
    peak = 0.06 + (i / ROWS) * 0.5                  # rows light up top to bottom
    a, b, c = peak - 0.05, peak, peak + 0.09
    assert 0 < a < b < c < 1, (a, b, c)
    return (f'<animate attributeName="fill" values="{cold};{cold};{hot};{cold};{cold}" '
            f'keyTimes="0;{a:.4f};{b:.4f};{c:.4f};1" begin="0s" dur="{SWEEP}s" '
            f'repeatCount="indefinite"/>')


# A light follows the pointer across the portrait and the chips invert under it.
# Both need a live SVG document: GitHub renders this file inside an <img>, which
# receives no mouse events and runs no script, so there it is simply inert.
COMPANION = """<defs>
  <radialGradient id="glow">
    <stop offset="0" stop-color="{fg}" stop-opacity="0.30"/>
    <stop offset="1" stop-color="{fg}" stop-opacity="0"/>
  </radialGradient>
  <linearGradient id="fade">
    <stop offset="0" stop-color="#000"/><stop offset="0.04" stop-color="#fff"/>
    <stop offset="0.93" stop-color="#fff"/><stop offset="1" stop-color="#000"/>
  </linearGradient>
</defs>
<style>
  #spot {{ transition: opacity .35s ease; }}
  .chip rect, .stat {{ transition: fill .18s ease, stroke .18s ease; }}
  .chip:hover rect {{ fill: {fg}; stroke: {fg}; }}
  .chip:hover text {{ fill: {bg}; }}
  .chip:hover path {{ fill: {bg}; }}
  .stat:hover {{ stroke: {muted}; }}
</style>
<script><![CDATA[
  var root = document.documentElement, spot = null;
  root.addEventListener("pointermove", function (e) {{
    spot = spot || document.getElementById("spot");
    var p = root.createSVGPoint();
    p.x = e.clientX; p.y = e.clientY;
    p = p.matrixTransform(root.getScreenCTM().inverse());
    spot.setAttribute("cx", p.x); spot.setAttribute("cy", p.y);
    spot.setAttribute("opacity", "1");
  }});
  root.addEventListener("pointerleave", function () {{
    if (spot) spot.setAttribute("opacity", "0");
  }});
]]></script>"""


def build(theme, art, gh, lc):
    t = THEMES[theme]
    PAD = 28
    W = round(PAD * 2 + COLS * CW + 589)                      # 32 gutter + 557 right column
    H = round(PAD * 2 + ROWS * LH)
    x2 = round(PAD + COLS * CW + 32)                          # right column starts here
    right = W - PAD - x2                                      # its width
    s = ['<?xml version="1.0" encoding="UTF-8"?>',
         f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
         f'role="img" aria-label="{escape(NAME)} — GitHub profile card">',
         COMPANION.format(**t),
         f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="14" fill="{t["bg"]}" '
         f'stroke="{t["border"]}"/>']

    for i, runs in enumerate(art):                            # portrait, fading into the card
        y = PAD + FS + i * LH
        c = mix(t["top"], t["bot"], i / (ROWS - 1))
        body = "".join(escape(chars) if a == 1 else
                       f'<tspan fill-opacity="{a:.3f}">{escape(chars)}</tspan>'
                       for chars, a in runs)
        s.append(f'<text x="{PAD}" y="{y:.1f}" fill="{c}" font-family="{MONO}" '
                 f'font-size="{FS}" xml:space="preserve">{body}'
                 f'{scanline(i, t["fg"], c)}</text>')

    s.append(f'<circle id="spot" cx="-400" cy="-400" r="150" fill="url(#glow)" '
             f'opacity="0" pointer-events="none"/>')

    def text(x, y, fill, size, body, family=MONO, extra=""):
        s.append(f'<text x="{x}" y="{y}" fill="{fill}" font-family="{family}" '
                 f'font-size="{size}"{extra}>{body}</text>')

    y = PAD + 40
    text(x2, y, t["fg"], 32, escape(NAME), SANS, ' font-weight="600" letter-spacing="-0.6"')
    y += 26
    text(x2, y, t["muted"], 13, f"@{USER}")
    y += 40
    text(x2, y, t["muted"], 15, escape(TAGLINE), SANS)
    y += 28
    s.append(f'<line x1="{x2}" y1="{y}" x2="{W-PAD}" y2="{y}" stroke="{t["border"]}"/>')

    for label, value in (("location", gh["location"]),        # the reference card's facts
                         ("languages", gh["langs"])):
        y += 36
        text(x2, y, t["faint"], 12, label, MONO, ' letter-spacing="0.6"')
        text(x2 + 96, y, t["fg"], 13, escape(value))

    def chip(bx, y, label, slug=None):
        """A pill; with an icon when the tool has a brand mark."""
        w = len(label) * 7.3 + (46 if slug else 22)
        g = [f'<g class="chip"><rect x="{bx:.1f}" y="{y}" width="{w:.0f}" height="24" rx="12" '
             f'fill="{t["chip"]}" stroke="{t["border"]}"/>']
        if slug:
            for d in ICONS[slug]:
                g.append(f'<path d="{d}" fill="{t["muted"]}" '
                         f'transform="translate({bx+13:.1f} {y+6}) scale(0.5)"/>')
            g.append(f'<text x="{bx+33:.1f}" y="{y+16}" fill="{t["muted"]}" font-family="{MONO}" '
                     f'font-size="12">{escape(label)}</text>')
        else:
            g.append(f'<text x="{bx+w/2:.1f}" y="{y+16}" fill="{t["muted"]}" font-family="{MONO}" '
                     f'font-size="12" text-anchor="middle">{escape(label)}</text>')
        s.append("".join(g) + "</g>")
        return w + 8

    def marquee(y, name, items, leftwards=True):
        """Both rows are wider than the column, so each drifts past behind a fading
        mask. The set is drawn twice and shifted by exactly one set width, which is
        what makes the loop seamless."""
        run = sum(len(label) * 7.3 + (54 if slug else 30) for label, slug in items)
        if run <= right:                                      # fits: no reason to move
            bx = x2
            for label, slug in items:
                bx += chip(bx, y, label, slug)
            return
        a, b = (0, -run) if leftwards else (-run, 0)
        s.append(f'<mask id="{name}fade"><rect x="{x2}" y="{y-4}" width="{right}" height="32" '
                 f'fill="url(#fade)"/></mask>')
        s.append(f'<g mask="url(#{name}fade)"><g>'
                 f'<animateTransform attributeName="transform" type="translate" '
                 f'values="{a:.0f} 0;{b:.0f} 0" dur="{run / 26:.0f}s" repeatCount="indefinite"/>')
        for copy in (0, 1):                                   # second copy closes the loop
            bx = x2 + copy * run
            for label, slug in items:
                bx += chip(bx, y, label, slug)
        s.append('</g></g>')

    for name, items, leftwards in (("stack", [(b, None) for b in STACK], False),
                                   ("tools", list(TOOLS.items()), True)):
        y += 32
        text(x2, y, t["faint"], 11, name, MONO, ' letter-spacing="0.8"')
        y += 10
        marquee(y, name, items, leftwards)
        y += 24

    y += 30                                                   # counters, above the footer
    cw, ch, gap = (right - 17) / 2, 96, 17
    for x, label, big, small, rows in (
            (x2, "leetcode", lc["All"], "solved",
             [(d.lower(), lc[d]) for d in ("Easy", "Medium", "Hard")]),
            (x2 + cw + gap, "github", gh["repos"], "repos",
             [("stars", gh["stars"]), ("followers", gh["followers"])])):
        s.append(f'<rect class="stat" x="{x:.0f}" y="{y}" width="{cw:.0f}" height="{ch}" rx="10" '
                 f'fill="{t["chip"]}" stroke="{t["border"]}"/>')
        text(x + 20, y + 26, t["faint"], 11, label, MONO, ' letter-spacing="0.8"')
        text(x + 20, y + 68, t["fg"], 30, big, SANS, ' font-weight="600" letter-spacing="-0.5"')
        text(x + 20 + len(str(big)) * 19 + 6, y + 68, t["muted"], 13, small)
        for k, (name, n) in enumerate(rows):
            text(x + cw - 20, y + 28 + k * 17, t["faint"], 11,
                 f'{name} <tspan fill="{t["muted"]}">{n}</tspan>', MONO, ' text-anchor="end"')

    y = H - PAD - 10                                          # footer
    s.append(f'<circle cx="{x2+4}" cy="{y-4}" r="4" fill="{t["accent"]}"/>')
    text(x2 + 18, y, t["muted"], 12, STATUS)
    text(W - PAD, y, t["faint"], 12, f"github.com/{USER}", MONO, ' text-anchor="end"')
    s.append("</svg>")
    return "\n".join(s) + "\n"


gh, lc = github(USER), leetcode(LEETCODE)
ICONS = icons(set(TOOLS.values()))
art = ascii_art()
for theme, path in (("dark", "dark_mode.svg"), ("light", "light_mode.svg")):
    open(path, "w").write(build(theme, art, gh, lc))
    print("wrote", path)
