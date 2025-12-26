# Ally Center

A comprehensive Decky Loader plugin for the **ASUS ROG Ally** running SteamOS.

## Features

- **🖥️ Screen Off Mode** - Turn off the display for background downloads to save battery
- **⚡ Performance Profiles** - Quick switch between Silent (15W), Performance (25W), and Turbo (30W) modes
- **🔋 Battery Health** - Monitor battery health, cycle count, temperature, and set charge limits
- **💡 RGB Lighting** - Control RGB colors, brightness, and effects (static, breathing, rainbow)
- **📱 Device Info** - View system information including CPU, GPU, BIOS, and kernel version

## Requirements

- ASUS ROG Ally or ROG Ally X
- SteamOS (or compatible distro like Bazzite, ChimeraOS)
- [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader) installed

## Installation

### Quick Install (Recommended)

```bash
curl -L https://github.com/PixelAddictGames/allycenter/raw/main/install.sh | sh
```

### Manual Install

1. Download the latest release from the [Releases](https://github.com/PixelAddictUnlocked/allycenter/releases) page
2. Extract to `~/homebrew/plugins/Ally Center/`
3. Restart Decky Loader or reboot

## Development

### Prerequisites

- Node.js v16.14+
- pnpm v9

### Setup

```bash
# Clone the repository
git clone https://github.com/PixelAddictGames/allycenter.git
cd allycenter

# Install dependencies
pnpm install

# Build the plugin
pnpm run build
```

### Deploy to ROG Ally

1. Edit `.vscode/settings.json` with your ROG Ally's IP address and SSH credentials
2. Run the deploy task in VSCode: `Ctrl+Shift+P` → `Tasks: Run Task` → `deploy-restart`

Or manually:

```bash
# Build
pnpm run build

# Copy to device (replace IP with your Ally's IP)
rsync -azp --delete . deck@192.168.1.100:~/homebrew/plugins/Ally\ Center/

# Restart Decky Loader
ssh deck@192.168.1.100 'sudo systemctl restart plugin_loader'
```

### Debugging

1. On ROG Ally: Decky Settings → Developer → Enable "Allow Remote CEF Debugging"
2. On your PC: Open Chrome and navigate to `chrome://inspect/#devices`
3. Click Configure and add `<ally-ip>:8081`
4. Click "inspect" on the QuickAccess target

## Configuration

Settings are stored in `~/homebrew/settings/Ally Center/settings.json`

## Hardware Support

| Feature              | ROG Ally | ROG Ally X |
| -------------------- | -------- | ---------- |
| Screen Off           | ✅       | ✅         |
| Performance Profiles | ✅       | ✅         |
| Battery Health       | ✅       | ✅         |
| Charge Limit         | ✅       | ✅         |
| RGB Lighting         | ✅       | ✅         |
| Device Info          | ✅       | ✅         |

## License

MIT License - see [LICENSE](LICENSE) for details.

## Credits

- [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader) - Plugin framework
- [decky-frontend-lib](https://github.com/SteamDeckHomebrew/decky-frontend-lib) - UI components

## Support

- [GitHub Issues](https://github.com/PixelAddictUnlocked/allycenter/issues)
- [Discord](https://discord.gg/pixeladdictgames)
