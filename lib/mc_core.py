import os
import sys
import json
import uuid
import shutil
import platform
import subprocess
import threading
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
import requests
import minecraft_launcher_lib

APP_NAME = "craftpulse"

# Determine OS-specific application directory:
# Windows: %APPDATA%/craftpulse (e.g. C:\Users\<user>\AppData\Roaming\craftpulse)
# Linux / macOS: ~/.local/share/craftpulse or ~/.craftpulse
if sys.platform == "win32":
    appdata_env = os.environ.get("APPDATA")
    if appdata_env:
        APP_DIR = Path(appdata_env) / APP_NAME
    else:
        APP_DIR = Path.home() / "AppData" / "Roaming" / APP_NAME
elif sys.platform == "darwin":
    APP_DIR = Path.home() / "Library" / "Application Support" / APP_NAME
else:
    # Linux / Unix
    xdg_data = os.environ.get("XDG_DATA_HOME")
    if xdg_data:
        APP_DIR = Path(xdg_data) / APP_NAME
    else:
        APP_DIR = Path.home() / ".local" / "share" / APP_NAME

INSTANCES_DIR = APP_DIR / "instances"
SHARED_MC_DIR = APP_DIR / "shared_minecraft"
JDK_DIR = APP_DIR / "jdk"
CONFIG_FILE = APP_DIR / "config.json"
ACCOUNTS_FILE = APP_DIR / "accounts.json"

DEFAULT_CONFIG = {
    "theme_seed_color": "#6750A4",  # Dynamic Material You Purple
    "theme_mode": "dark",
    "jvm_max_ram": 4096,
    "jvm_min_ram": 1024,
    "jvm_args": "-XX:+UseG1GC -Dsun.rmi.dgc.server.gcInterval=2147483646 -XX:+UnlockExperimentalVMOptions -XX:G1NewSizePercent=20 -XX:G1ReservePercent=20 -XX:MaxGCPauseMillis=50 -XX:G1HeapRegionSize=32M",
    "global_java_path": "",  # Empty = auto-detect & auto-download JDK
    "active_instance": None,
    "active_account": "Steve",
    "game_resolution": "854x480",
    "auto_refresh_logs": True,
}

def ensure_dirs():
    APP_DIR.mkdir(parents=True, exist_ok=True)
    INSTANCES_DIR.mkdir(parents=True, exist_ok=True)
    SHARED_MC_DIR.mkdir(parents=True, exist_ok=True)
    JDK_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
    if not ACCOUNTS_FILE.exists():
        default_accs = [
            {"id": "steve_default", "username": "Steve", "uuid": str(uuid.uuid4()), "type": "offline", "skin": "default", "created_at": "2026-01-01"},
            {"id": "alex_default", "username": "Alex", "uuid": str(uuid.uuid4()), "type": "offline", "skin": "slim", "created_at": "2026-01-01"}
        ]
        with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
            json.dump(default_accs, f, indent=4)

def load_config() -> dict:
    ensure_dirs()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            merged = DEFAULT_CONFIG.copy()
            merged.update(cfg)
            return merged
    except Exception:
        return DEFAULT_CONFIG.copy()

def save_config(cfg: dict):
    APP_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4)

def load_accounts() -> List[dict]:
    ensure_dirs()
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            accs = json.load(f)
            if not accs:
                raise ValueError("Empty")
            return accs
    except Exception:
        fallback = [{"id": "steve_default", "username": "Steve", "uuid": str(uuid.uuid4()), "type": "offline", "skin": "default", "created_at": "2026-01-01"}]
        save_accounts(fallback)
        return fallback

def save_accounts(accs: List[dict]):
    APP_DIR.mkdir(parents=True, exist_ok=True)
    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        json.dump(accs, f, indent=4)

