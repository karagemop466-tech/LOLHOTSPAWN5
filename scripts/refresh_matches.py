#!/usr/bin/env python3
"""Refresh Hotspawn's LoL fixture inventory and attach market-derived odds only.

Fail closed on an unverified game selection, match identity or odds outcome.
Hotspawn pick-share fields are never read for probability calculations.
"""
from __future__ import annotations
import datetime as dt
import html
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MATCH_FILE, REVIEW_FILE = ROOT / "data/matches.json", ROOT / "data/review.json"
HOTSPAWN_LOBBY = os.getenv("HOTSPAWN_LOBBY_URL", "https://play.hotspawn.com/lobby")
HOTSPAWN_API = "https://www.hotspawn.com/wp-json/pickem/v1/fixtures"
ODDS_API = "https://api.oddspapi.io/v4"
ODDS_DOCS = "https://oddspapi.io/sports/esports/lol"
USER_AGENT = "HotspawnLoLPicksDashboard/1.0 (+https://github.com/karagemop466-tech/LOLHOTSPAWN5)"
NOW = dt.datetime.now(dt.timezone.utc)

def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def get_json(url: str) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=40) as response:
        if response.status != 200: raise RuntimeError(f"HTTP {response.status}: {url}")
        return json.loads(response.read().decode("utf-8"))

@dataclass
class Node:
    tag: str
    attrs: dict[str, str]
    parent: "Node | None" = None
    children: list[Any] = field(default_factory=list)
    def text(self) -> str:
        return " ".join(child.text() if isinstance(child, Node) else child for child in self.children)
    def descendants(self, tag: str | None = None):
        for child in self.children:
            if isinstance(child, Node):
                if tag is None or child.tag == tag: yield child
                yield from child.descendants(tag)

from html.parser import HTMLParser
class TreeParser(HTMLParser):
    VOID = {"area","base","br","col","embed","hr","img","input","link","meta","param","source","track","wbr"}
    def __init__(self):
        super().__init__(convert_charrefs=True); self.root=Node("document",{}); self.stack=[self.root]
    def handle_starttag(self, tag, attrs):
        node=Node(tag.lower(),{k.lower():v or "" for k,v in attrs},self.stack[-1]); self.stack[-1].children.append(node)
        if tag.lower() not in self.VOID: self.stack.append(node)
    def handle_startendtag(self,tag,attrs):
        self.handle_starttag(tag,attrs)
        if tag.lower() not in self.VOID: self.handle_endtag(tag)
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,0,-1):
            if self.stack[i].tag==tag.lower(): del self.stack[i:]; break
    def handle_data(self,data):
        if data.strip(): self.stack[-1].children.append(data.strip())

def normalize(value: str) -> str:
    value=unicodedata.normalize("NFKD",value).encode("ascii","ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+","",value)

def is_lol_marker(node: Node) -> bool:
    evidence=[]
    for item in [node,*list(node.descendants())]:
        for key,value in item.attrs.items():
            if key in {"data-game","data-title","data-esport","aria-label","title"}: evidence.append(value.lower())
        classes=item.attrs.get("class","").lower()
        if "active" in classes or "selected" in classes or item.attrs.get("aria-selected","").lower()=="true" or item.attrs.get("aria-pressed","").lower()=="true":
            evidence.append(item.text().lower())
    return bool(re.search(r"\b(?:league\s+of\s+legends|lol)\b"," ".join(evidence)))

def is_lol_card(node: Node, active_lol: bool) -> bool:
    for item in [node,*list(node.descendants())]:
        marker=" ".join(item.attrs.get(k,"") for k in ("data-game","data-title","data-esport","aria-label","title")).lower()
        if re.search(r"\b(?:league\s+of\s+legends|lol)\b",marker): return True
        if re.search(r"\b(?:cs2|counter\s*strike|dota\s*2|valorant)\b",marker): return False
    return active_lol

