#!/usr/bin/env bash
# Apply an installed FUI palette to the running Plasma session.
# Usage: ./apply.sh [cyan|amber|green]                     full FUI (default: cyan)
#        ./apply.sh [breeze-cyan|breeze-amber|breeze-green]  Breeze Dark + FUI colours only
# The previous settings are saved to ~/.config/kde-fui-theme/backup.ini (first run only,
# so switching between palettes never overwrites the pre-FUI backup). ./restore.sh reverts.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONF="${XDG_CONFIG_HOME:-$HOME/.config}"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
ARG="${1:-cyan}"
BREEZE=0
PAL="$ARG"
case "$ARG" in breeze-*) BREEZE=1; PAL="${ARG#breeze-}" ;; esac
case "$PAL" in
  cyan)  NAME=Cyan ;;
  amber) NAME=Amber ;;
  green) NAME=Green ;;
  *) echo "unknown palette: $ARG (cyan|amber|green|breeze-cyan|breeze-amber|breeze-green)" >&2; exit 1 ;;
esac
FONTS="$ROOT/dist/fonts.ini"
BACKUP_DIR="$CONF/kde-fui-theme"
BACKUP="$BACKUP_DIR/backup.ini"
if [ "$BREEZE" = 1 ]; then
  # Breeze Dark with only the colour scheme swapped: stock Plasma theme, decoration and fonts.
  TITLE="Breeze FUI $NAME"
  SCHEME="BreezeFUI$NAME"
  PLASMA="default"
  DECO_LIB="org.kde.breeze"
  DECO="Breeze"
  LNF="org.kobago.breezefui.$PAL"
  WALL=""   # keep the pre-FUI wallpaper (from the backup) instead of the grid
  NEED=("$DATA/color-schemes/$SCHEME.colors" "$FONTS")
else
  TITLE="FUI $NAME"
  SCHEME="FUI$NAME"
  PLASMA="fui-$PAL"
  DECO_LIB="org.kde.kwin.aurorae"
  DECO="__aurorae__svg__FUI-$NAME"
  LNF="org.kobago.fui.$PAL"
  WALL="$DATA/wallpapers/FUI-$NAME/contents/images/3840x2160.png"
  NEED=("$DATA/color-schemes/$SCHEME.colors" "$DATA/plasma/desktoptheme/$PLASMA/metadata.json" \
        "$DATA/aurorae/themes/FUI-$NAME/decoration.svg" "$WALL" "$FONTS")
fi

for f in "${NEED[@]}"; do
  [ -e "$f" ] || { echo "missing $f -- run ./install.sh first" >&2; exit 1; }
done

# ---- backup (once) -------------------------------------------------------
KEYS=(
  "kdeglobals General ColorScheme"
  "kdeglobals General font"
  "kdeglobals General fixed"
  "kdeglobals General smallestReadableFont"
  "kdeglobals General toolBarFont"
  "kdeglobals General menuFont"
  "kdeglobals WM activeFont"
  "kdeglobals KDE LookAndFeelPackage"
  "kdeglobals Icons Theme"
  "plasmarc Theme name"
  "kwinrc org.kde.kdecoration2 library"
  "kwinrc org.kde.kdecoration2 theme"
)
if [ ! -e "$BACKUP" ]; then
  mkdir -p "$BACKUP_DIR"
  {
    echo "# settings before the FUI theme was applied ($(date -Iseconds))"
    for k in "${KEYS[@]}"; do
      set -- $k
      printf '%s/%s/%s=%s\n' "$1" "$2" "$3" "$(kreadconfig6 --file "$1" --group "$2" --key "$3")"
    done
    # first desktop wallpaper image found in the Plasma layout
    printf 'wallpaper=%s\n' "$(grep -m1 -E '^Image=' "$CONF/plasma-org.kde.plasma.desktop-appletsrc" 2>/dev/null | cut -d= -f2- || true)"
  } > "$BACKUP"
  echo "== backup written: $BACKUP"
else
  echo "== backup already exists, keeping: $BACKUP"
fi

# ---- apply ---------------------------------------------------------------
echo "== fonts"
while IFS='=' read -r key val; do
  [ -z "$key" ] && continue
  group=General; [ "$key" = activeFont ] && group=WM
  [ "$BREEZE" = 1 ] && val=""   # Breeze FUI uses no theme fonts at all
  if [ -z "$val" ]; then
    # theme leaves this font at the system default: put back what the backup saved, else drop the key
    val="$(grep -m1 -E "^kdeglobals/$group/$key=" "$BACKUP" | cut -d= -f2- || true)"
    if [ -z "$val" ]; then
      kwriteconfig6 --notify --file kdeglobals --group "$group" --key "$key" --delete
      continue
    fi
  fi
  kwriteconfig6 --notify --file kdeglobals --group "$group" --key "$key" "$val"
done < "$FONTS"
# Tell the KDE platform theme (and KWin's title font) to re-read kdeglobals fonts.
dbus-send --session --type=signal /KDEPlatformTheme org.kde.KDEPlatformTheme.refreshFonts || true
dbus-send --session --type=signal /KGlobalSettings org.kde.KGlobalSettings.notifyChange int32:1 int32:0 || true

echo "== colour scheme: $SCHEME"
plasma-apply-colorscheme "$SCHEME"

echo "== plasma theme: $PLASMA"
plasma-apply-desktoptheme "$PLASMA"

echo "== window decoration: $DECO"
kwriteconfig6 --notify --file kwinrc --group org.kde.kdecoration2 --key library "$DECO_LIB"
kwriteconfig6 --notify --file kwinrc --group org.kde.kdecoration2 --key theme "$DECO"
kwriteconfig6 --notify --file kdeglobals --group KDE --key LookAndFeelPackage "$LNF"
qdbus6 org.kde.KWin /KWin reconfigure >/dev/null 2>&1 || true

echo "== wallpaper"
if [ -z "$WALL" ]; then
  WALL="$(grep -m1 -E '^wallpaper=' "$BACKUP" | cut -d= -f2- || true)"
  WALL="${WALL#file://}"
fi
if [ -n "$WALL" ] && [ -e "$WALL" ]; then
  plasma-apply-wallpaperimage "$WALL" >/dev/null
else
  echo "   (left unchanged)"
fi

echo
echo "applied $TITLE. Newly started apps pick up the fonts; running ones may need a restart."
echo "revert with ./restore.sh"