def get_instances() -> List[dict]:
    ensure_dirs()
    instances = []
    for d in INSTANCES_DIR.iterdir():
        if d.is_dir():
            meta_file = d / "instance.json"
            if meta_file.exists():
                try:
                    with open(meta_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        data["id"] = d.name
                        data["path"] = str(d)
                        # Ensure fields
                        data.setdefault("custom_java_path", "")
                        data.setdefault("custom_jvm_ram", 0)
                        data.setdefault("loader_version_id", None)
                        instances.append(data)
                except Exception:
                    pass
            else:
                meta = {
                    "id": d.name,
                    "name": d.name,
                    "version": "1.20.4",
                    "loader": "vanilla",
                    "loader_version_id": None,
                    "custom_java_path": "",
                    "custom_jvm_ram": 0,
                    "path": str(d),
                    "created_at": "Unknown",
                    "playtime_seconds": 0,
                    "icon": "cube"
                }
                save_instance_metadata(d.name, meta)
                instances.append(meta)
    return instances

def save_instance_metadata(instance_id: str, data: dict):
    inst_path = INSTANCES_DIR / instance_id
    inst_path.mkdir(parents=True, exist_ok=True)
    with open(inst_path / "instance.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def fetch_mojang_versions():
    url = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.json().get("versions", [])
    except Exception as e:
        print(f"Error fetching mojang versions: {e}")
    return []

# Auto-download and resolve Java Runtime for Minecraft version
def resolve_or_download_java(minecraft_version: str, instance_custom_java: str, progress_cb: Callable[[str, float], None], log_cb: Callable[[str], None]) -> str:
    # 1. If user set an explicit java path for this specific instance and it exists, use it!
    if instance_custom_java and instance_custom_java.strip():
        custom_path = instance_custom_java.strip()
        if Path(custom_path).exists() or custom_path.lower() == "java":
            log_cb(f"[Java Resolver] Using custom Java configured for instance: {custom_path}")
            return custom_path

    # 2. Check global configuration
    cfg = load_config()
    global_java = cfg.get("global_java_path", "").strip()
    if global_java and Path(global_java).exists():
        log_cb(f"[Java Resolver] Using global custom Java: {global_java}")
        return global_java

    # 3. Automatic Java Selection & Mojang Official Runtime Download for OS (Windows / Linux)
    # Target directory: {APP_DIR}/jdk
    jdk_base_dir = str(JDK_DIR)
    
    try:
        log_cb(f"[Java Resolver] Determining required JVM runtime for Minecraft {minecraft_version}...")
        runtime_info = minecraft_launcher_lib.runtime.get_version_runtime_information(minecraft_version, str(SHARED_MC_DIR))
        jvm_name = runtime_info.get("name", "java-runtime-gamma") if runtime_info else "java-runtime-gamma"
        major_ver = runtime_info.get("javaMajorVersion", 17) if runtime_info else 17
        log_cb(f"[Java Resolver] Target Java Runtime: '{jvm_name}' (Java {major_ver}) for OS: {platform.system()} ({platform.architecture()[0]})")

        # Check if already installed in {APP_DIR}/jdk
        existing_exec = minecraft_launcher_lib.runtime.get_executable_path(jvm_name, jdk_base_dir)
        if existing_exec and Path(existing_exec).exists():
            log_cb(f"[Java Resolver] Found cached Mojang Java runtime: {existing_exec}")
            return existing_exec

        # Download JDK to {APP_DIR}/jdk
        log_cb(f"[Java Resolver] Downloading official {jvm_name} (Java {major_ver}) to {jdk_base_dir}...")
        progress_cb(f"Downloading Java {major_ver} for {platform.system()}...", 0.25)

        current_max = 0
        def jvm_status(s):
            log_cb(f"[Java Engine] {s}")
            progress_cb(f"Java: {s}", 0.5)

        def jvm_progress(p):
            if current_max > 0:
                frac = min(1.0, max(0.0, p / current_max))
                progress_cb(f"Downloading Java Runtime ({int(frac*100)}%)...", frac)

        def jvm_max(m):
            nonlocal current_max
            current_max = m

        cb = {"setStatus": jvm_status, "setProgress": jvm_progress, "setMax": jvm_max}

        minecraft_launcher_lib.runtime.install_jvm_runtime(jvm_name, jdk_base_dir, callback=cb)
        downloaded_exec = minecraft_launcher_lib.runtime.get_executable_path(jvm_name, jdk_base_dir)
        if downloaded_exec and Path(downloaded_exec).exists():
            log_cb(f"[Java Resolver] Successfully installed Java Runtime: {downloaded_exec}")
            return downloaded_exec
    except Exception as e:
        log_cb(f"[Java Resolver Warning] Auto-download of JVM runtime failed: {e}. Falling back to system 'java'.")

    # Fallback to system java command
    return "java"

def search_modrinth(query: str, version: Optional[str] = None, project_type: str = "mod", limit: int = 25):
    url = "https://api.modrinth.com/v2/search"
    facets = []
    if project_type:
        facets.append([f"project_type:{project_type}"])
    if version:
        facets.append([f"versions:{version}"])
    
    params = {
        "query": query,
        "limit": limit,
        "index": "relevance"
    }
    if facets:
        params["facets"] = json.dumps(facets)
        
    headers = {"User-Agent": "CraftPulseLauncher/2.0 (craftpulse@antigravity.local)"}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.json().get("hits", [])
    except Exception as e:
        print(f"Modrinth search error: {e}")
    return []

def get_modrinth_project_versions(project_id: str, game_version: Optional[str] = None):
    url = f"https://api.modrinth.com/v2/project/{project_id}/version"
    params = {}
    if game_version:
        params["game_versions"] = json.dumps([game_version])
    headers = {"User-Agent": "CraftPulseLauncher/2.0 (craftpulse@antigravity.local)"}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"Modrinth versions error: {e}")
    return []

def download_mod_file(download_url: str, dest_path: Path, progress_cb: Optional[Callable[[float, str], None]] = None):
    resp = requests.get(download_url, stream=True, timeout=30)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    total = int(resp.headers.get("content-length", 0))
    downloaded = 0
    with open(dest_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=16384):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if progress_cb and total > 0:
                    pct = downloaded / total
                    progress_cb(pct, f"{round(downloaded/(1024*1024), 2)}MB / {round(total/(1024*1024), 2)}MB")

def install_modloader_to_instance(instance: dict, loader_type: str, progress_cb: Callable[[str, float], None], log_cb: Callable[[str], None]) -> bool:
    game_version = instance.get("version", "1.20.4")
    shared_dir = str(SHARED_MC_DIR)
    
    current_max = 0
    def set_status(s: str):
        log_cb(f"[{loader_type.upper()}] {s}")
        progress_cb(s, 0.5)

    def set_progress(p: int):
        if current_max > 0:
            fraction = min(1.0, max(0.0, p / current_max))
            progress_cb(f"Installing {loader_type}... ({int(fraction*100)}%)", fraction)

    def set_max(m: int):
        nonlocal current_max
        current_max = m

    cb = {
        "setStatus": set_status,
        "setProgress": set_progress,
        "setMax": set_max
    }

    try:
        if loader_type.lower() == "fabric":
            log_cb(f"[CraftPulse] Installing Fabric loader for Minecraft {game_version}...")
            progress_cb("Installing Fabric loader...", 0.2)
            minecraft_launcher_lib.fabric.install_fabric(
                minecraft_version=game_version,
                minecraft_directory=shared_dir,
                callback=cb
            )
            installed = [v["id"] for v in minecraft_launcher_lib.utils.get_installed_versions(shared_dir)]
            fabric_versions = [v for v in installed if "fabric" in v.lower() and game_version in v]
            if fabric_versions:
                instance["loader_version_id"] = fabric_versions[0]
            instance["loader"] = "fabric"
            save_instance_metadata(instance["id"], instance)
            log_cb(f"[CraftPulse] Fabric installed! Loader ID: {instance.get('loader_version_id')}")
            return True

        elif loader_type.lower() == "quilt":
            log_cb(f"[CraftPulse] Installing Quilt loader for Minecraft {game_version}...")
            progress_cb("Installing Quilt loader...", 0.2)
            minecraft_launcher_lib.quilt.install_quilt(
                minecraft_version=game_version,
                minecraft_directory=shared_dir,
                callback=cb
            )
            installed = [v["id"] for v in minecraft_launcher_lib.utils.get_installed_versions(shared_dir)]
            quilt_versions = [v for v in installed if "quilt" in v.lower() and game_version in v]
            if quilt_versions:
                instance["loader_version_id"] = quilt_versions[0]
            instance["loader"] = "quilt"
            save_instance_metadata(instance["id"], instance)
            log_cb(f"[CraftPulse] Quilt installed! Loader ID: {instance.get('loader_version_id')}")
            return True

        elif loader_type.lower() == "forge":
            log_cb(f"[CraftPulse] Installing Forge loader for Minecraft {game_version}...")
            progress_cb("Installing Forge loader...", 0.3)
            forge_ver = minecraft_launcher_lib.forge.find_forge_version(game_version)
            if not forge_ver:
                log_cb(f"[CraftPulse ERROR] No automated Forge version found for {game_version}")
                return False
            minecraft_launcher_lib.forge.install_forge_version(
                versionid=forge_ver,
                path=shared_dir,
                callback=cb
            )
            instance["loader_version_id"] = minecraft_launcher_lib.forge.forge_to_installed_version(forge_ver)
            instance["loader"] = "forge"
            save_instance_metadata(instance["id"], instance)
            log_cb(f"[CraftPulse] Forge installed!")
            return True

        elif loader_type.lower() == "vanilla":
            instance["loader"] = "vanilla"
            instance["loader_version_id"] = None
            save_instance_metadata(instance["id"], instance)
            log_cb(f"[CraftPulse] Reverted to Vanilla.")
            return True

    except Exception as e:
        log_cb(f"[CraftPulse ERROR] Loader installation failed: {e}")
        return False
    return False