def extract_cards(document: Node, page_url: str) -> list[dict[str, Any]]:
    active_lol=is_lol_marker(document); matches={}
    for anchor in document.descendants("a"):
        href=urllib.parse.urljoin(page_url,html.unescape(anchor.attrs.get("href","")))
        match=re.search(r"/matches/([^/?#]*?)-(\d+)(?:[/?#]|$)",urllib.parse.urlparse(href).path)
        if not match: continue
        card=anchor.parent; labels=[]
        while card and card.parent:
            labels=list(dict.fromkeys(n.attrs.get("alt","").strip() for n in card.descendants("img") if n.attrs.get("alt","").strip()))
            if len(labels)>=2: break
            card=card.parent
        if not card or len(labels)<2 or not is_lol_card(card,active_lol): continue
        names=list(dict.fromkeys(n.attrs.get("alt","").strip() for n in card.descendants("img") if n.attrs.get("alt","").strip()))
        if len(names)<2: continue
        start=None
        for time_node in card.descendants("time"):
            try:
                parsed=dt.datetime.fromisoformat(time_node.attrs.get("datetime","").replace("Z","+00:00"))
                if parsed.tzinfo:
                    start=parsed.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z"); break
            except ValueError: pass
        event=None
        for item in [card,*list(card.descendants())]:
            event=item.attrs.get("data-tournament","").strip() or item.attrs.get("data-event","").strip()
            if event: break
        matches[match.group(2)]={"id":match.group(2),"team_a":names[0],"team_b":names[1],"tournament":event or None,"format":None,"start_time_utc":start,"hotspawn_url":href,"hotspawn_lobby_url":page_url,"game":"League of Legends","source_evidence":"Hotspawn lobby match link and team logo alt labels","source_text_excerpt":re.sub(r"\s+"," ",card.text()).strip()[:350]}
    if not active_lol and not matches:
        raise RuntimeError("No active LoL marker or game-tagged LoL match cards; refusing to publish a possibly mixed/CS2 board")
    if not matches:
        raise RuntimeError("Selected LoL lobby contained no numeric match links with two labeled team images; refusing to publish an empty or guessed inventory")
    return list(matches.values())

