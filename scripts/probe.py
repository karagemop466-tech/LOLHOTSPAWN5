#!/usr/bin/env python3
"""Capture raw payloads from candidate sources so every schema can be verified.

Runs inside GitHub Actions (the runner has full internet). Writes one file per URL
under the output directory and a manifest next to it.

Nothing here is used as a probability signal on its own - the probe only records
what each source actually returns, so downstream code can be written against the
real schema instead of a guess.

Usage:
    python scripts/probe.py --targets targets.json --out evidence/raw2
"""
from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_BYTES = 12 * 1024 * 1024
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0.0.0 Safari/537.36")


def suffix_for(content_type: str, url: str) -> str:
    ct = (content_type or "").lower()
    if "json" in ct:
        return ".json"
    if "csv" in ct:
        return ".csv"
    if "html" in ct:
        return ".html"
    if "text" in ct:
        return ".txt"
    path = urllib.parse.urlparse(url).path
    if path.endswith(".csv"):
        return ".csv"
    if path.endswith(".json"):
        return ".json"
    return ".html"


def fetch(name: str, url: str, extra_headers: dict[str, str], out_dir: str) -> dict:
    headers = {"User-Agent": UA, "Accept": "*/*"}
    headers.update(extra_headers or {})
    req = urllib.request.Request(url, headers=headers, method="GET")
    ctx = ssl.create_default_context()
    started = time.time()
    record: dict = {"name": name, "url": url,
                    "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    try:
        with urllib.request.urlopen(req, timeout=90, context=ctx) as resp:
            body = resp.read(MAX_BYTES)
            record.update({
                "status": resp.status,
                "content_type": resp.headers.get("Content-Type", ""),
                "bytes": len(body),
                "age": resp.headers.get("Age", ""),
                "x_cache": resp.headers.get("X-Cache", ""),
            })
            path = os.path.join(out_dir, name + suffix_for(record["content_type"], url))
            with open(path, "wb") as fh:
                fh.write(body)
            record["file"] = os.path.relpath(path, REPO_ROOT)
            record["sample"] = body[:300].decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        body = exc.read(1500)
        record.update({"status": exc.code, "error": f"HTTPError {exc.code}",
                       "sample": body.decode("utf-8", "replace")[:300]})
    except Exception as exc:  # noqa: BLE001 - a probe must never abort the run
        record.update({"status": None, "error": f"{type(exc).__name__}: {exc}"})
    record["elapsed_s"] = round(time.time() - started, 2)
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets", required=True, help="JSON list of [name, url, headers?]")
    parser.add_argument("--out", required=True, help="output directory (relative to repo root)")
    parser.add_argument("--manifest", default=None, help="manifest path (relative to repo root)")
    parser.add_argument("--delay", type=float, default=0.7)
    args = parser.parse_args()

    targets_path = args.targets if os.path.isabs(args.targets) else os.path.join(REPO_ROOT, args.targets)
    out_dir = args.out if os.path.isabs(args.out) else os.path.join(REPO_ROOT, args.out)
    manifest_path = args.manifest or os.path.join(os.path.dirname(out_dir),
                                                  os.path.basename(out_dir.rstrip("/")) + "_manifest.json")
    if not os.path.isabs(manifest_path):
        manifest_path = os.path.join(REPO_ROOT, manifest_path)

    with open(targets_path, encoding="utf-8") as fh:
        targets = json.load(fh)

    os.makedirs(out_dir, exist_ok=True)
    records = []
    for entry in targets:
        name, url = entry[0], entry[1]
        headers = entry[2] if len(entry) > 2 else {}
        rec = fetch(name, url, headers, out_dir)
        records.append(rec)
        print(f"{name:44s} status={rec.get('status')} bytes={rec.get('bytes', 0)} {rec.get('error', '')}")
        sys.stdout.flush()
        time.sleep(args.delay)

    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump({"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   "targets": records}, fh, indent=2)
    print("wrote", manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
