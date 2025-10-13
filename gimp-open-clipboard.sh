#!/bin/bash

# Simple script to open image files from clipboard with GIMP
# Works by checking clipboard content for image file paths

# Get clipboard content
if [[ -n "$WAYLAND_DISPLAY" ]] && command -v wl-paste >/dev/null 2>&1; then
    CLIPBOARD_CONTENT=$(wl-paste 2>/dev/null)
else
    CLIPBOARD_CONTENT=$(xclip -selection clipboard -o 2>/dev/null)
fi

echo "Clipboard content: $CLIPBOARD_CONTENT"

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
    
    echo "File path: $FILE_PATH"
    
    # Check if it's a valid file and an image
    if [[ -f "$FILE_PATH" ]]; then
        # Check if it's an image file
        FILE_TYPE=$(file --mime-type -b "$FILE_PATH" 2>/dev/null | cut -d'/' -f1)
        if [[ "$FILE_TYPE" == "image" ]]; then
            echo "Opening image file with GIMP: $FILE_PATH"
            # Open with GIMP
            gimp "$FILE_PATH" &
            
            # Show success notification
            if command -v notify-send >/dev/null 2>&1; then
                notify-send "GIMP" "Opening $(basename "$FILE_PATH")"
            fi
            exit 0
        else
            echo "File is not an image: $FILE_TYPE"
            if command -v notify-send >/dev/null 2>&1; then
                notify-send "GIMP" "File is not an image: $(basename "$FILE_PATH")"
            fi
        fi
    else
        echo "Not a valid file path: '$FILE_PATH'"
        if command -v notify-send >/dev/null 2>&1; then
            notify-send "GIMP" "Not a valid file path"
        fi
    fi
else
    echo "No clipboard content found"
    if command -v notify-send >/dev/null 2>&1; then
        notify-send "GIMP" "No file selected. Copy an image file path to clipboard and try again."
    fi
fi
