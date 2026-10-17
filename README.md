# ⛏️ CraftPulse

### A Modern Material You Minecraft Launcher

A sleek, feature-rich, and offline-capable Minecraft launcher built with **Python + Flet**, inspired by Google's **Material You (Material 3)** design language.

Manage multiple Minecraft instances, automatically download Java, install mod loaders, browse Modrinth, and customize your Minecraft experience — all from one modern interface.

<p align="center">

🎮 **Launch** · 📦 **Manage** · 🧩 **Mod** · 🎨 **Customize**

</p>

---

## 📥 Download & Install

**Get started without manually setting up Python!**

Visit the **[Releases](../../releases)** page and download the prebuilt ZIP package for your operating system.

| Platform | Package |
|---|---|
| 🪟 Windows | `CraftPulseLauncher-windows.zip` |
| 🐧 Linux | `CraftPulseLauncher-linux.zip` |
| 🍎 macOS | `CraftPulseLauncher-macos.zip` |

### 🚀 Installation Steps

1. 📦 Download the prebuilt ZIP for your operating system from Releases.
2. 🗜️ Extract the ZIP archive to a folder of your choice.
3. ▶️ Run the included executable or open the application bundle, depending on your OS.

That's it! A compatible prebuilt release includes the packaged application and its required bundled dependencies.

> 💡 **Note:** Download the package matching your operating system and supported CPU architecture. macOS builds may require additional security approval if they are unsigned or not notarized. Availability depends on published releases.

---

## ✨ Features

| | Feature | Description |
|---|---|---|
| 🎮 | **Instant Launch** | One-click PLAY with `F5` and force-stop with `Ctrl + F2`. |
| 📦 | **Instance Manager** | Create, duplicate, rename, delete, search, and sort isolated instances. |
| ☕ | **Automatic Java** | Downloads the appropriate Mojang Java runtime for supported Minecraft versions. |
| 🧩 | **Mod Loader Support** | Install and switch between Fabric, Quilt, and Forge. |
| 🔎 | **Modrinth Browser** | Browse and install mods, resource packs, shaders, and datapacks. |
| 👤 | **Offline Profiles** | Manage multiple offline player profiles and copy UUIDs. |
| 📜 | **Live Console** | Real-time, colour-coded logs with search, refresh, and export. |
| 📸 | **Screenshot Gallery** | Browse, open, and delete Minecraft screenshots. |
| 🎨 | **40 Material You Themes** | Choose from a collection of colour presets and switch between dark and light modes. |
| ⚙️ | **Advanced Settings** | Configure RAM, JVM arguments, Java paths, resolution, and more. |
| 💾 | **Local Data Management** | Keep instances, settings, and downloaded game files organized locally. |
| 🖥️ | **Multi-Platform Builds** | Prebuilt release packages for Windows, Linux, and macOS when available. |

---

## 🚀 Getting Started

### 🛠️ Requirements

- Python **3.10 or newer**
- `pip`
- Internet access for initial Minecraft and Java downloads and Modrinth browsing

### 📚 Install Dependencies

```bash
pip install flet minecraft-launcher-lib requests
```

### ▶️ Run from Source

```bash
python main.py
```

CraftPulse creates its application data directory automatically.

### 🍎 macOS Setup