def fetch_hotspawn() -> list[dict[str,Any]]:
    try: from playwright.sync_api import sync_playwright
    except ImportError as exc: raise RuntimeError("Playwright is required to interact with Hotspawn's game selector") from exc
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        page=browser.new_page(user_agent=USER_AGENT)
        page.goto(HOTSPAWN_LOBBY,wait_until="domcontentloaded",timeout=60000)
        page.wait_for_timeout(1500)
        # Click the exact visible LoL UI control; do not rely on an undocumented query parameter.
        controls=page.locator('button, a, [role="tab"], [role="button"]').filter(has_text=re.compile(r"^\s*LoL\s*$",re.I))
        clicked=False
        for i in range(min(controls.count(),8)):
            candidate=controls.nth(i)
            try:
                if candidate.is_visible(timeout=500): candidate.click(timeout=3000); clicked=True; break
            except Exception: continue
        if not clicked:
            browser.close(); raise RuntimeError("Could not find a visible exact LoL tab/control in the Hotspawn lobby")
        page.wait_for_timeout(1200)
        evidence=page.evaluate("""() => [...document.querySelectorAll('button,a,[role=tab],[role=button]')].filter(n=>n.textContent.trim().toLowerCase()==='lol').map(n=>({selected:n.getAttribute('aria-selected'),pressed:n.getAttribute('aria-pressed'),cls:String(n.className||''),parentClass:String(n.parentElement?.className||''),parentSelected:n.parentElement?.getAttribute('aria-selected')}))""")
        active=any(str(x.get("selected","")).lower()=="true" or str(x.get("pressed","")).lower()=="true" or any(token in (str(x.get(key,"")).lower()) for key in ("cls","parentClass") for token in ("active","selected")) or str(x.get("parentSelected","")).lower()=="true" for x in evidence)
        cards=page.evaluate("""() => {
          const records = new Map();
          for (const anchor of document.querySelectorAll('a[href*="/matches/"]')) {
            if (!anchor.getClientRects().length) continue;
            const match = anchor.href.match(/\\/matches\\/[^/?#]*?-(\\d+)(?:[/?#]|$)/);
            if (!match) continue;
            let card = anchor.parentElement;
            let names = [];
            for (let depth=0; card && depth<10; depth++, card=card.parentElement) {
              names = [...new Set([...card.querySelectorAll('img[alt]')].map(img=>img.alt.trim()).filter(Boolean))];
              if (names.length>=2) break;
            }
            if (!card || names.length<2) continue;
            const marker = [card.getAttribute('data-game'),card.getAttribute('data-title'),card.getAttribute('data-esport')].filter(Boolean).join(' ').toLowerCase();
            if (/\\b(cs2|counter\\s*strike|dota\\s*2|valorant)\\b/.test(marker)) continue;
            const time = card.querySelector('time[datetime]')?.getAttribute('datetime') || null;
            const event = card.getAttribute('data-tournament') || card.getAttribute('data-event') || card.querySelector('[data-tournament],[data-event]')?.getAttribute('data-tournament') || card.querySelector('[data-event]')?.getAttribute('data-event') || null;
            records.set(match[1], {id:match[1],team_names:names.slice(0,2),tournament:event,start_time_raw:time,hotspawn_url:anchor.href});
          }
          return [...records.values()];
        }""")
        page_url=page.url; browser.close()
    if not active: raise RuntimeError("Clicked LoL but could not verify the selected/active state; preserving previous snapshot")
    if not cards: raise RuntimeError("Selected LoL lobby has no visible match cards with numeric fixture links and team labels")
    for item in cards:
        names=item.pop("team_names",[])
        if len(names)<2: raise RuntimeError(f"Hotspawn fixture {item.get('id')} is missing two team labels")
        item["team_a"],item["team_b"]=names[:2]
        item["game"]="League of Legends"
        item["start_time_utc"]=None
        if item.pop("start_time_raw",None):
            try:
                parsed=dt.datetime.fromisoformat(item["start_time_raw"].replace("Z","+00:00"))
                if parsed.tzinfo: item["start_time_utc"]=parsed.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
            except ValueError: pass
        item["format"]=None
        item["hotspawn_lobby_url"]=page_url
        item["source_evidence"]="Visible match card after selecting Hotspawn's active LoL tab; match link and team logo alt labels"
    permalinks={}
    for offset in range(0,len(cards),40):
        ids=",".join(item["id"] for item in cards[offset:offset+40])
        api_data=get_json(HOTSPAWN_API+"?"+urllib.parse.urlencode({"ids":ids}))
        batch=api_data.get("permalinks",{}) if isinstance(api_data,dict) else {}
        if not api_data.get("success") or not isinstance(batch,dict): raise RuntimeError("Hotspawn Pick'em API did not return its documented permalink map")
        permalinks.update(batch)
    for item in cards:
        permalink=permalinks.get(item["id"])
        if not permalink or urllib.parse.urlparse(permalink).hostname!="www.hotspawn.com": raise RuntimeError(f"Hotspawn did not validate official permalink for fixture {item['id']}")
        item["hotspawn_url"]=permalink
    return cards

def api_json(path: str, params: dict[str,str], key: str) -> Any:
    url=f"{ODDS_API}/{path}?{urllib.parse.urlencode({**params,'apiKey':key})}"
    for attempt in range(3):
        try: return get_json(url)
        except urllib.error.HTTPError as error:
            if error.code==429 and attempt<2: time.sleep(4*(attempt+1)); continue
            if error.code==404: return None
            raise
    return None

