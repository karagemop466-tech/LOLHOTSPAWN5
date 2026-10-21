#!/usr/bin/env python3
"""Shared helpers: HTTP client, source health log, name normalisation.

Design rules for this project:
  * HotSpawn is a *fixture inventory* source only. Its crowd percentages are never
    read into the probability model (see collect_hotspawn.py).
  * Every external number that reaches the site carries the URL it came from and
    the moment it was retrieved.
  * If a source cannot be read, the failure is recorded - never silently filled in.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import ssl
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO_ROOT, "data")
EVIDENCE_DIR = os.path.join(REPO_ROOT, "evidence")

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0.0.0 Safari/537.36")

# Words that carry no identifying signal in an esports org name.
FILLER = {
    "esports", "e", "sport", "gaming", "team", "club", "gg", "academy", "ac",
    "the", "of", "gaming", "org", "squad", "lineup", "roster", "play", "vs",
}


class Http:
    """Small JSON/text fetcher that records every request in a health log."""

    def __init__(self, log_path: str | None = None, delay: float = 0.4):
        self.log_path = log_path
        self.delay = delay
        self.records: list[dict] = []
        self._ctx = ssl.create_default_context()

    def _record(self, entry: dict) -> None:
        self.records.append(entry)
        if self.log_path:
            os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
            with open(self.log_path, "w", encoding="utf-8") as fh:
                json.dump({"generated_at": utcnow(), "requests": self.records}, fh, indent=2)

    def get(self, url: str, *, retries: int = 3, timeout: int = 60,
            headers: dict | None = None, sleep: float | None = None) -> tuple[bytes | None, dict]:
        """Return (body, meta). body is None when the request failed."""
        hdrs = {"User-Agent": UA, "Accept": "*/*"}
        hdrs.update(headers or {})
        last_error = None
        for attempt in range(1, retries + 1):
            started = time.time()
            req = urllib.request.Request(url, headers=hdrs, method="GET")
            try:
                with urllib.request.urlopen(req, timeout=timeout, context=self._ctx) as resp:
                    body = resp.read()
                    meta = {
                        "url": url,
                        "status": resp.status,
                        "bytes": len(body),
                        "sha256": hashlib.sha256(body).hexdigest(),
                        "retrieved_at": utcnow(),
                        "content_type": resp.headers.get("Content-Type", ""),
                        "age": resp.headers.get("Age", ""),
                        "x_cache": resp.headers.get("X-Cache", ""),
                        "attempt": attempt,
                        "elapsed_s": round(time.time() - started, 2),
                    }
                    self._record(meta)
                    time.sleep(self.delay if sleep is None else sleep)
                    return body, meta
            except urllib.error.HTTPError as exc:
                body = b""
                try:
                    body = exc.read(400)
                except Exception:  # noqa: BLE001
                    pass
                last_error = f"HTTP {exc.code}: {body[:200].decode('utf-8', 'replace')}"
                meta = {"url": url, "status": exc.code, "error": last_error,
                        "retrieved_at": utcnow(), "attempt": attempt,
                        "elapsed_s": round(time.time() - started, 2)}
                self._record(meta)
                if exc.code in (400, 401, 403, 404):
                    break
            except Exception as exc:  # noqa: BLE001
                last_error = f"{type(exc).__name__}: {exc}"
                self._record({"url": url, "status": None, "error": last_error,
                              "retrieved_at": utcnow(), "attempt": attempt})
            if attempt < retries:
                time.sleep(min(2 ** attempt, 20))
        return None, {"url": url, "status": None, "error": last_error, "retrieved_at": utcnow()}

    def get_json(self, url: str, **kwargs):
        body, meta = self.get(url, **kwargs)
        if body is None:
            return None, meta
        try:
            return json.loads(body.decode("utf-8", "replace")), meta
        except Exception as exc:  # noqa: BLE001
            meta = dict(meta)
            meta["error"] = f"invalid JSON: {exc}"
            return None, meta


def utcnow() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def write_json(rel_path: str, payload) -> str:
    path = os.path.join(REPO_ROOT, rel_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False, sort_keys=False)
        fh.write("\n")
    return path


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value))
    value = value.encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value


def strip_accents(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", value)
                   if not unicodedata.combining(c))


def norm_name(value: str) -> str:
    """Normalised key for team-name matching."""
    value = strip_accents(str(value)).lower()
    value = value.replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def name_tokens(value: str) -> set[str]:
    toks = set(norm_name(value).split())
    return {t for t in toks if t and t not in FILLER}


def team_match_score(a: str, b: str) -> float:
    """Similarity in [0,1] between two team names (no fuzzy typo tolerance)."""
    na, nb = norm_name(a), norm_name(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    ta, tb = name_tokens(a), name_tokens(b)
    if not ta or not tb:
        return 0.0
    inter = ta & tb
    if not inter:
        return 0.0
    jaccard = len(inter) / len(ta | tb)
    coverage = len(inter) / min(len(ta), len(tb))
    return max(jaccard, coverage * 0.9)


def american_to_decimal(american: float) -> float:
    if american is None:
        return None
    if american > 0:
        return round(1 + american / 100.0, 6)
    if american < 0:
        return round(1 + 100.0 / abs(american), 6)
    return None


def devig(p_a: float, p_b: float) -> tuple[float, float]:
    """Remove the bookmaker margin from two implied probabilities."""
    total = p_a + p_b
    if not total:
        return p_a, p_b
    return p_a / total, p_b / total


def implied(decimal_odds: float) -> float:
    if not decimal_odds or decimal_odds <= 1:
        return None
    return 1.0 / decimal_odds


def epoch_ms_to_iso(value) -> str | None:
    if value in (None, ""):
        return None
    try:
        seconds = int(value) / 1000
    except (TypeError, ValueError):
        return None
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(seconds))