To run CraftPulse from source on macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install flet minecraft-launcher-lib requests
python main.py
```

For prebuilt macOS packages, download the appropriate ZIP from Releases, extract it, and open the packaged application if provided.

### 📂 Application Data Locations

| Operating System | Directory |
|---|---|
| 🪟 Windows | `%APPDATA%\craftpulse\` |
| 🐧 Linux | `~/.local/share/craftpulse/` |
| 🍎 macOS | `~/Library/Application Support/craftpulse/` |

---

## 🏠 Explore CraftPulse

### 🎮 Home Dashboard

Get an overview of your Minecraft setup with instance statistics, mod counts, playtime, player profiles, quick actions, and active-instance status.

### 📦 Instance Manager

- Create, duplicate, rename, and delete instances.
- Search by instance name or Minecraft version.
- Sort by name, version, playtime, or date.
- View last-played dates and total playtime.
- Configure Java paths and RAM for individual instances.
- Keep saves and other instance files separate.

### 🔎 Modrinth Browser

- Search for mods, resource packs, shaders, and datapacks.
- Filter results by content type.
- Match supported content to your instance's Minecraft version.
- Install supported content directly into the selected instance.

### 🗃️ Instance Files

Manage your instance files directly through CraftPulse.

- Browse installed mods.
- Manage resource packs and shader packs.
- Access single-player worlds.
- Delete files through the interface.

### 👤 Account Manager

- Add, delete, and switch between offline player profiles.
- View player UUIDs and copy them to the clipboard.
- Check profile creation dates.

> ℹ️ Offline profiles do not provide Microsoft account authentication or access to authenticated online-mode servers.

### 📜 Console & Logs

- Monitor live Minecraft output.
- Identify errors, warnings, and launcher messages through colour coding.
- Toggle automatic scrolling.
- Refresh or clear logs.
- Export console output to `.txt` files.

### 📸 Screenshot Gallery

- Browse `.png` and `.jpg` screenshots.
- Open images or their containing folders.
- Delete screenshots directly.
- Sort images with the newest first.

### 🎨 Personalization & Settings

- Choose from **40 Material You colour presets**.
- Switch between dark and light themes.
- Allocate between 1 GB and 16 GB of RAM.
- Customize JVM arguments and Java paths.
- Select a game window resolution.
- Configure console auto-scrolling.
- Open the application folder or reset settings to defaults.

---

## 🎨 Theme Collection

CraftPulse includes a collection of Material You-inspired colour presets.

### 💜 Original Themes

- Dynamic Purple
- Emerald Grove
- Ocean Sapphire
- Crimson Nether
- Amber Blaze
- Obsidian Deep
- Amethyst Glow
- Teal Prism

### 🌿 Nature & Biomes

- Forest Canopy
- Cherry Blossom
- Mossy Stone
- Arctic Frost
- Desert Dune
- Ocean Depths
- Aurora Green
- Lavender Mist

### 💎 Gems & Minerals

- Ruby Flame
- Rose Quartz
- Citrine Gold
- Sapphire Night
- Jade Crystal
- Turquoise Gem
- Onyx Black
- Opal Dream

### ⛏️ Minecraft-Inspired

- Nether Portal
- Redstone Dust
- Diamond Armor
- Slime Chunk
- Gold Ingot
- Ender Void
- Lapis Lazuli
- Copper Oxide

### 🌌 Modern & Aesthetic

- Cyberpunk Neon
- Electric Indigo
- Sunset Coral
- Midnight Blue
- Soft Peach
- Glacier Blue
- Vintage Rose
- Monochrome

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `F5` | Launch the selected instance |
| `Ctrl + F2` | Force-stop the running game |

---

## 🗂️ Project Structure

```text
craftpulse_launcher/
├── main.py                  # UI and application routing
├── lib/
│   ├── mc_core.py           # Configuration, accounts, instances, Modrinth API
│   └── launcher_runner.py   # Downloads, verification, and game launching
├── requirements.txt         # Python dependencies, if present
└── README.md
```

### 💾 Application Data Structure

```text
craftpulse/
├── config.json              # Launcher settings
├── accounts.json            # Offline player profiles
├── shared_minecraft/
│   ├── versions/            # Shared Minecraft versions
│   ├── assets/              # Shared game assets
│   └── libraries/           # Shared libraries
├── instances/
│   └── <instance-id>/
│       ├── instance.json
│       ├── mods/
│       ├── resourcepacks/
│       ├── shaderpacks/
│       ├── screenshots/
│       └── saves/
└── jdk/                     # Downloaded Java runtimes
```

---

## 🐛 Latest Fixes

| Issue | Improvement |
|---|---|
| ❌ Missing Minecraft client JAR | Verify the client JAR after installation and redownload when necessary. |
| 📜 Logs not refreshing automatically | Refresh log output and scroll to new lines when auto-scroll is enabled. |
| 🔎 Mod type filter not searching | Corrected the dropdown change handler. |
| 🎮 PLAY button remaining enabled | Disable the button and display `PLAYING` while Minecraft runs; re-enable it after exit. |
| ⚠️ Closing while Minecraft runs | Display a confirmation dialog before closing the launcher. |

---

## 📋 Changelog

### ✨ Latest Updates

- 🎨 **Added More Themes** — Expanded the Material You theme collection with additional colours and styles, bringing the total to 40 presets.
- 🍎 **Added Support For macOS** — Added macOS to the automated release build workflow alongside Windows and Linux.

---

## ⚙️ Configuration Reference

Settings are stored in `config.json`.

| Key | Default | Description |
|---|---|---|
| `theme_seed_color` | `#6750A4` | Material You primary colour |
| `theme_mode` | `dark` | Theme mode: `dark` or `light` |
| `jvm_max_ram` | `4096` | Maximum heap size in MB |
| `jvm_min_ram` | `1024` | Initial heap size in MB |
| `jvm_args` | G1GC flags | Additional JVM arguments |
| `global_java_path` | `""` | Custom Java executable; empty uses automatic Java selection |
| `game_resolution` | `854x480` | Default game window resolution |
| `auto_refresh_logs` | `true` | Automatically scroll console output |
| `active_instance` | `null` | Last selected instance ID |
| `active_account` | `"Steve"` | Last selected player name |

---

## 🧰 Built With

| Technology | Purpose |
|---|---|
| 🐍 [Python](https://www.python.org/) | Core application logic |
| 🎨 [Flet](https://flet.dev/) | Modern UI and Material 3 styling |
| ⛏️ [minecraft-launcher-lib](https://minecraft-launcher-lib.readthedocs.io/) | Minecraft installation and launch support |
| 🌐 [Modrinth API](https://docs.modrinth.com/) | Mod and content discovery |

---

## 📜 License

Released under the **MIT License**. See the repository's license file for details.

---

<p align="center">

**Built with ❤️ and Python.**

*Craft your Minecraft experience. Your launcher, your rules.* ⛏️

</p>
