#!/bin/bash

# Simplified script to open image files with GIMP
# This script reads the current clipboard and opens image files with GIMP

# Log file for debugging (optional)
LOG_FILE="/tmp/gimp-middle-click.log"

# Function to log messages
log_message() {
    echo "$(date): $1" >> "$LOG_FILE"
}

log_message "GIMP launcher script triggered"

# Store current clipboard content
if [[ -n "$WAYLAND_DISPLAY" ]] && command -v wl-paste >/dev/null 2>&1; then
    CURRENT_CLIPBOARD=$(wl-paste 2>/dev/null)
else
    CURRENT_CLIPBOARD=$(xclip -selection clipboard -o 2>/dev/null)
fi

# Send Ctrl+C to copy the selected file/item
log_message "Sending Ctrl+C to copy selection"
if [[ -n "$WAYLAND_DISPLAY" ]] && command -v wtype >/dev/null 2>&1; then
    # Wayland keyboard input
    wtype -M ctrl -k c
else
    # X11 fallback
    xdotool key ctrl+c
fi

# Wait for clipboard to be populated
sleep 0.3

# Get the clipboard content after Ctrl+C
if [[ -n "$WAYLAND_DISPLAY" ]] && command -v wl-paste >/dev/null 2>&1; then
    NEW_CLIPBOARD=$(wl-paste 2>/dev/null)
else
    NEW_CLIPBOARD=$(xclip -selection clipboard -o 2>/dev/null)
fi

log_message "Clipboard content after Ctrl+C: '$NEW_CLIPBOARD'"

# If clipboard didn't change, try the current clipboard content
if [[ "$NEW_CLIPBOARD" == "$CURRENT_CLIPBOARD" ]] && [[ -n "$CURRENT_CLIPBOARD" ]]; then
    log_message "Using existing clipboard content: '$CURRENT_CLIPBOARD'"
    CLIPBOARD_CONTENT="$CURRENT_CLIPBOARD"
else
    CLIPBOARD_CONTENT="$NEW_CLIPBOARD"
fi

# Check if clipboard contains a file path
if [[ -n "$CLIPBOARD_CONTENT" ]]; then
    # Handle different clipboard formats
    if [[ "$CLIPBOARD_CONTENT" =~ ^file:// ]]; then
        # Remove file:// prefix and decode URL encoding
        FILE_PATH=$(echo "$CLIPBOARD_CONTENT" | sed 's|^file://||' | python3 -c "import sys, urllib.parse; print(urllib.parse.unquote(sys.stdin.read().strip()))" 2>/dev/null)
    else
        # Assume it's already a plain file path
        FILE_PATH="$CLIPBOARD_CONTENT"
    fi
    
    # Remove any trailing newlines or whitespace
    FILE_PATH=$(echo "$FILE_PATH" | tr -d '\n' | xargs)
    
    log_message "Processed file path: '$FILE_PATH'"
    
    # Check if it's a valid file and an image
    if [[ -f "$FILE_PATH" ]]; then
        # Check if it's an image file
        FILE_TYPE=$(file --mime-type -b "$FILE_PATH" 2>/dev/null | cut -d'/' -f1)
        if [[ "$FILE_TYPE" == "image" ]]; then
            log_message "Opening image file with GIMP: $FILE_PATH"
            # Open with GIMP
            gimp "$FILE_PATH" &
            
            # Show success notification
            if command -v notify-send >/dev/null 2>&1; then
                notify-send "GIMP" "Opening $(basename "$FILE_PATH")"
            fi
            exit 0
        else
            log_message "File is not an image: $FILE_TYPE"
            if command -v notify-send >/dev/null 2>&1; then
                notify-send "GIMP" "File is not an image: $(basename "$FILE_PATH")"
            fi
        fi
    else
        log_message "Not a valid file path: '$FILE_PATH'"
        if command -v notify-send >/dev/null 2>&1; then
            notify-send "GIMP" "Not a valid file path"
        fi
    fi
else
    log_message "No clipboard content found"
    if command -v notify-send >/dev/null 2>&1; then
        notify-send "GIMP" "No file selected. Select an image file and try again."
    fi
fi
