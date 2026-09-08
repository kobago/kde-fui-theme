#!/usr/bin/env bash
# Put back the settings saved by apply.sh (~/.config/kde-fui-theme/backup.ini).
set -euo pipefail
CONF="${XDG_CONFIG_HOME:-$HOME/.config}"
BACKUP="$CONF/kde-fui-theme/backup.ini"
[ -e "$BACKUP" ] || { echo "no backup at $BACKUP" >&2; exit 1; }

WALL=""
while IFS='=' read -r key val; do
  case "$key" in
    ''|'#'*) continue ;;
    wallpaper) WALL="$val"; continue ;;
    ghostty_theme) continue ;;   # written by older versions (Ghostty moved to ghostty-fui-theme)
  esac
  IFS='/' read -r file group name <<< "$key"
  if [ -z "$val" ]; then
    kwriteconfig6 --notify --file "$file" --group "$group" --key "$name" --delete
  else
    kwriteconfig6 --notify --file "$file" --group "$group" --key "$name" "$val"
  fi
done < "$BACKUP"

dbus-send --session --type=signal /KDEPlatformTheme org.kde.KDEPlatformTheme.refreshFonts || true
dbus-send --session --type=signal /KGlobalSettings org.kde.KGlobalSettings.notifyChange int32:1 int32:0 || true
scheme="$(kreadconfig6 --file kdeglobals --group General --key ColorScheme)"
[ -n "$scheme" ] && plasma-apply-colorscheme "$scheme" || true
theme="$(kreadconfig6 --file plasmarc --group Theme --key name)"
plasma-apply-desktoptheme "${theme:-default}" || true
qdbus6 org.kde.KWin /KWin reconfigure >/dev/null 2>&1 || true
[ -n "$WALL" ] && [ -e "$WALL" ] && plasma-apply-wallpaperimage "$WALL" >/dev/null || true

mv "$BACKUP" "$BACKUP.restored"
echo "restored. (backup kept as $BACKUP.restored)"
