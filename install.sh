#!/usr/bin/env bash
# Build the FUI theme set and install it for the current user (no root needed).
# Nothing is applied here; run ./apply.sh [cyan|amber|green] afterwards.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"

echo "== build"
python3 "$ROOT/build.py"

echo "== fonts (Orbitron / Share Tech Mono / FUI Mono, OFL)"
mkdir -p "$DATA/fonts/fui"
cp "$ROOT"/fonts/*.ttf "$ROOT"/fonts/OFL-*.txt "$ROOT"/dist/fonts/* "$DATA/fonts/fui/"
fc-cache -f "$DATA/fonts/fui" >/dev/null

echo "== install"
install_tree() {  # src dst
  mkdir -p "$2"
  cp -r "$1"/. "$2"/
}
mkdir -p "$DATA/color-schemes" "$DATA/konsole"
cp "$ROOT"/dist/color-schemes/*.colors "$DATA/color-schemes/"
cp "$ROOT"/dist/konsole/*.colorscheme "$DATA/konsole/"
for d in "$ROOT"/dist/plasma/desktoptheme/*; do install_tree "$d" "$DATA/plasma/desktoptheme/$(basename "$d")"; done
for d in "$ROOT"/dist/plasma/look-and-feel/*; do install_tree "$d" "$DATA/plasma/look-and-feel/$(basename "$d")"; done
for d in "$ROOT"/dist/aurorae/themes/*; do install_tree "$d" "$DATA/aurorae/themes/$(basename "$d")"; done
for d in "$ROOT"/dist/wallpapers/*; do install_tree "$d" "$DATA/wallpapers/$(basename "$d")"; done

# Plasma caches rendered SVG elements per theme; drop them so edits show up.
rm -f "$HOME"/.cache/plasma-svgelements* "$HOME"/.cache/plasma_theme_*.kcache 2>/dev/null || true
kbuildsycoca6 --noincremental >/dev/null 2>&1 || true

echo
echo "installed:"
echo "  colour schemes : $DATA/color-schemes/FUI{Cyan,Amber,Green}.colors"
echo "  plasma themes  : $DATA/plasma/desktoptheme/fui-{cyan,amber,green}"
echo "  decorations    : $DATA/aurorae/themes/FUI-{Cyan,Amber,Green}"
echo "  wallpapers     : $DATA/wallpapers/FUI-{Cyan,Amber,Green}"
echo "  global themes  : $DATA/plasma/look-and-feel/org.kobago.fui.{cyan,amber,green}"
echo "  konsole        : $DATA/konsole/FUI{Cyan,Amber,Green}.colorscheme"
echo
echo "next: ./apply.sh cyan   (backs up current settings; ./restore.sh puts them back)"