def result_market_definitions(definitions: Any) -> list[dict[str,Any]]:
    if not isinstance(definitions,list): return []
    selected=[]
    for item in definitions:
        if str(item.get("sportId",""))!="18" or int(item.get("marketLength",0) or 0)!=2: continue
        name=str(item.get("marketName","")).lower()
        kind=str(item.get("marketType","")).lower()
        if any(word in name for word in ("handicap","total","over under","correct score","map ")): continue
        if not ("winner" in name or "match result" in name or "moneyline" in name or kind in {"winner","moneyline","match_winner"}): continue
        outcomes=item.get("outcomes",[])
        if not isinstance(outcomes,list) or len(outcomes)!=2: continue
        sides={}
        for outcome in outcomes:
            label=str(outcome.get("outcomeName","")).strip().lower()
            outcome_id=str(outcome.get("outcomeId",""))
            if label in {"home","1","team 1","participant 1","competitor 1"}: sides[outcome_id]="home"
            elif label in {"away","2","team 2","participant 2","competitor 2"}: sides[outcome_id]="away"
        if set(sides.values())=={"home","away"}:
            selected.append({"market_id":str(item.get("marketId","")),"sides":sides})
    return selected

def line_for_match(match: dict[str,Any], fixtures: list[dict[str,Any]], key: str, market_defs: list[dict[str,Any]]) -> dict[str,Any] | None:
    a,b=normalize(match["team_a"]),normalize(match["team_b"])
    for fixture in fixtures:
        first,second=normalize(str(fixture.get("participant1Name",""))),normalize(str(fixture.get("participant2Name","")))
        if not first or not second or {first,second}!={a,b} or not fixture.get("hasOdds"): continue
        detail=api_json("odds",{"fixtureId":str(fixture.get("fixtureId","")),"bookmakers":"pinnacle,bet365,1xbet"},key)
        books=(detail or {}).get("bookmakerOdds",{}) if isinstance(detail,dict) else {}
        available={}
        for slug,board in books.items():
            if not (board or {}).get("bookmakerIsActive",True) or (board or {}).get("suspended",False): continue
            for market_def in market_defs:
                market_id=market_def["market_id"]
                market=((board or {}).get("markets") or {}).get(market_id)
                if not market or not market.get("marketActive",True): continue
                outcomes=market.get("outcomes") or {}; prices={}
                for outcome_id,outcome in outcomes.items():
                    player=(outcome.get("players") or {}).get("0") or {}
                    if not player.get("active"): continue
                    try: price=float(player.get("price"))
                    except (ValueError,TypeError): continue
                    label=market_def["sides"].get(str(outcome_id),str(player.get("bookmakerOutcomeId","")).lower())
                    if price<=1 or price>1000: continue
                    if label in {"home","1"}: prices["home"]=price
                    elif label in {"away","2"}: prices["away"]=price
                if "home" not in prices or "away" not in prices: continue
                ih,ia=1/prices["home"],1/prices["away"]; total=ih+ia
                ph,pa=ih/total,ia/total
                if first!=a: ph,pa=pa,ph
                available[slug]=(ph,pa,(board or {}).get("fixturePath","")); break
        if not available: continue
        values=list(available.values()); avg_a=sum(v[0] for v in values)/len(values); avg_b=sum(v[1] for v in values)/len(values); total=avg_a+avg_b
        pa=round(100*avg_a/total,1); pb=round(100-pa,1)
        source=next((v[2] for v in values if v[2].startswith("https://")),ODDS_DOCS)
        bookmaker_sources=[{"name":slug,"url":v[2]} for slug,v in available.items() if v[2].startswith("https://")]
        return {"probability_a":pa,"probability_b":pb,"pick":match["team_a"] if pa>=pb else match["team_b"],"odds_source_name":"Normalized bookmaker match-winner prices","odds_source_url":source,"odds_provider_url":ODDS_DOCS,"bookmakers":list(available),"bookmaker_sources":bookmaker_sources,"odds_fetched_at":iso_now(),"odds_fixture_id":str(fixture.get("fixtureId","")),"probability_method":"Mean of per-book two-way implied probabilities after normalizing each pair to 100%; Hotspawn crowd percentages excluded."}
    return None

