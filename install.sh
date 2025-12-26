#!/bin/bash

# Ally Center - Installation Script
# Author: Keith Baker (Pixel Addict Games)

set -e

PLUGIN_NAME="Ally Center"
PLUGIN_DIR="$HOME/homebrew/plugins/$PLUGIN_NAME"
REPO_URL="https://github.com/PixelAddictGames/allycenter"

echo "================================"
echo "  Ally Center Installer"
echo "  by Pixel Addict Games"
echo "================================"
echo ""

# Check if running on SteamOS/Linux
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    echo "Error: This script is intended for Linux/SteamOS only."
    exit 1
fi

# Check if Decky Loader is installed
if [ ! -d "$HOME/homebrew/plugins" ]; then
    echo "Error: Decky Loader does not appear to be installed."
    echo "Please install Decky Loader first: https://decky.xyz"
    exit 1
fi

echo "Installing $PLUGIN_NAME..."

# Create plugin directory
mkdir -p "$PLUGIN_DIR"

# Download latest release
echo "Downloading latest release..."
LATEST_URL=$(curl -s https://api.github.com/repos/PixelAddictGames/allycenter/releases/latest | grep "browser_download_url.*zip" | cut -d '"' -f 4)

if [ -z "$LATEST_URL" ]; then
    echo "Could not find latest release. Cloning from repository..."
    
    # Clone and build
    TEMP_DIR=$(mktemp -d)
    git clone "$REPO_URL" "$TEMP_DIR"
    
    # Copy files
    cp -r "$TEMP_DIR"/* "$PLUGIN_DIR/"
    
    # Cleanup
    rm -rf "$TEMP_DIR"
else
    # Download and extract
    TEMP_ZIP=$(mktemp)
    curl -L "$LATEST_URL" -o "$TEMP_ZIP"
    unzip -o "$TEMP_ZIP" -d "$PLUGIN_DIR"
    rm "$TEMP_ZIP"
fi

echo ""
echo "================================"
echo "  Installation Complete!"
echo "================================"
echo ""
echo "Please restart Decky Loader or reboot your device."
echo "You can restart Decky Loader with:"
echo "  sudo systemctl restart plugin_loader"
echo ""
