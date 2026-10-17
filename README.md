# ⛏️ CraftPulse
### A Modern Material You Minecraft Launcher

A sleek, feature-rich, and offline-capable Minecraft launcher built with **Python + Flet**, inspired by Google's **Material You (Material 3)** design language.

Manage multiple Minecraft instances, automatically download Java, install mod loaders, browse Modrinth, and customize your experience — all from one modern interface.

<p align="center">

🎮 **Launch** · 📦 **Manage** · 🧩 **Mod** · 🎨 **Customize**

</p>

---

## 📥 Download & Install

**Want to get started without setting up Python?**

Head over to the **[Releases](../../releases)** page and download the prebuilt ZIP package for your operating system.

1. 📦 Download the prebuilt ZIP for your OS.
2. 🗜️ Extract the ZIP archive to a folder of your choice.
3. ▶️ Run the included executable to launch CraftPulse.

That's it! No need to install Python or manually set up the launcher dependencies when using a compatible prebuilt release.

> 💡 **Tip:** Download the package that matches your operating system. If no prebuilt release is available for your OS, use the source installation instructions below.

---

## ✨ Features

| | Feature | Description |
|---|---|---|
| 🎮 | **Instant Launch** | One-click PLAY with `F5` and force-stop with `Ctrl + F2`. |
| 📦 | **Instance Manager** | Create, duplicate, rename, and delete unlimited isolated instances. |
| ☕ | **Automatic Java** | Automatically downloads the appropriate Mojang Java runtime for each Minecraft version. |
| 🧩 | **Mod Loader Support** | Install and switch between Fabric, Quilt, and Forge without wiping your saves. |
| 🔎 | **Modrinth Browser** | Browse and install mods, resource packs, shaders, and datapacks. |
| 👤 | **Offline Profiles** | Manage multiple offline player profiles and copy UUIDs with one click. |
| 📜 | **Live Console** | Real-time, colour-coded logs with search, refresh, and export functionality. |
| 📸 | **Screenshot Gallery** | View, open, and manage Minecraft screenshots in a convenient grid. |
| 🎨 | **Material You Themes** | Choose from 8 colour seeds and switch between dark and light modes. |
| ⚙️ | **Advanced Settings** | Configure RAM, JVM arguments, Java paths, resolution, and more. |
| 💾 | **Offline-Friendly** | Keep your instances and downloaded game files locally for convenient access. |

---

## 🚀 Getting Started

### 🛠️ Requirements

- Python **3.10 or newer**
- `pip`
- An internet connection for initial game downloads, Java downloads, and Modrinth browsing

### 📚 Install Dependencies

```bash
pip install flet minecraft-launcher-lib requests
```

### ▶️ Run from Source

```bash
python main.py
```

CraftPulse will create its application data directory automatically.

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

### 🔎 Modrinth Browser
- Search for mods, resource packs, shaders, and datapacks.
- Filter results by content type.
- Match compatible content to your instance's Minecraft version.
- Install supported content directly into the selected instance.

### 🗃️ Instance Files
Manage installed mods, resource packs, and single-player worlds for each instance, with file deletion available directly from the interface.

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
- Pick from 8 Material You colour presets.
- Switch between dark and light themes.
- Allocate between 1 GB and 16 GB of RAM.
- Customize JVM arguments and Java paths.
- Select a game window resolution.
- Configure console auto-scrolling.
- Open the application folder or reset settings to defaults.

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