def write_atomic(path:Path,payload:dict[str,Any])->None:
    temporary=path.with_suffix(path.suffix+".tmp"); temporary.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); temporary.replace(path)

def main()->int:
    try: matches=fetch_hotspawn()
    except Exception as exc:
        print(f"ERROR: Hotspawn inventory validation failed: {exc}",file=sys.stderr)
        try: previous=json.loads(REVIEW_FILE.read_text(encoding="utf-8"))
        except Exception: previous={}
        flags=[f for f in previous.get("flags",[]) if f.get("title")!="Automated Hotspawn inventory refresh failed"]
        flags.insert(0,{"title":"Automated Hotspawn inventory refresh failed","detail":str(exc),"source_url":HOTSPAWN_LOBBY,"source_name":"Hotspawn lobby"})
        write_atomic(REVIEW_FILE,{"generated_at":iso_now(),"flags":flags}); return 1
    key=os.getenv("ODDSPAPI_API_KEY","").strip(); fixtures=[]; market_defs=[]; odds_error=None
    if key:
        try:
            start=NOW.date().isoformat(); end=(NOW+dt.timedelta(days=9)).date().isoformat()
            fixtures=api_json("fixtures",{"sportId":"18","from":start,"to":end},key) or []
            if not isinstance(fixtures,list): raise RuntimeError("OddsPapi fixtures response is not a list")
            market_defs=result_market_definitions(api_json("markets",{"language":"en"},key))
            if not market_defs: raise RuntimeError("No two-outcome LoL match-winner market definitions could be verified")
        except Exception as exc: odds_error=str(exc); print(f"WARNING: Odds feed unavailable: {exc}",file=sys.stderr)
    for match in matches:
        match.update({"probability_a":None,"probability_b":None,"pick":None,"odds_source_name":None,"odds_source_url":None,"odds_fetched_at":None,"bookmakers":[]})
        if key and fixtures:
            try:
                line=line_for_match(match,fixtures,key,market_defs)
                if line: match.update(line); continue
            except Exception as exc: odds_error=odds_error or str(exc)
        match["unresolved_reason"]=("No external line verified. Odds API key is not configured; Hotspawn crowd picks are not substituted." if not key else "No exact active two-team external LoL market was verified; probability withheld.")
        match["odds_search_url"]=ODDS_DOCS
    payload={"schema_version":1,"fetched_at":iso_now(),"source_url":HOTSPAWN_LOBBY,"matches":matches,"collector":{"status":"ok","message":f"Hotspawn inventory verified for {len(matches)} LoL matches. {sum(bool(m.get('pick')) for m in matches)} have a matched external line; all others are unpriced. Hotspawn crowd shares are excluded.","odds_source":"OddsPapi" if key else None,"odds_api_configured":bool(key),"odds_error":odds_error}}
    write_atomic(MATCH_FILE,payload)
    flags=[]
    if not key: flags.append({"title":"External odds API access is not configured","detail":"Hotspawn inventory refreshed, but no OddsPapi key is configured. Probabilities remain blank; no Hotspawn popularity fallback is used.","source_url":ODDS_DOCS,"source_name":"OddsPapi LoL odds/API access"})
    if odds_error: flags.append({"title":"External odds request failed","detail":odds_error,"source_url":ODDS_DOCS,"source_name":"OddsPapi documentation"})
    for match in matches:
        if not match.get("pick"): flags.append({"title":f"No verified external line: {match['team_a']} vs {match['team_b']}","detail":match["unresolved_reason"],"source_url":ODDS_DOCS,"source_name":"OddsPapi LoL odds lookup","match_url":match["hotspawn_url"]})
    write_atomic(REVIEW_FILE,{"generated_at":iso_now(),"flags":flags})
    print(f"Published {len(matches)} LoL fixtures; priced={sum(bool(m.get('pick')) for m in matches)}, unresolved={sum(not m.get('pick') for m in matches)}")
    return 0

if __name__=="__main__": raise SystemExit(main())
