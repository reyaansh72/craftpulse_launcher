# ⛏️ CraftPulse — Material You Minecraft Launcher

A sleek, feature-rich, offline-capable Minecraft launcher built with **Python + Flet** using **Material You (M3)** design. Supports multiple isolated instances, auto Java download, Fabric/Quilt/Forge, Modrinth mod browser, and much more.

---

## ✨ Features

| Category | Feature |
|---|---|
| 🎮 **Launching** | One-click PLAY with F5 shortcut, force-stop with Ctrl+F2 |
| 📦 **Instances** | Isolated per-instance game dirs, unlimited instances, search & sort |
| ☕ **Java** | Auto-downloads the correct Mojang JDK for every version — no manual setup |
| 🧩 **Mod Loaders** | Fabric, Quilt, Forge — install/swap per-instance without wiping saves |
| 🔍 **Modrinth** | Full mod/resource pack/shader/datapack browser with 1-click install |
| 👤 **Accounts** | Multiple offline player profiles, UUID copy, per-profile switching |
| 📜 **Logs** | Real-time auto-scrolling console with colour coding, export, and search |
| 📸 **Screenshots** | Browse, open, and delete Minecraft screenshots in a grid gallery |
| 🎨 **Theming** | 8 Material You colour seeds + dark/light mode toggle |
| ⚙️ **Settings** | Global JVM args, RAM allocation, resolution, auto-scroll toggle |

---

## 🚀 Quick Start

### Prerequisites
```
Python 3.10+
pip install flet minecraft-launcher-lib requests
```

### Run
```bash
python main.py
```

The launcher stores all data (instances, JDK, game files) in:
- **Windows:** `%APPDATA%\craftpulse\`
- **Linux:** `~/.local/share/craftpulse/`
- **macOS:** `~/Library/Application Support/craftpulse/`

---

## 🗂️ Directory Layout

```
craftpulse_launcher/
├── main.py                  # UI & routing (Flet)
├── lib/
│   ├── mc_core.py           # Config, accounts, instances, Modrinth API
│   └── launcher_runner.py   # Download, verify, and launch Minecraft
└── README.md
```

### AppData layout (auto-created)
```
craftpulse/
├── config.json              # Launcher settings
├── accounts.json            # Offline player profiles
├── shared_minecraft/        # Shared game JARs & assets (all instances share these)
│   ├── versions/
│   ├── assets/
│   └── libraries/
├── instances/
│   └── <instance-id>/
│       ├── instance.json    # Instance metadata
│       ├── mods/
│       ├── resourcepacks/
│       ├── shaderpacks/
│       ├── screenshots/
│       └── saves/
└── jdk/                     # Auto-downloaded Mojang JDK runtimes
```

---

## ⌨️ Keyboard Shortcuts

| Key | Action |
|---|---|
| `F5` | Launch selected instance |
| `Ctrl + F2` | Force-stop running game |

---

## 📖 Pages

### 🏠 Home Dashboard
Stats overview (instances, mods, playtime, profiles), quick-action buttons, active instance status card.

### 📦 Instances
- Create, duplicate, delete, and rename instances
- Search by name/version, sort by name, version, playtime, or date
- Shows last played date and total playtime per card
- Per-instance Java path and RAM override

### 🔍 Modrinth Browser
- Search mods, resource packs, shaders, and datapacks
- Filters by type and automatically matches your instance's game version
- 1-click install directly into the selected instance

### 🗃️ Instance Files
- Installed mods, resource packs, and singleplayer worlds per instance
- Delete files directly from the UI

### 👤 Accounts
- Add/delete/switch offline player profiles
- UUID display with 1-click clipboard copy
- Shows profile creation date

### 📜 Console Logs
- Real-time colour-coded output: errors (red), warnings (amber), CraftPulse messages (primary)
- Auto-scroll toggle, manual refresh, clear, and export to `.txt`

### ⚙️ Settings
- Material You colour seed picker (8 presets)
- Dark / light mode toggle
- RAM slider (1 GB – 16 GB), custom JVM args, global Java path
- Game window resolution preset
- Auto-scroll console logs toggle
- Open app folder, reset to defaults

### 📸 Screenshots
- Grid gallery of all `.png` / `.jpg` in the instance's screenshots folder
- Open image, open folder, delete — sorted newest first

---

## 🐛 Bug Fixes (latest update)

| Bug | Fix |
|---|---|
| `Could not find or load main class net.minecraft.client.main.Main` | Client JAR is now verified after every install; broken folders are auto-wiped and re-downloaded |
| Logs not auto-refreshing | `scroll_to()` is called after every new log line; `auto_scroll=True` on ListView |
| Mod type filter not triggering search | Fixed `on_select` → `on_change` on Dropdown |
| PLAY button stays enabled after launch | Button now disables and shows "PLAYING" while game is running, re-enables on exit |
| No confirmation on close while game runs | Window close now shows a confirmation dialog if Minecraft is active |

---

## 🔧 Configuration (`config.json`)

| Key | Default | Description |
|---|---|---|
| `theme_seed_color` | `#6750A4` | Material You primary seed hex |
| `theme_mode` | `dark` | `"dark"` or `"light"` |
| `jvm_max_ram` | `4096` | Max heap in MB |
| `jvm_min_ram` | `1024` | Initial heap in MB |
| `jvm_args` | G1GC flags | Extra JVM arguments |
| `global_java_path` | `""` | Custom Java executable (empty = auto) |
| `game_resolution` | `854x480` | Default window size |
| `auto_refresh_logs` | `true` | Auto-scroll console logs |
| `active_instance` | `null` | Last selected instance ID |
| `active_account` | `"Steve"` | Last selected username |

---

## 📝 License

MIT — do whatever you want with it.

---

*Made with ❤️ using [Flet](https://flet.dev) + [minecraft-launcher-lib](https://minecraft-launcher-lib.readthedocs.io)*
