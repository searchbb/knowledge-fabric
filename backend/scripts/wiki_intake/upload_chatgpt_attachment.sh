#!/usr/bin/env bash
set -euo pipefail

FILE="$1"
if [[ ! -f "$FILE" ]]; then
  echo "attachment file missing: $FILE" >&2
  exit 2
fi

# ChatGPT Desktop's file picker is fragile under automation. Copying a Finder
# file object and pasting into the composer creates the same attachment card
# without relying on the picker.
osascript -e 'tell application "ChatGPT" to activate' >/dev/null
UPLOAD_FILE="$FILE" osascript <<'OSA'
set filePath to system attribute "UPLOAD_FILE"
tell application "Finder"
  set the clipboard to (POSIX file filePath)
end tell
delay 0.35
tell application "ChatGPT" to activate
delay 0.5
tell application "System Events"
  keystroke "v" using {command down}
end tell
OSA
sleep "${CHATGPT_ATTACHMENT_SETTLE_SECONDS:-4}"
