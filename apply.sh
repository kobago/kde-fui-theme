#!/usr/bin/env bash
# Apply an installed FUI palette to the running Plasma session.
# Usage: ./apply.sh [cyan|amber|green]      (default: cyan)
# The previous settings are saved to ~/.config/kde-fui-theme/backup.ini (first run only,
# so switching between palettes never overwrites the pre-FUI backup). ./restore.sh reverts.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONF="${XDG_CONFIG_HOME:-$HOME/.config}"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
PAL="${1:-cyan}"
case "$PAL" in
  cyan)  NAME=Cyan ;;
  amber) NAME=Amber ;;
  green) NAME=Green ;;
  *) echo "unknown palette: $PAL (cyan|amber|green)" >&2; exit 1 ;;
esac
SCHEME="FUI$NAME"
PLASMA="fui-$PAL"
DECO="__aurorae__svg__FUI-$NAME"
LNF="org.kobago.fui.$PAL"
WALL="$DATA/wallpapers/FUI-$NAME/contents/images/3840x2160.png"
FONTS="$ROOT/dist/fonts.ini"
BACKUP_DIR="$CONF/kde-fui-theme"
BACKUP="$BACKUP_DIR/backup.ini"

for f in "$DATA/color-schemes/$SCHEME.colors" "$DATA/plasma/desktoptheme/$PLASMA/metadata.json" \
         "$DATA/aurorae/themes/FUI-$NAME/decoration.svg" "$WALL" "$FONTS"; do
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
    printf 'ghostty_theme=%s\n' "$(grep -m1 -E '^\s*theme\s*=' "$CONF/ghostty/config.ghostty" 2>/dev/null | sed -E 's/^\s*theme\s*=\s*//' || true)"
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
kwriteconfig6 --notify --file kwinrc --group org.kde.kdecoration2 --key library org.kde.kwin.aurorae
kwriteconfig6 --notify --file kwinrc --group org.kde.kdecoration2 --key theme "$DECO"
kwriteconfig6 --notify --file kdeglobals --group KDE --key LookAndFeelPackage "$LNF"
qdbus6 org.kde.KWin /KWin reconfigure >/dev/null 2>&1 || true

echo "== wallpaper"
plasma-apply-wallpaperimage "$WALL" >/dev/null

echo "== ghostty theme: $PLASMA"
GH="$CONF/ghostty/config.ghostty"
if [ -e "$GH" ]; then
  if grep -qE '^\s*theme\s*=' "$GH"; then
    sed -i -E "s|^\s*theme\s*=.*|theme = $PLASMA|" "$GH"
  else
    printf '\ntheme = %s\n' "$PLASMA" >> "$GH"
  fi
fi

echo
echo "applied FUI $NAME. Newly started apps pick up the fonts; running ones may need a restart."
echo "revert with ./restore.sh"
