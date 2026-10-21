# Evidence

What is kept here and why.

| File | Meaning |
| --- | --- |
| `source_health_hotspawn.json` | every request the HotSpawn collector made, with status, byte count and SHA-256 |
| `source_health_odds.json` | the same for the external betting line sources |
| `source_health_reference.json` | the same for the Leaguepedia requests |
| `link_check.json` | result of the link and per-row source check that runs before every publish |
| `raw*/_manifest.json` | discovery manifests: for every candidate source, the URL, HTTP status, size and hash |

The `raw*/` folders hold the raw payloads captured while researching which sources answer and what their schema is.
They are research artefacts, not part of the published site: the collectors re-read the live sources on every run, so
the current values always come from `data/`.

Not kept: anything from HotSpawn's crowd "X% picked" figures - they are never collected, because the project brief
forbids using HotSpawn as a probability signal.
