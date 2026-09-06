# Bundled fonts

Both fonts are redistributed unmodified under the SIL Open Font License 1.1; the licence texts are next to them.

| File | Family | Licence | Source |
|---|---|---|---|
| `Orbitron[wght].ttf` | Orbitron (variable, weights 400-900) | `OFL-Orbitron.txt` (Reserved Font Name "Orbitron") | https://github.com/theleagueof/orbitron via google/fonts |
| `ShareTechMono-Regular.ttf` | Share Tech Mono | `OFL-ShareTechMono.txt` (Reserved Font Name "Share") | Carrois Type Design via google/fonts |

`build.py` derives **FUI Mono** from Share Tech Mono (vertical metrics matched to Noto Sans CJK JP, advance widened
to 0.60em, glyphs untouched). It is written to `dist/fonts/` (not committed), carries the OFL, and is renamed because
the OFL reserves the name "Share" for the original.
