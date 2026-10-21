#!/usr/bin/env python3
"""Verify every internal link and asset reference resolves, and that required pages exist.

Fails with a non-zero exit code if anything is broken, so a broken site can never be published.
External links are counted but not fetched (they are citations for a human to open).
"""
import os, re, sys

PAGES = ["index.html", "picks.html", "unresolved.html", "methodology.html",
         "sources.html", "review.html"]
ASSETS = ["assets/style.css", "assets/app.js"]
REQUIRED_IDS = {"index.html": ["exec", "where"]}


def main():
    errors, warnings = [], []
    local_refs, external, anchors = set(), set(), set()

    for p in PAGES:
        if not os.path.exists(p):
            errors.append(f"missing page: {p}")
            continue
        html = open(p, encoding="utf-8").read()
        if "<html" not in html or "</html>" not in html:
            errors.append(f"{p}: not a complete HTML document")
        if 'name="viewport"' not in html:
            errors.append(f"{p}: missing mobile viewport meta tag")
        for ref in re.findall(r'(?:href|src)="([^"]+)"', html):
            if ref.startswith(("http://", "https://")):
                external.add(ref)
            elif ref.startswith(("#", "data:", "mailto:", "javascript:")):
                if ref.startswith("#") and len(ref) > 1:
                    anchors.add((p, ref[1:]))
            else:
                path, _, frag = ref.partition("#")
                path = path.split("?")[0]
                if path:
                    local_refs.add((p, path))
                if frag:
                    anchors.add((path or p, frag))

    for a in ASSETS:
        if not os.path.exists(a):
            errors.append(f"missing asset: {a}")

    for page, target in sorted(local_refs):
        if not target:
            continue
        if not os.path.exists(target):
            errors.append(f"{page}: broken link -> {target}")

    # anchors must exist as an id in the target page
    for page, anchor in sorted(anchors):
        target = page or "index.html"
        if not os.path.exists(target):
            errors.append(f"{page}: anchor #{anchor} in missing page {target}")
            continue
        html = open(target, encoding="utf-8").read()
        if f'id="{anchor}"' not in html:
            errors.append(f"{page}: missing anchor #{anchor} in {target}")

    for page, ids in REQUIRED_IDS.items():
        if not os.path.exists(page):
            continue
        html = open(page, encoding="utf-8").read()
        for a in ids:
            if f'id="{a}"' not in html:
                errors.append(f"{page}: missing anchor #{a}")

    # every pick card must carry at least one source link
    picks = open("picks.html", encoding="utf-8").read() if os.path.exists("picks.html") else ""
    cards = picks.count('<article class="card"')
    srcs = picks.count('<div class="src">')
    if cards != srcs:
        errors.append(f"picks.html: {cards} cards but {srcs} source rows")

    print(f"pages={len(PAGES)} assets={len(ASSETS)} cards={cards} "
          f"internal_refs={len(local_refs)} anchors={len(anchors)} "
          f"external_refs={len(external)}")
    for w in warnings:
        print(f"WARN {w}")
    if errors:
        print("\nBROKEN:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("link check OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
