#!/bin/bash
# Ally Center - Installation Script
# Author: Keith Baker (Pixel Addict Games)
set -e

PLUGIN_NAME="Ally Center"
PLUGIN_DIR="$HOME/homebrew/plugins/$PLUGIN_NAME"
REPO_OWNER="PixelAddictUnlocked"
REPO_NAME="allycenter"

# Trap to ensure cleanup on exit
TEMP_FILES=()
cleanup() {
    if [ ${#TEMP_FILES[@]} -gt 0 ]; then
        echo "Cleaning up temporary files..."
        for file in "${TEMP_FILES[@]}"; do
            rm -rf "$file" 2>/dev/null || true
        done
    fi
}
trap cleanup EXIT

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

# Check if plugin is already installed
if [ -d "$PLUGIN_DIR" ]; then
    echo ""
    echo "Existing installation detected at: $PLUGIN_DIR"
    echo "This will remove the old installation and reinstall the plugin."
    read -p "Continue? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Installation cancelled."
        exit 0
    fi
    echo "Removing old installation..."
    sudo rm -rf "$PLUGIN_DIR"
fi

# Create plugin directory with sudo
echo ""
echo "Creating plugin directory (requires sudo permission)..."
sudo mkdir -p "$PLUGIN_DIR"
sudo chown -R $USER:$USER "$PLUGIN_DIR"

# Try to get latest release
echo "Checking for latest release..."
RELEASE_INFO=$(curl -s "https://api.github.com/repos/$REPO_OWNER/$REPO_NAME/releases/latest")
LATEST_URL=$(echo "$RELEASE_INFO" | grep -o '"browser_download_url": *"[^"]*\.zip"' | head -1 | cut -d '"' -f 4)

if [ -z "$LATEST_URL" ]; then
    echo ""
    echo "Error: No prebuilt release found."
    echo ""
    echo "Please download a release from:"
    echo "  https://github.com/$REPO_OWNER/$REPO_NAME/releases"
    echo ""
    echo "Or wait for the developer to publish a prebuilt release."
    exit 1
fi

# Download release zip
echo "Found prebuilt release, downloading..."
TEMP_ZIP=$(mktemp --suffix=.zip)
TEMP_FILES+=("$TEMP_ZIP")

if ! curl -L -f "$LATEST_URL" -o "$TEMP_ZIP" 2>/dev/null; then
    echo ""
    echo "Error: Failed to download release."
    echo "Please check your internet connection and try again."
    exit 1
fi

echo "Extracting release..."
if ! unzip -q -o "$TEMP_ZIP" -d "$PLUGIN_DIR"; then
    echo ""
    echo "Error: Failed to extract release."
    exit 1
fi

echo "✓ Prebuilt release installed successfully!"

# Set proper permissions
chmod -R 755 "$PLUGIN_DIR"

echo ""
echo "================================"
echo "  Installation Complete!"
echo "================================"
echo ""
echo "Plugin installed to: $PLUGIN_DIR"
echo ""
echo "Restarting Decky Loader..."

# Restart Decky Loader service
if sudo systemctl restart plugin_loader 2>/dev/null; then
    echo "✓ Decky Loader restarted successfully!"
    echo ""
    echo "Your plugin should now be available in the Quick Access menu."
else
    echo "⚠ Could not restart Decky Loader automatically."
    echo "Please restart it manually with:"
    echo "  sudo systemctl restart plugin_loader"
    echo "Or reboot your device."
fi

echo ""
