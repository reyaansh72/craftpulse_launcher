import os
import sys
import time
import uuid
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Callable, Optional
import minecraft_launcher_lib
from lib.mc_core import (
    APP_DIR, INSTANCES_DIR, SHARED_MC_DIR, JDK_DIR, load_config, save_instance_metadata, resolve_or_download_java
)

def ensure_client_jar(version_id: str, mc_dir: str) -> bool:
    """Check that the client JAR for version_id exists. Returns True if OK."""
    jar = Path(mc_dir) / "versions" / version_id / f"{version_id}.jar"
    return jar.is_file() and jar.stat().st_size > 0


class InstanceRunner:
    def __init__(self, instance_data: dict, account_data: dict, log_callback: Callable[[str], None], status_callback: Callable[[str, float], None]):
        self.instance = instance_data
        self.account = account_data
        self.log_callback = log_callback
        self.status_callback = status_callback
        self.process: Optional[subprocess.Popen] = None
        self.is_running = False

    def install_and_launch(self):
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def _run(self):
        try:
            config = load_config()
            inst_dir = Path(self.instance["path"])
            inst_dir.mkdir(parents=True, exist_ok=True)
            version_id = self.instance.get("version", "1.20.4")
            loader_type = self.instance.get("loader", "vanilla")
            loader_ver_id = self.instance.get("loader_version_id")
            
            self.log_callback(f"[CraftPulse] =========================================")
            self.log_callback(f"[CraftPulse] Launching Instance: {self.instance.get('name')}")
            self.log_callback(f"[CraftPulse] Minecraft Version: {version_id}")
            self.log_callback(f"[CraftPulse] Loader: {loader_type.upper()} ({loader_ver_id or 'vanilla'})")
            self.log_callback(f"[CraftPulse] Player: {self.account.get('username')}")
            self.log_callback(f"[CraftPulse] Game Directory: {inst_dir}")
            self.log_callback(f"[CraftPulse] =========================================")
            
            self.status_callback("Checking Java Runtime environment...", 0.1)

            # Auto-resolve or download matching Java Runtime for Windows / Linux
            custom_java_for_inst = self.instance.get("custom_java_path", "")
            java_executable = resolve_or_download_java(
                minecraft_version=version_id,
                instance_custom_java=custom_java_for_inst,
                progress_cb=self.status_callback,
                log_cb=self.log_callback
            )
            self.log_callback(f"[CraftPulse] Java executable selected: {java_executable}")

            self.status_callback("Checking Minecraft game files...", 0.25)

            # Callback for minecraft_launcher_lib progress
            current_max = 0
            def set_status(status: str):
                self.log_callback(f"[Download Engine] {status}")
                self.status_callback(status, 0.45)

            def set_progress(progress: int):
                if current_max > 0:
                    fraction = min(1.0, max(0.0, progress / current_max))
                    self.status_callback(f"Downloading game files ({int(fraction*100)}%)...", fraction)

            def set_max(new_max: int):
                nonlocal current_max
                current_max = new_max

            callback = {
                "setStatus": set_status,
                "setProgress": set_progress,
                "setMax": set_max
            }

            shared_mc_dir = str(SHARED_MC_DIR)
            Path(shared_mc_dir).mkdir(parents=True, exist_ok=True)
            
            installed_versions = [v["id"] for v in minecraft_launcher_lib.utils.get_installed_versions(shared_mc_dir)]
            if version_id not in installed_versions:
                self.log_callback(f"[CraftPulse] Downloading base Minecraft {version_id}...")
                try:
                    minecraft_launcher_lib.install.install_minecraft_version(
                        version=version_id,
                        minecraft_directory=shared_mc_dir,
                        callback=callback
                    )
                except Exception as ex:
                    err_msg = str(ex)
                    if "wrong Checksum" in err_msg or "Checksum" in err_msg:
                        # Extract offending file path if present and remove it, then retry once
                        self.log_callback(f"[CraftPulse Warning] Detected corrupted download cache: {err_msg}. Cleaning up and retrying...")
                        import re
                        m = re.search(r'([A-Za-z]:\\[^:\n\r]+has the wrong Checksum)', err_msg)
                        if m:
                            path_str = m.group(1).replace(" has the wrong Checksum", "").strip()
                            bad_p = Path(path_str)
                            if bad_p.exists():
                                bad_p.unlink(missing_ok=True)
                        # Retry installation cleanly
                        minecraft_launcher_lib.install.install_minecraft_version(
                            version=version_id,
                            minecraft_directory=shared_mc_dir,
                            callback=callback
                        )
                    else:
                        raise ex
                self.log_callback(f"[CraftPulse] Minecraft {version_id} successfully installed.")

            # ── Verify client JAR exists (fixes "Could not find or load main class") ──
            if not ensure_client_jar(version_id, shared_mc_dir):
                self.log_callback(f"[CraftPulse] Client JAR missing for {version_id} – forcing re-download...")
                # Delete the broken version folder and reinstall fresh
                broken_dir = Path(shared_mc_dir) / "versions" / version_id
                if broken_dir.exists():
                    import shutil as _shutil
                    _shutil.rmtree(broken_dir, ignore_errors=True)
                minecraft_launcher_lib.install.install_minecraft_version(
                    version=version_id,
                    minecraft_directory=shared_mc_dir,
                    callback=callback
                )
                if not ensure_client_jar(version_id, shared_mc_dir):
                    raise RuntimeError(
                        f"Failed to obtain client JAR for {version_id}. "
                        "Check your internet connection and try again."
                    )
                self.log_callback(f"[CraftPulse] Client JAR verified OK for {version_id}.")


            target_launch_version = version_id
            if loader_type != "vanilla":
                if loader_ver_id and loader_ver_id in installed_versions:
                    target_launch_version = loader_ver_id
                else:
                    self.log_callback(f"[CraftPulse] Verifying {loader_type} installation...")
                    if loader_type == "fabric":
                        minecraft_launcher_lib.fabric.install_fabric(version_id, shared_mc_dir, callback=callback)
                        up_installed = [v["id"] for v in minecraft_launcher_lib.utils.get_installed_versions(shared_mc_dir)]
                        matches = [v for v in up_installed if "fabric" in v.lower() and version_id in v]
                        if matches:
                            target_launch_version = matches[0]
                            self.instance["loader_version_id"] = target_launch_version
                            save_instance_metadata(self.instance["id"], self.instance)
                    elif loader_type == "quilt":
                        minecraft_launcher_lib.quilt.install_quilt(version_id, shared_mc_dir, callback=callback)
                        up_installed = [v["id"] for v in minecraft_launcher_lib.utils.get_installed_versions(shared_mc_dir)]
                        matches = [v for v in up_installed if "quilt" in v.lower() and version_id in v]
                        if matches:
                            target_launch_version = matches[0]
                            self.instance["loader_version_id"] = target_launch_version
                            save_instance_metadata(self.instance["id"], self.instance)

            self.status_callback("Configuring JVM parameters...", 0.88)

            player_name = self.account.get("username", "Steve")
            player_uuid = self.account.get("uuid", str(uuid.uuid4()))
            
            # Per-instance RAM or global fallback
            inst_ram = self.instance.get("custom_jvm_ram", 0)
            max_ram = inst_ram if inst_ram > 0 else config.get("jvm_max_ram", 4096)
            min_ram = config.get("jvm_min_ram", 1024)
            custom_args = config.get("jvm_args", "").split()

            jvm_arguments = [f"-Xmx{max_ram}M", f"-Xms{min_ram}M"] + [arg for arg in custom_args if arg.strip()]

            res_str = config.get("game_resolution", "854x480")
            w, h = "854", "480"
            if "x" in res_str:
                parts = res_str.split("x")
                w, h = parts[0], parts[1]

            options = {
                "username": player_name,
                "uuid": player_uuid,
                "token": "0",  # Offline mode token
                "jvmArguments": jvm_arguments,
                "customResolution": True,
                "resolutionWidth": w,
                "resolutionHeight": h,
                "gameDirectory": str(inst_dir),
                "executablePath": java_executable
            }

            self.log_callback(f"[CraftPulse] Target Version: {target_launch_version}")
            minecraft_command = minecraft_launcher_lib.command.get_minecraft_command(
                version=target_launch_version,
                minecraft_directory=shared_mc_dir,
                options=options
            )

            # Log the full command so the user can debug classpath issues
            self.log_callback(f"[CraftPulse] Launch command: {' '.join(str(a) for a in minecraft_command[:6])} ...")
            self.log_callback(f"[CraftPulse] Classpath entries: {sum(1 for a in minecraft_command if str(a).endswith('.jar'))} JARs")

            self.status_callback("Game running", 1.0)
            self.is_running = True


            start_time = time.time()

            creationflags = 0
            if sys.platform == "win32":
                creationflags = subprocess.CREATE_NO_WINDOW

            self.process = subprocess.Popen(
                minecraft_command,
                cwd=str(inst_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags
            )

            for line in self.process.stdout:
                clean_line = line.strip()
                if clean_line:
                    self.log_callback(clean_line)

            self.process.wait()
            elapsed_seconds = int(time.time() - start_time)
            
            prev_time = self.instance.get("playtime_seconds", 0)
            self.instance["playtime_seconds"] = prev_time + elapsed_seconds
            self.instance["last_played"] = time.strftime("%Y-%m-%d %H:%M")
            save_instance_metadata(self.instance["id"], self.instance)

            self.log_callback(f"[CraftPulse] Minecraft session finished (Session time: {elapsed_seconds}s, Exit Code: {self.process.returncode})")
            self.status_callback("Idle", 0.0)
            self.is_running = False

        except Exception as e:
            self.log_callback(f"[CraftPulse ERROR] Failed to launch: {str(e)}")
            self.status_callback(f"Error: {str(e)[:30]}", 0.0)
            self.is_running = False

    def kill(self):
        if self.process and self.process.poll() is None:
            self.log_callback("[CraftPulse] Forcefully stopping Minecraft...")
            self.process.kill()
            self.is_running = False
