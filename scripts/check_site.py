#!/usr/bin/env python3
"""Validate static site local links and required data safety invariants."""
import json
import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
HTML_FILES = [ROOT / "index.html", ROOT / "sources/index.html", ROOT / "review/index.html"]
errors: list[str] = []

for path in HTML_FILES:
    if not path.is_file():
        errors.append(f"missing page: {path.relative_to(ROOT)}")
        continue
    text = path.read_text(encoding="utf-8")
    for attr, target in re.findall(r'\b(href|src)=["\']([^"\']+)["\']', text, re.I):
        if target.startswith(("http://", "https://", "mailto:", "tel:", "#", "data:")):
            continue
        base = path.parent
        local = (base / target.split("#", 1)[0].split("?", 1)[0]).resolve()
        if not local.exists():
            errors.append(f"broken {attr} in {path.relative_to(ROOT)}: {target}")

try:
    matches = json.loads((ROOT / "data/matches.json").read_text(encoding="utf-8"))
    assert matches.get("schema_version") == 1
    assert isinstance(matches.get("matches"), list)
    for entry in matches["matches"]:
        if entry.get("pick"):
            if not entry.get("odds_source_url") or not entry.get("hotspawn_url"):
                errors.append(f"priced row {entry.get('id')} missing a source link")
            pa, pb = entry.get("probability_a"), entry.get("probability_b")
            if not isinstance(pa, (int, float)) or not isinstance(pb, (int, float)) or abs(pa + pb - 100) > .11:
                errors.append(f"priced row {entry.get('id')} has invalid probabilities")
        if not entry.get("hotspawn_url") and matches.get("fetched_at"):
            errors.append(f"published match {entry.get('id')} missing Hotspawn source")
except Exception as exc:
    errors.append(f"data/matches.json validation error: {exc}")

try:
    review = json.loads((ROOT / "data/review.json").read_text(encoding="utf-8"))
    if not isinstance(review.get("flags"), list):
        errors.append("data/review.json flags must be a list")
except Exception as exc:
    errors.append(f"data/review.json validation error: {exc}")

if errors:
    print("Site validation failed:")
    print("\n".join(f" - {error}" for error in errors))
    raise SystemExit(1)
print(f"Validated {len(HTML_FILES)} pages, local links, match data invariants, and review feed.")
