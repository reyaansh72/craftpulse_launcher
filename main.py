import os
import sys
import json
import time
import uuid
import shutil
import platform
import subprocess
import threading
from pathlib import Path
from typing import Optional
import flet as ft

# Add local directory to sys.path so lib imports work seamlessly
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from lib.mc_core import (
    load_config, save_config, load_accounts, save_accounts,
    get_instances, save_instance_metadata, fetch_mojang_versions,
    search_modrinth, get_modrinth_project_versions, download_mod_file,
    install_modloader_to_instance, APP_DIR, INSTANCES_DIR, SHARED_MC_DIR, JDK_DIR
)
from lib.launcher_runner import InstanceRunner

THEME_PRESETS = [
    {"name": "Dynamic Purple", "color": "#6750A4"},
    {"name": "Emerald Grove", "color": "#2E7D32"},
    {"name": "Ocean Sapphire", "color": "#0288D1"},
    {"name": "Crimson Nether", "color": "#C2185B"},
    {"name": "Amber Blaze", "color": "#FF8F00"},
    {"name": "Obsidian Deep", "color": "#37474F"},
    {"name": "Amethyst Glow", "color": "#7B1FA2"},
    {"name": "Teal Prism", "color": "#00897B"},
]

def main(page: ft.Page):
    config = load_config()
    page.title = "CraftPulse - Sleek Material You Minecraft Launcher"
    page.window.width = 1240
    page.window.height = 800
    page.window.min_width = 1000
    page.window.min_height = 650
    page.padding = 0
    page.theme_mode = ft.ThemeMode.DARK if config.get("theme_mode", "dark") == "dark" else ft.ThemeMode.LIGHT
    
    seed_color = config.get("theme_seed_color", "#6750A4")
    page.theme = ft.Theme(color_scheme_seed=seed_color, use_material3=True)
    page.dark_theme = ft.Theme(color_scheme_seed=seed_color, use_material3=True)

    def on_keyboard(e: ft.KeyboardEvent):
        """Global keyboard shortcuts."""
        if e.key == "F5":
            launch_current_instance()
        elif e.key == "F2" and e.ctrl:
            kill_current_instance()

    page.on_keyboard_event = on_keyboard

    def on_window_event(e):
        if e.data == "close":
            if active_runner and active_runner.is_running:
                def do_close(ev):
                    active_runner.kill()
                    page.window.destroy()
                dlg = ft.AlertDialog(
                    title=ft.Text("Game Still Running"),
                    content=ft.Text("Minecraft is still running. Force-quit and close the launcher?"),
                    actions=[
                        ft.TextButton("Stay", on_click=lambda ev: close_dialog(dlg)),
                        ft.FilledButton("Quit Anyway", bgcolor=ft.Colors.RED_700, on_click=do_close)
                    ]
                )
                page.show_dialog(dlg)
            else:
                page.window.destroy()

    page.window.prevent_close = True
    page.window.on_event = on_window_event

    instances_list = get_instances()
    accounts_list = load_accounts()
    
    current_instance = None
    if instances_list:
        saved_id = config.get("active_instance")
        current_instance = next((x for x in instances_list if x["id"] == saved_id), instances_list[0])
    
    current_account = None
    if accounts_list:
        saved_acc = config.get("active_account")
        current_account = next((a for a in accounts_list if a["username"] == saved_acc), accounts_list[0])

    active_runner: Optional[InstanceRunner] = None
    logs_buffer = []
    cached_mojang_versions = []

    def notify(msg: str, is_error=False):
        snack = ft.SnackBar(
            content=ft.Text(msg, color=ft.Colors.WHITE, size=13),
            bgcolor=ft.Colors.RED_800 if is_error else ft.Colors.GREEN_700,
            duration=3500
        )
        page.overlay.append(snack)
        snack.open = True
        page.update()

    def close_dialog(dlg=None):
        try:
            page.pop_dialog()
        except Exception:
            pass
        if dlg:
            dlg.open = False
        page.update()

    def append_log(line: str):
        logs_buffer.append(line)
        if len(logs_buffer) > 3000:
            logs_buffer.pop(0)
        
        clr = ft.Colors.ON_SURFACE_VARIANT
        if "ERROR" in line or "Exception" in line or "FATAL" in line:
            clr = ft.Colors.RED_ACCENT
        elif "WARN" in line:
            clr = ft.Colors.AMBER_ACCENT
        elif "[CraftPulse]" in line:
            clr = ft.Colors.PRIMARY
        
        txt_node = ft.Text(line, size=12, font_family="Consolas, monospace", color=clr, selectable=True)
        log_view.controls.append(txt_node)
        if len(log_view.controls) > 600:
            log_view.controls.pop(0)
        try:
            log_view.update()
            # Auto-scroll to newest line so user always sees latest output
            if config.get("auto_refresh_logs", True):
                log_view.scroll_to(offset=-1, duration=100)
        except Exception:
            try:
                page.update()
            except Exception:
                pass


    def update_runner_status(status: str, progress: float):
        launch_status_text.value = status
        launch_progress_bar.value = progress
        launch_progress_bar.visible = (progress > 0.0 and progress < 1.0)
        try:
            launch_status_text.update()
            launch_progress_bar.update()
        except Exception:
            try:
                page.update()
            except Exception:
                pass

    # --- TOP BAR & ACCOUNT SWITCHER ---
    account_dropdown_label = ft.Text(current_account["username"] if current_account else "Offline Player", weight=ft.FontWeight.BOLD, size=13)
    account_avatar_text = ft.Text(current_account["username"][:1].upper() if current_account else "P", weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY)

    def switch_account(acc):
        nonlocal current_account
        current_account = acc
        account_dropdown_label.value = acc["username"]
        account_avatar_text.value = acc["username"][:1].upper()
        config["active_account"] = acc["username"]
        save_config(config)
        notify(f"Switched player to '{acc['username']}'")
        refresh_accounts_view()
        page.update()

    def open_accounts_dialog(e=None):
        name_input = ft.TextField(label="Add Offline Username", dense=True, expand=True)
        acc_list_col = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True)

        def redraw():
            acc_list_col.controls.clear()
            for acc in accounts_list:
                is_active = (current_account and current_account["username"] == acc["username"])
                acc_list_col.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Row([
                                ft.CircleAvatar(content=ft.Text(acc["username"][:1].upper(), size=12, weight=ft.FontWeight.BOLD), radius=14, bgcolor=ft.Colors.PRIMARY_CONTAINER),
                                ft.Column([
                                    ft.Text(acc["username"], weight=ft.FontWeight.BOLD if is_active else ft.FontWeight.NORMAL),
                                    ft.Text("Offline Mode", size=10, color=ft.Colors.ON_SURFACE_VARIANT)
                                ], spacing=0)
                            ], spacing=10),
                            ft.Row([
                                ft.IconButton(
                                    ft.Icons.CHECK_CIRCLE if is_active else ft.Icons.RADIO_BUTTON_UNCHECKED,
                                    icon_color=ft.Colors.PRIMARY if is_active else ft.Colors.OUTLINE,
                                    tooltip="Select Profile",
                                    on_click=lambda ev, a=acc: [switch_account(a), close_dialog(dlg)]
                                ),
                                ft.IconButton(
                                    ft.Icons.DELETE_OUTLINE,
                                    tooltip="Delete Profile",
                                    icon_color=ft.Colors.RED_400,
                                    icon_size=18,
                                    on_click=lambda ev, a=acc: delete_profile(a)
                                ) if len(accounts_list) > 1 else ft.Container()
                            ])
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        padding=8,
                        border_radius=8,
                        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST if is_active else ft.Colors.TRANSPARENT
                    )
                )

        def add_profile(ev):
            val = name_input.value.strip()
            if not val:
                return
            if any(a["username"].lower() == val.lower() for a in accounts_list):
                notify("An account with this username already exists!", is_error=True)
                return
            new_acc = {
                "id": str(uuid.uuid4())[:8],
                "username": val,
                "uuid": str(uuid.uuid4()),
                "type": "offline",
                "skin": "default",
                "created_at": time.strftime("%Y-%m-%d")
            }
            accounts_list.append(new_acc)
            save_accounts(accounts_list)
            name_input.value = ""
            switch_account(new_acc)
            redraw()
            page.update()

        def delete_profile(acc_to_del):
            nonlocal current_account
            if acc_to_del in accounts_list:
                accounts_list.remove(acc_to_del)
                save_accounts(accounts_list)
                if current_account == acc_to_del and accounts_list:
                    switch_account(accounts_list[0])
                redraw()
                page.update()

        redraw()

        dlg = ft.AlertDialog(
            title=ft.Row([ft.Icon(ft.Icons.SWITCH_ACCOUNT), ft.Text("Switch or Add Player")]),
            content=ft.Container(
                width=420,
                height=340,
                content=ft.Column([
                    ft.Row([name_input, ft.FilledButton("Add", icon=ft.Icons.ADD, on_click=add_profile)], spacing=8),
                    ft.Divider(),
                    ft.Text("Available Profiles:", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    acc_list_col
                ])
            ),
            actions=[ft.TextButton("Close", on_click=lambda ev: close_dialog(dlg))]
        )
        page.show_dialog(dlg)

    # --- INSTANCE SELECTION & SETTINGS ---
    def select_instance(inst):
        nonlocal current_instance
        current_instance = inst
        config["active_instance"] = inst["id"]
        save_config(config)
        selected_instance_title.value = inst.get("name", "Unknown")
        java_display = "Auto JDK" if not inst.get("custom_java_path") else Path(inst.get("custom_java_path")).name
        selected_instance_subtitle.value = f"MC {inst.get('version')} • {inst.get('loader', 'vanilla').capitalize()} • Java: {java_display}"
        target_instance_badge.value = f"Target Instance: {inst.get('name')}"
        refresh_instance_mods_tab()
        refresh_instance_resourcepacks_tab()
        refresh_instance_worlds_tab()
        try:
            refresh_screenshots()
        except NameError:
            pass  # screenshots view may not be built yet at startup
        page.update()


    # --- PER-INSTANCE SETTINGS DIALOG (CUSTOM JAVA & RAM) ---
    def open_instance_settings_dialog(inst):
        if not inst:
            notify("Please create or select an instance first!", is_error=True)
            return
        name_field = ft.TextField(label="Instance Name", value=inst.get("name", ""), dense=True)
        java_field = ft.TextField(
            label="Custom Java Path (Leave blank to Auto-Download JDK)",
            value=inst.get("custom_java_path", ""),
            dense=True,
            hint_text="e.g. C:/Program Files/Java/jdk-17/bin/javaw.exe"
        )
        ram_val = inst.get("custom_jvm_ram", 0)
        ram_field = ft.TextField(
            label="Custom Allocated RAM in MB (0 = Use Global Setting)",
            value=str(ram_val),
            dense=True
        )

        def save_inst_settings(e):
            inst["name"] = name_field.value.strip() or inst["name"]
            inst["custom_java_path"] = java_field.value.strip()
            try:
                inst["custom_jvm_ram"] = int(ram_field.value.strip())
            except ValueError:
                inst["custom_jvm_ram"] = 0
            save_instance_metadata(inst["id"], inst)
            select_instance(inst)
            refresh_instances_grid()
            close_dialog(dlg)
            notify(f"Updated settings for '{inst['name']}'")

        dlg = ft.AlertDialog(
            title=ft.Row([ft.Icon(ft.Icons.TUNE), ft.Text(f"Instance Settings: {inst.get('name')}")]),
            content=ft.Container(
                width=480,
                height=280,
                content=ft.Column([
                    name_field,
                    java_field,
                    ft.Text("When left blank, CraftPulse automatically resolves & downloads the exact matching Mojang JDK for your OS into the jdk/ folder.", size=11, color=ft.Colors.PRIMARY),
                    ram_field
                ], spacing=12)
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda ev: close_dialog(dlg)),
                ft.FilledButton("Save Instance Settings", icon=ft.Icons.CHECK, on_click=save_inst_settings)
            ]
        )
        page.show_dialog(dlg)

    # --- INSTALL MODLOADER ON EXISTING INSTANCE ---
    def open_install_modloader_dialog(target_inst=None):
        inst = target_inst or current_instance
        if not inst:
            notify("Select an instance first!", is_error=True)
            return

        loader_radio = ft.RadioGroup(
            content=ft.Column([
                ft.Radio(value="fabric", label=f"Fabric Loader (Fast, modern, lightweight)"),
                ft.Radio(value="quilt", label="Quilt Loader (Fabric fork with extended compatibility)"),
                ft.Radio(value="forge", label="Forge Mod Loader (Classic extensive modding)"),
                ft.Radio(value="vanilla", label="Reset to Official Vanilla (Remove loader)"),
            ]),
            value="fabric"
        )
        loader_progress_bar = ft.ProgressBar(visible=False, height=4)
        loader_status_txt = ft.Text("", size=12, color=ft.Colors.PRIMARY)

        def do_install_loader(e):
            chosen = loader_radio.value
            loader_progress_bar.visible = True
            loader_status_txt.value = f"Injecting {chosen.capitalize()} into {inst['name']}..."
            page.update()

            def run_job():
                def prog(status, fraction):
                    loader_status_txt.value = status
                    loader_progress_bar.value = fraction
                    page.update()

                ok = install_modloader_to_instance(inst, chosen, prog, append_log)
                loader_progress_bar.visible = False
                if ok:
                    save_instance_metadata(inst["id"], inst)
                    select_instance(inst)
                    refresh_instances_grid()
                    loader_status_txt.value = f"Success! {chosen.capitalize()} is now active."
                    notify(f"Successfully configured {chosen.capitalize()} on '{inst['name']}'!")
                    time.sleep(1)
                    close_dialog(dlg)
                else:
                    loader_status_txt.value = f"Failed to install {chosen}. See logs for details."
                    notify(f"Failed to install {chosen}", is_error=True)
                page.update()

            threading.Thread(target=run_job, daemon=True).start()

        dlg = ft.AlertDialog(
            title=ft.Row([ft.Icon(ft.Icons.INTEGRATION_INSTRUCTIONS), ft.Text(f"Install Mod Loader: {inst['name']}")]),
            content=ft.Container(
                width=450,
                height=260,
                content=ft.Column([
                    ft.Text(f"Current Loader: {inst.get('loader', 'vanilla').upper()}", weight=ft.FontWeight.BOLD),
                    ft.Text("Select a mod loader to install on top of this instance without wiping worlds or configs:", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    loader_radio,
                    loader_progress_bar,
                    loader_status_txt
                ], spacing=10)
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda ev: close_dialog(dlg)),
                ft.FilledButton("Install Loader", icon=ft.Icons.INSTALL_DESKTOP, on_click=do_install_loader)
            ]
        )
        page.show_dialog(dlg)

    # --- CREATE NEW INSTANCE MODAL ---
    def open_create_instance_dialog(e=None):
        name_field = ft.TextField(label="Instance Name", value=f"Instance {len(instances_list) + 1}", dense=True)
        version_dropdown = ft.Dropdown(
            label="Minecraft Version",
            dense=True,
            options=[
                ft.dropdown.Option("1.20.4", "1.20.4 (Release)"),
                ft.dropdown.Option("1.20.2", "1.20.2 (Release)"),
                ft.dropdown.Option("1.20.1", "1.20.1 (Release)"),
                ft.dropdown.Option("1.19.4", "1.19.4 (Release)"),
                ft.dropdown.Option("1.16.5", "1.16.5 (Release)"),
                ft.dropdown.Option("1.12.2", "1.12.2 (Legacy)"),
                ft.dropdown.Option("1.8.9", "1.8.9 (Legacy PvP)")
            ]
        )
        version_dropdown.value = "1.20.4"

        version_type_filter = ft.Dropdown(
            label="Sort / Filter by Type",
            dense=True,
            value="release",
            options=[
                ft.dropdown.Option("all", "All Versions (Release, Snapshot, Beta, Alpha)"),
                ft.dropdown.Option("release", "Official Releases Only"),
                ft.dropdown.Option("snapshot", "Snapshots / Pre-releases"),
                ft.dropdown.Option("old_beta", "Beta Versions"),
                ft.dropdown.Option("old_alpha", "Alpha Versions"),
            ]
        )

        version_search_field = ft.TextField(
            label="Filter Version by Name",
            hint_text="e.g. 1.20, 24w, b1.7",
            dense=True,
        )

        loader_dropdown = ft.Dropdown(
            label="Initial Mod Loader",
            dense=True,
            value="vanilla",
            options=[
                ft.dropdown.Option("vanilla", "Vanilla Official"),
                ft.dropdown.Option("fabric", "Fabric Loader"),
                ft.dropdown.Option("quilt", "Quilt Loader"),
                ft.dropdown.Option("forge", "Forge Loader")
            ]
        )
        fetch_status = ft.Text("Loading Mojang release manifest...", size=11, color=ft.Colors.PRIMARY)

        def apply_version_filter(e=None):
            selected_type = version_type_filter.value or "release"
            search_query = (version_search_field.value or "").strip().lower()

            filtered = cached_mojang_versions
            if selected_type != "all":
                filtered = [v for v in filtered if v.get("type") == selected_type]

            if search_query:
                filtered = [v for v in filtered if search_query in v.get("id", "").lower()]

            tag_labels = {
                "release": "Release",
                "snapshot": "Snapshot",
                "old_beta": "Beta",
                "old_alpha": "Alpha"
            }

            opts = []
            for v in filtered:
                t = v.get("type", "release")
                tag = tag_labels.get(t, t.capitalize())
                opts.append(ft.dropdown.Option(v["id"], f"{v['id']} ({tag})"))

            version_dropdown.options = opts
            if opts:
                current_val = version_dropdown.value
                if not any(o.key == current_val for o in opts):
                    version_dropdown.value = opts[0].key
            else:
                version_dropdown.value = None

            total_loaded = len(cached_mojang_versions)
            fetch_status.value = f"✓ Showing {len(opts)} of {total_loaded} versions"
            page.update()

        version_type_filter.on_change = apply_version_filter
        version_search_field.on_change = apply_version_filter

        def load_manifest_versions():
            nonlocal cached_mojang_versions
            if not cached_mojang_versions:
                cached_mojang_versions = fetch_mojang_versions()
            if cached_mojang_versions:
                apply_version_filter()
            else:
                fetch_status.value = "Loaded local release database."
                page.update()

        threading.Thread(target=load_manifest_versions, daemon=True).start()

        def do_create(ev):
            inst_name = name_field.value.strip() or "My Instance"
            inst_id = "".join(c for c in inst_name if c.isalnum() or c in ("-", "_")).lower() + "_" + str(uuid.uuid4())[:6]
            new_inst_dir = INSTANCES_DIR / inst_id
            new_inst_dir.mkdir(parents=True, exist_ok=True)
            (new_inst_dir / "mods").mkdir(parents=True, exist_ok=True)
            (new_inst_dir / "resourcepacks").mkdir(parents=True, exist_ok=True)
            (new_inst_dir / "shaderpacks").mkdir(parents=True, exist_ok=True)
            (new_inst_dir / "screenshots").mkdir(parents=True, exist_ok=True)
            (new_inst_dir / "saves").mkdir(parents=True, exist_ok=True)

            meta = {
                "id": inst_id,
                "name": inst_name,
                "version": version_dropdown.value or "1.20.4",
                "loader": loader_dropdown.value,
                "loader_version_id": None,
                "custom_java_path": "",
                "custom_jvm_ram": 0,
                "created_at": time.strftime("%Y-%m-%d"),
                "playtime_seconds": 0,
                "icon": "cube"
            }
            save_instance_metadata(inst_id, meta)
            meta["path"] = str(new_inst_dir)
            instances_list.append(meta)
            select_instance(meta)
            close_dialog(dlg)
            refresh_instances_grid()
            notify(f"Created and saved instance '{inst_name}' in AppData!")

        dlg = ft.AlertDialog(
            title=ft.Row([ft.Icon(ft.Icons.ADD_BOX), ft.Text("Create Isolated Instance")]),
            content=ft.Container(
                width=500,
                height=420,
                content=ft.Column([
                    name_field,
                    ft.Row([version_type_filter, version_search_field], spacing=10),
                    version_dropdown,
                    fetch_status,
                    loader_dropdown,
                    ft.Text(f"Directory: {INSTANCES_DIR}", size=11, color=ft.Colors.ON_SURFACE_VARIANT)
                ], spacing=12)
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda ev: close_dialog(dlg)),
                ft.FilledButton("Create Instance", icon=ft.Icons.CHECK, on_click=do_create)
            ]
        )
        page.show_dialog(dlg)

    def _set_launch_button_state(running: bool):
        """Update PLAY button appearance based on whether Minecraft is running."""
        try:
            if running:
                launch_button.content = ft.Row([
                    ft.Icon(ft.Icons.SPORTS_ESPORTS, size=20),
                    ft.Text("PLAYING", size=14, weight=ft.FontWeight.BOLD)
                ], spacing=6)
                launch_button.disabled = True
                launch_status_text.value = "🟢 Game Running"
                launch_status_text.color = ft.Colors.GREEN_400
            else:
                launch_button.content = ft.Row([
                    ft.Icon(ft.Icons.PLAY_ARROW_ROUNDED, size=24),
                    ft.Text("PLAY", size=16, weight=ft.FontWeight.BOLD)
                ], spacing=6)
                launch_button.disabled = False
                launch_status_text.value = "Idle"
                launch_status_text.color = ft.Colors.PRIMARY
            launch_button.update()
            launch_status_text.update()
        except Exception:
            pass

    def launch_current_instance(e=None):
        nonlocal active_runner
        if not current_instance:
            notify("No instance selected!", is_error=True)
            return
        if not current_account:
            notify("No player profile selected!", is_error=True)
            return
        if active_runner and active_runner.is_running:
            notify("Instance is already active! Stop it before launching another.", is_error=True)
            return

        _set_launch_button_state(True)

        def _on_finish_wrapper(original_status_cb):
            def _wrapped(status: str, progress: float):
                original_status_cb(status, progress)
                if progress == 0.0 and not (active_runner and active_runner.is_running):
                    _set_launch_button_state(False)
            return _wrapped

        append_log(f"--- Launching Instance [{current_instance.get('name')}] as [{current_account.get('username')}] ---")
        active_runner = InstanceRunner(
            instance_data=current_instance,
            account_data=current_account,
            log_callback=append_log,
            status_callback=_on_finish_wrapper(update_runner_status)
        )
        active_runner.install_and_launch()
        nav_rail.selected_index = 5  # Jump to Logs tab
        switch_view(5)

    def kill_current_instance(e=None):
        if active_runner and active_runner.is_running:
            active_runner.kill()
            notify("Forcefully terminated Minecraft process.")
        else:
            notify("No active Minecraft session is currently running.")

    def open_instance_folder(e=None):
        if current_instance:
            p = current_instance["path"]
            if sys.platform == "win32":
                os.startfile(p)
            else:
                subprocess.Popen(["xdg-open", p])

    def duplicate_instance(inst):
        new_id = f"{inst['id']}_copy_{str(uuid.uuid4())[:4]}"
        src_path = Path(inst["path"])
        dst_path = INSTANCES_DIR / new_id
        try:
            shutil.copytree(src_path, dst_path)
            new_meta = inst.copy()
            new_meta["id"] = new_id
            new_meta["name"] = f"{inst['name']} (Copy)"
            new_meta["path"] = str(dst_path)
            new_meta["playtime_seconds"] = 0
            save_instance_metadata(new_id, new_meta)
            instances_list.append(new_meta)
            refresh_instances_grid()
            notify(f"Duplicated '{inst['name']}' to '{new_meta['name']}'")
        except Exception as ex:
            notify(f"Failed to duplicate: {ex}", is_error=True)

    def delete_instance_prompt(inst):
        def confirm(e):
            try:
                shutil.rmtree(inst["path"], ignore_errors=True)
                instances_list.remove(inst)
                nonlocal current_instance
                if current_instance and current_instance["id"] == inst["id"]:
                    current_instance = instances_list[0] if instances_list else None
                    if current_instance:
                        select_instance(current_instance)
                close_dialog(dlg)
                refresh_instances_grid()
                notify(f"Permanently removed instance '{inst['name']}'")
            except Exception as ex:
                notify(f"Error deleting: {ex}", is_error=True)

        dlg = ft.AlertDialog(
            title=ft.Text("Confirm Deletion"),
            content=ft.Text(f"Are you sure you want to delete '{inst['name']}' and its isolated files?"),
            actions=[
                ft.TextButton("Cancel", on_click=lambda ev: close_dialog(dlg)),
                ft.FilledButton("Delete", bgcolor=ft.Colors.RED_600, on_click=confirm)
            ]
        )
        page.show_dialog(dlg)

    # --- BOTTOM PLAY DOCK ---
    selected_instance_title = ft.Text(current_instance["name"] if current_instance else "No Instance", size=16, weight=ft.FontWeight.BOLD)
    selected_instance_subtitle = ft.Text(
        f"MC {current_instance.get('version')} • {current_instance.get('loader', 'vanilla').capitalize()} • Auto JDK" if current_instance else "Create an instance to start",
        size=11, color=ft.Colors.ON_SURFACE_VARIANT
    )
    launch_status_text = ft.Text("Idle", size=12, color=ft.Colors.PRIMARY, weight=ft.FontWeight.W_500)
    launch_progress_bar = ft.ProgressBar(value=0.0, visible=False, height=4)

    launch_button = ft.FilledButton(
        content=ft.Row([ft.Icon(ft.Icons.PLAY_ARROW_ROUNDED, size=24), ft.Text("PLAY", size=16, weight=ft.FontWeight.BOLD)], spacing=6),
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=12),
            padding=ft.Padding.symmetric(horizontal=30, vertical=16)
        ),
        on_click=launch_current_instance
    )

    kill_button = ft.IconButton(
        icon=ft.Icons.STOP_CIRCLE_OUTLINED,
        icon_color=ft.Colors.RED_ACCENT,
        tooltip="Force Stop Minecraft",
        icon_size=28,
        on_click=kill_current_instance
    )

    folder_button = ft.IconButton(
        icon=ft.Icons.FOLDER_OPEN_ROUNDED,
        tooltip="Open Instance Folder",
        icon_size=24,
        on_click=open_instance_folder
    )

    bottom_play_dock = ft.Container(
        content=ft.Column([
            launch_progress_bar,
            ft.Row([
                ft.Container(
                    content=ft.Row([
                        ft.Container(
                            content=ft.Icon(ft.Icons.VIDEOGAME_ASSET, size=28, color=ft.Colors.PRIMARY),
                            padding=10,
                            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                            border_radius=12
                        ),
                        ft.Column([
                            selected_instance_title,
                            selected_instance_subtitle,
                            launch_status_text
                        ], spacing=2)
                    ], spacing=14),
                    expand=True
                ),
                ft.Row([
                    folder_button,
                    kill_button,
                    launch_button
                ], spacing=10)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        ], spacing=4),
        padding=ft.Padding.symmetric(horizontal=24, vertical=12),
        bgcolor=ft.Colors.SURFACE_CONTAINER,
        border=ft.Border(top=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT))
    )

    # --- VIEW 1: INSTANCES MANAGEMENT ---
    instances_grid = ft.GridView(
        expand=True,
        runs_count=5,
        max_extent=290,
        child_aspect_ratio=0.80,
        spacing=16,
        run_spacing=16
    )
    instances_search_field = ft.TextField(
        hint_text="Search instances by name or version...",
        prefix_icon=ft.Icons.SEARCH,
        dense=True,
        expand=True,
        on_change=lambda e: refresh_instances_grid()
    )
    instances_sort_dropdown = ft.Dropdown(
        dense=True,
        value="name",
        width=160,
        options=[
            ft.dropdown.Option("name", "Sort: Name A-Z"),
            ft.dropdown.Option("version", "Sort: Version"),
            ft.dropdown.Option("playtime", "Sort: Most Played"),
            ft.dropdown.Option("created", "Sort: Newest"),
        ],
        on_select=lambda e: refresh_instances_grid()
    )

    def refresh_instances_grid():
        nonlocal instances_list
        instances_list = get_instances()
        query = (instances_search_field.value or "").strip().lower()
        sort_by = instances_sort_dropdown.value or "name"

        filtered = instances_list
        if query:
            filtered = [i for i in filtered if query in i.get("name", "").lower() or query in i.get("version", "").lower()]

        if sort_by == "name":
            filtered = sorted(filtered, key=lambda i: i.get("name", "").lower())
        elif sort_by == "version":
            filtered = sorted(filtered, key=lambda i: i.get("version", ""), reverse=True)
        elif sort_by == "playtime":
            filtered = sorted(filtered, key=lambda i: i.get("playtime_seconds", 0), reverse=True)
        elif sort_by == "created":
            filtered = sorted(filtered, key=lambda i: i.get("created_at", ""), reverse=True)

        instances_grid.controls.clear()

        if not filtered and instances_list:
            instances_grid.controls.append(ft.Container(
                content=ft.Column([
                    ft.Icon(ft.Icons.SEARCH_OFF, size=48, color=ft.Colors.OUTLINE),
                    ft.Text("No instances match your search.", color=ft.Colors.ON_SURFACE_VARIANT)
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=40, alignment=ft.Alignment(0, 0)
            ))
        elif not filtered:
            instances_grid.controls.append(ft.Container(
                content=ft.Column([
                    ft.Icon(ft.Icons.ADD_BOX_OUTLINED, size=48, color=ft.Colors.OUTLINE),
                    ft.Text("No instances yet. Click \"New Instance\" to get started!", color=ft.Colors.ON_SURFACE_VARIANT),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                padding=40, alignment=ft.Alignment(0, 0)
            ))

        for inst in filtered:
            is_active = (current_instance and current_instance["id"] == inst["id"])
            play_secs = inst.get("playtime_seconds", 0)
            play_hrs = round(play_secs / 3600, 1)
            loader_txt = inst.get("loader", "vanilla").upper()
            has_custom_java = bool(inst.get("custom_java_path"))
            last_played = inst.get("last_played", inst.get("created_at", "Never"))

            card = ft.Card(
                elevation=is_active and 6 or 1,
                content=ft.Container(
                    padding=16,
                    border_radius=12,
                    border=ft.Border.all(2, ft.Colors.PRIMARY if is_active else ft.Colors.TRANSPARENT),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH if is_active else ft.Colors.SURFACE_CONTAINER,
                    content=ft.Column([
                        ft.Row([
                            ft.Container(
                                content=ft.Icon(ft.Icons.EXTENSION if inst.get("loader") != "vanilla" else ft.Icons.SPORTS_ESPORTS, size=24, color=ft.Colors.PRIMARY),
                                padding=8,
                                border_radius=8,
                                bgcolor=ft.Colors.PRIMARY_CONTAINER
                            ),
                            ft.PopupMenuButton(
                                icon=ft.Icons.MORE_VERT,
                                items=[
                                    ft.PopupMenuItem(icon=ft.Icons.TUNE, content=ft.Text("Instance Settings (Java/RAM)"), on_click=lambda ev, i=inst: open_instance_settings_dialog(i)),
                                    ft.PopupMenuItem(icon=ft.Icons.INTEGRATION_INSTRUCTIONS, content=ft.Text("Install / Change Mod Loader"), on_click=lambda ev, i=inst: open_install_modloader_dialog(i)),
                                    ft.PopupMenuItem(icon=ft.Icons.COPY, content=ft.Text("Duplicate Instance"), on_click=lambda ev, i=inst: duplicate_instance(i)),
                                    ft.PopupMenuItem(icon=ft.Icons.FOLDER, content=ft.Text("Open Folder"), on_click=lambda ev, i=inst: os.startfile(i["path"])),
                                    ft.PopupMenuItem(icon=ft.Icons.DELETE, content=ft.Text("Delete Instance"), on_click=lambda ev, i=inst: delete_instance_prompt(i)),
                                ]
                            )
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Container(height=4),
                        ft.Text(inst.get("name", "Unnamed"), size=16, weight=ft.FontWeight.BOLD, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(f"Minecraft {inst.get('version')}", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Row([
                            ft.Container(
                                content=ft.Text(loader_txt, size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SECONDARY_CONTAINER),
                                bgcolor=ft.Colors.SECONDARY_CONTAINER,
                                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                border_radius=6
                            ),
                            ft.Container(
                                content=ft.Text("Custom Java" if has_custom_java else "Auto JDK", size=10, color=ft.Colors.PRIMARY),
                                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                border_radius=4,
                                border=ft.Border.all(1, ft.Colors.PRIMARY)
                            )
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Row([
                            ft.Icon(ft.Icons.CALENDAR_TODAY, size=12, color=ft.Colors.OUTLINE),
                            ft.Text(f"Played: {last_played}", size=10, color=ft.Colors.OUTLINE)
                        ], spacing=4),
                        ft.Container(expand=True),
                        ft.Row([
                            ft.Row([ft.Icon(ft.Icons.ACCESS_TIME, size=14, color=ft.Colors.OUTLINE), ft.Text(f"{play_hrs}h", size=11, color=ft.Colors.OUTLINE)], spacing=4),
                            ft.FilledTonalButton("Select", icon=ft.Icons.CHECK if is_active else ft.Icons.PLAY_ARROW, on_click=lambda ev, i=inst: [select_instance(i), refresh_instances_grid()])
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                    ], spacing=4)
                )
            )
            instances_grid.controls.append(card)
        page.update()

    refresh_instances_grid()

    instances_view = ft.Container(
        padding=24,
        expand=True,
        content=ft.Column([
            ft.Row([
                ft.Column([
                    ft.Text("My Instances", size=24, weight=ft.FontWeight.BOLD),
                    ft.Text(f"Saved to: {INSTANCES_DIR}", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
                ], spacing=2),
                ft.Row([
                    ft.FilledButton("New Instance", icon=ft.Icons.ADD, on_click=open_create_instance_dialog),
                    ft.IconButton(ft.Icons.REFRESH, tooltip="Refresh Instances", on_click=lambda ev: refresh_instances_grid())
                ], spacing=10)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Row([instances_search_field, instances_sort_dropdown], spacing=10),
            ft.Container(height=4),
            instances_grid
        ], expand=True)
    )

    # --- VIEW 2: MODRINTH BROWSER ---
    mod_search_input = ft.TextField(
        hint_text="Search mods, resource packs, shaders on Modrinth...",
        prefix_icon=ft.Icons.SEARCH,
        dense=True,
        expand=True,
        on_submit=lambda e: perform_mod_search()
    )
    mod_type_filter = ft.Dropdown(
        dense=True,
        value="mod",
        options=[
            ft.dropdown.Option("mod", "Mods"),
            ft.dropdown.Option("resourcepack", "Resource Packs"),
            ft.dropdown.Option("shader", "Shaders"),
            ft.dropdown.Option("datapack", "Datapacks")
        ],
        width=160,
        on_select=lambda e: perform_mod_search()
    )
    mod_results_list = ft.ListView(expand=True, spacing=10, padding=4)
    mod_search_progress = ft.ProgressBar(visible=False, height=3)

    mod_download_progress_bar = ft.ProgressBar(visible=False, value=0.0, height=5)
    mod_download_status_label = ft.Text("", size=12, color=ft.Colors.PRIMARY, weight=ft.FontWeight.W_500)

    target_instance_badge = ft.Text(
        f"Target Instance: {current_instance['name'] if current_instance else 'None'}",
        size=12,
        color=ft.Colors.PRIMARY,
        weight=ft.FontWeight.BOLD
    )

    def install_mod_to_current_instance(hit):
        if not current_instance:
            notify("Please select an instance first!", is_error=True)
            return

        def task():
            try:
                mod_download_progress_bar.visible = True
                mod_download_progress_bar.value = 0.05
                mod_download_status_label.value = f"Finding compatible version for '{hit['title']}'..."
                page.update()

                game_ver = current_instance.get("version")
                versions = get_modrinth_project_versions(hit["project_id"], game_version=game_ver)
                if not versions:
                    versions = get_modrinth_project_versions(hit["project_id"])
                
                if not versions:
                    mod_download_progress_bar.visible = False
                    mod_download_status_label.value = ""
                    notify(f"No compatible version found for {hit['title']} on {game_ver}", is_error=True)
                    page.update()
                    return

                selected_version = versions[0]
                primary_file = next((f for f in selected_version.get("files", []) if f.get("primary")), selected_version.get("files", [None])[0])
                if not primary_file:
                    mod_download_progress_bar.visible = False
                    notify("No downloadable binary file found.", is_error=True)
                    page.update()
                    return

                download_url = primary_file["url"]
                filename = primary_file["filename"]
                
                proj_type = hit.get("project_type", "mod")
                folder_map = {
                    "mod": "mods",
                    "resourcepack": "resourcepacks",
                    "shader": "shaderpacks",
                    "datapack": "datapacks"
                }
                dest_dir = Path(current_instance["path"]) / folder_map.get(proj_type, "mods")
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest_path = dest_dir / filename

                append_log(f"[Modrinth] Starting download: {filename}")

                def progress_cb(pct, status_info):
                    mod_download_progress_bar.value = pct
                    mod_download_status_label.value = f"Downloading {filename}: {int(pct*100)}% ({status_info})"
                    page.update()

                download_mod_file(download_url, dest_path, progress_cb=progress_cb)

                mod_download_progress_bar.value = 1.0
                mod_download_status_label.value = f"✓ Successfully installed {filename}!"
                append_log(f"[Modrinth] Installed {filename} into {dest_path}")
                notify(f"Installed {hit['title']} into '{current_instance['name']}'!")
                refresh_instance_mods_tab()
                time.sleep(2)
                mod_download_progress_bar.visible = False
                mod_download_status_label.value = ""
                page.update()
            except Exception as ex:
                append_log(f"[Modrinth ERROR] Failed to install: {ex}")
                mod_download_progress_bar.visible = False
                mod_download_status_label.value = f"Error: {ex}"
                notify(f"Install failed: {ex}", is_error=True)
                page.update()

        threading.Thread(target=task, daemon=True).start()

    def perform_mod_search():
        q = mod_search_input.value.strip()
        ptype = mod_type_filter.value
        mod_search_progress.visible = True
        page.update()

        def run_search():
            game_ver = current_instance.get("version") if current_instance else None
            hits = search_modrinth(query=q, version=game_ver, project_type=ptype, limit=30)
            mod_results_list.controls.clear()
            
            if not hits:
                mod_results_list.controls.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Icon(ft.Icons.SEARCH_OFF, size=48, color=ft.Colors.OUTLINE),
                            ft.Text("No results found on Modrinth for this filter.", color=ft.Colors.ON_SURFACE_VARIANT)
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        padding=40,
                        alignment=ft.Alignment(0, 0)
                    )
                )
            else:
                for hit in hits:
                    icon_url = hit.get("icon_url")
                    downloads_count = f"{hit.get('downloads', 0):,}"
                    follows = f"{hit.get('follows', 0):,}"

                    card = ft.Card(
                        elevation=1,
                        content=ft.Container(
                            padding=14,
                            content=ft.Row([
                                ft.Image(
                                    src=icon_url if icon_url else "https://modrinth.com/assets/favicon.ico",
                                    width=54,
                                    height=54,
                                    fit=ft.BoxFit.CONTAIN,
                                    border_radius=8,
                                    error_content=ft.Icon(ft.Icons.EXTENSION, size=40, color=ft.Colors.PRIMARY)
                                ),
                                ft.Column([
                                    ft.Row([
                                        ft.Text(hit.get("title", "Unknown"), size=15, weight=ft.FontWeight.BOLD),
                                        ft.Text(f"by {hit.get('author')}", size=11, color=ft.Colors.ON_SURFACE_VARIANT)
                                    ], spacing=8),
                                    ft.Text(hit.get("description", "No description provided"), size=12, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS, color=ft.Colors.ON_SURFACE_VARIANT),
                                    ft.Row([
                                        ft.Row([ft.Icon(ft.Icons.DOWNLOAD_ROUNDED, size=13, color=ft.Colors.PRIMARY), ft.Text(downloads_count, size=11, color=ft.Colors.PRIMARY)], spacing=3),
                                        ft.Row([ft.Icon(ft.Icons.STAR_BORDER, size=13, color=ft.Colors.AMBER), ft.Text(follows, size=11)], spacing=3),
                                        ft.Text(f"Supported: {', '.join(hit.get('latest_version_game_versions', [])[:3])}", size=11, color=ft.Colors.OUTLINE)
                                    ], spacing=14)
                                ], spacing=4, expand=True),
                                ft.FilledButton(
                                    "Install",
                                    icon=ft.Icons.DOWNLOAD,
                                    tooltip=f"Install directly into '{current_instance['name']}'" if current_instance else "Select instance first",
                                    on_click=lambda ev, h=hit: install_mod_to_current_instance(h)
                                )
                            ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=14)
                        )
                    )
                    mod_results_list.controls.append(card)

            mod_search_progress.visible = False
            page.update()

        threading.Thread(target=run_search, daemon=True).start()

    mod_browser_view = ft.Container(
        padding=24,
        expand=True,
        content=ft.Column([
            ft.Row([
                ft.Column([
                    ft.Text("Modrinth Mod Browser", size=24, weight=ft.FontWeight.BOLD),
                    target_instance_badge
                ], spacing=2),
            ]),
            ft.Container(height=6),
            ft.Row([
                mod_search_input,
                mod_type_filter,
                ft.FilledButton("Search", icon=ft.Icons.SEARCH, on_click=lambda e: perform_mod_search())
            ], spacing=10),
            mod_search_progress,
            mod_download_progress_bar,
            mod_download_status_label,
            ft.Container(height=4),
            mod_results_list
        ], expand=True)
    )

    perform_mod_search()

    # --- VIEW 3: INSTANCE FILES ---
    installed_mods_list = ft.ListView(expand=True, spacing=6)
    installed_resourcepacks_list = ft.ListView(expand=True, spacing=6)
    installed_worlds_list = ft.ListView(expand=True, spacing=6)

    def refresh_instance_resourcepacks_tab():
        installed_resourcepacks_list.controls.clear()
        if not current_instance:
            return
        rp_dir = Path(current_instance["path"]) / "resourcepacks"
        if not rp_dir.exists():
            rp_dir.mkdir(parents=True, exist_ok=True)
        files = list(rp_dir.glob("*.zip")) + list(rp_dir.glob("*.jar"))
        if not files:
            installed_resourcepacks_list.controls.append(
                ft.Container(
                    content=ft.Text("No resource packs installed yet. Download them from the Modrinth browser tab!", color=ft.Colors.ON_SURFACE_VARIANT),
                    padding=20
                )
            )
        else:
            for f in files:
                sz_mb = round(f.stat().st_size / (1024 * 1024), 2)
                row = ft.Container(
                    content=ft.Row([
                        ft.Row([
                            ft.Icon(ft.Icons.PALETTE, color=ft.Colors.TERTIARY),
                            ft.Column([
                                ft.Text(f.name, weight=ft.FontWeight.W_500),
                                ft.Text(f"{sz_mb} MB", size=11, color=ft.Colors.ON_SURFACE_VARIANT)
                            ], spacing=1)
                        ], spacing=10),
                        ft.Row([
                            ft.IconButton(
                                ft.Icons.DELETE_OUTLINE,
                                tooltip="Delete Resource Pack",
                                icon_color=ft.Colors.RED_400,
                                on_click=lambda ev, file_path=f: [os.remove(file_path), refresh_instance_resourcepacks_tab(), notify(f"Removed {file_path.name}")]
                            )
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    padding=10,
                    bgcolor=ft.Colors.SURFACE_CONTAINER,
                    border_radius=8
                )
                installed_resourcepacks_list.controls.append(row)
        page.update()

    def refresh_instance_mods_tab():
        installed_mods_list.controls.clear()
        if not current_instance:
            return
        mods_dir = Path(current_instance["path"]) / "mods"
        if not mods_dir.exists():
            mods_dir.mkdir(parents=True, exist_ok=True)
        files = list(mods_dir.glob("*.jar"))
        if not files:
            installed_mods_list.controls.append(
                ft.Container(
                    content=ft.Text("No mods installed yet. Install them directly using the Modrinth tab!", color=ft.Colors.ON_SURFACE_VARIANT),
                    padding=20
                )
            )
        else:
            for f in files:
                sz_mb = round(f.stat().st_size / (1024 * 1024), 2)
                row = ft.Container(
                    content=ft.Row([
                        ft.Row([
                            ft.Icon(ft.Icons.EXTENSION, color=ft.Colors.PRIMARY),
                            ft.Column([
                                ft.Text(f.name, weight=ft.FontWeight.W_500),
                                ft.Text(f"{sz_mb} MB", size=11, color=ft.Colors.ON_SURFACE_VARIANT)
                            ], spacing=1)
                        ], spacing=10),
                        ft.IconButton(
                            ft.Icons.DELETE_OUTLINE,
                            tooltip="Delete Mod",
                            icon_color=ft.Colors.RED_400,
                            on_click=lambda ev, file_path=f: [os.remove(file_path), refresh_instance_mods_tab(), notify(f"Removed {file_path.name}")]
                        )
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    padding=10,
                    bgcolor=ft.Colors.SURFACE_CONTAINER,
                    border_radius=8
                )
                installed_mods_list.controls.append(row)
        page.update()

    def refresh_instance_worlds_tab():
        installed_worlds_list.controls.clear()
        if not current_instance:
            return
        saves_dir = Path(current_instance["path"]) / "saves"
        if not saves_dir.exists():
            saves_dir.mkdir(parents=True, exist_ok=True)
        worlds = [d for d in saves_dir.iterdir() if d.is_dir()]
        if not worlds:
            installed_worlds_list.controls.append(
                ft.Container(
                    content=ft.Text("No singleplayer worlds in this instance yet.", color=ft.Colors.ON_SURFACE_VARIANT),
                    padding=20
                )
            )
        else:
            for w in worlds:
                installed_worlds_list.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Row([
                                ft.Icon(ft.Icons.PUBLIC, color=ft.Colors.TERTIARY),
                                ft.Text(w.name, weight=ft.FontWeight.W_500)
                            ], spacing=10),
                            ft.Row([
                                ft.IconButton(ft.Icons.FOLDER, tooltip="Open World Folder", on_click=lambda ev, wp=w: os.startfile(wp))
                            ])
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        padding=10,
                        bgcolor=ft.Colors.SURFACE_CONTAINER,
                        border_radius=8
                    )
                )
        page.update()

    content_tabs = ft.Tabs(
        length=3,
        selected_index=0,
        expand=True,
        content=ft.Column(
            expand=True,
            controls=[
                ft.TabBar(
                    tabs=[
                        ft.Tab(label="Installed Mods", icon=ft.Icons.EXTENSION),
                        ft.Tab(label="Resource Packs", icon=ft.Icons.PALETTE),
                        ft.Tab(label="Singleplayer Worlds", icon=ft.Icons.PUBLIC),
                    ]
                ),
                ft.TabBarView(
                    expand=True,
                    controls=[
                        ft.Container(padding=12, content=installed_mods_list),
                        ft.Container(padding=12, content=installed_resourcepacks_list),
                        ft.Container(padding=12, content=installed_worlds_list),
                    ]
                )
            ]
        )
    )

    instance_content_view = ft.Container(
        padding=24,
        expand=True,
        content=ft.Column([
            ft.Row([
                ft.Column([
                    ft.Text(f"Instance Files: {current_instance['name'] if current_instance else 'None'}", size=24, weight=ft.FontWeight.BOLD),
                    ft.Text("Inspect and manage mods, resource packs, and world saves per instance", size=13, color=ft.Colors.ON_SURFACE_VARIANT)
                ], spacing=2),
                ft.Row([
                    ft.FilledTonalButton("Configure Settings / Java", icon=ft.Icons.TUNE, on_click=lambda e: open_instance_settings_dialog(current_instance)),
                    ft.FilledTonalButton("Install Mod Loader", icon=ft.Icons.BUILD, on_click=lambda e: open_install_modloader_dialog(current_instance)),
                    ft.FilledButton("Open Folder", icon=ft.Icons.FOLDER_OPEN, on_click=lambda e: os.startfile(Path(current_instance['path'])))
                ], spacing=8)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Container(height=8),
            content_tabs
        ], expand=True)
    )

    # --- VIEW 4: ACCOUNTS MANAGER ---
    accounts_grid = ft.GridView(expand=True, max_extent=280, child_aspect_ratio=1.4, spacing=14, run_spacing=14)
    new_acc_username_field = ft.TextField(label="New Player Username", dense=True, width=280)

    def refresh_accounts_view():
        accounts_grid.controls.clear()
        for acc in accounts_list:
            is_active = (current_account and current_account["username"] == acc["username"])
            created = acc.get("created_at", "Unknown")
            short_uuid = acc.get("uuid", "")[:8] + "..."

            def copy_uuid(ev, u=acc.get("uuid", "")):
                page.set_clipboard(u)
                notify("UUID copied to clipboard!")

            card = ft.Card(
                elevation=is_active and 4 or 1,
                content=ft.Container(
                    padding=16,
                    border_radius=12,
                    border=ft.Border.all(2, ft.Colors.PRIMARY if is_active else ft.Colors.TRANSPARENT),
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH if is_active else ft.Colors.SURFACE_CONTAINER,
                    content=ft.Column([
                        ft.Row([
                            ft.Row([
                                ft.CircleAvatar(
                                    content=ft.Text(acc["username"][:1].upper(), size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                                    radius=18,
                                    bgcolor=ft.Colors.PRIMARY_CONTAINER
                                ),
                                ft.Column([
                                    ft.Text(acc["username"], size=16, weight=ft.FontWeight.BOLD),
                                    ft.Text("Offline Mode", size=11, color=ft.Colors.ON_SURFACE_VARIANT)
                                ], spacing=1)
                            ], spacing=10),
                            ft.IconButton(
                                ft.Icons.DELETE_OUTLINE,
                                tooltip="Delete Account",
                                icon_color=ft.Colors.RED_400,
                                on_click=lambda ev, a=acc: delete_acc_action(a)
                            ) if len(accounts_list) > 1 else ft.Container()
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Row([
                            ft.Icon(ft.Icons.CALENDAR_TODAY, size=12, color=ft.Colors.OUTLINE),
                            ft.Text(f"Created: {created}", size=10, color=ft.Colors.OUTLINE)
                        ], spacing=4),
                        ft.Row([
                            ft.Text(f"UUID: {short_uuid}", size=10, color=ft.Colors.OUTLINE, selectable=True),
                            ft.IconButton(ft.Icons.COPY, icon_size=14, tooltip="Copy full UUID", on_click=copy_uuid)
                        ], spacing=2),
                        ft.Container(expand=True),
                        ft.Row([
                            ft.Container(
                                content=ft.Text("ACTIVE" if is_active else "INACTIVE", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY if is_active else ft.Colors.OUTLINE),
                                padding=ft.Padding.symmetric(horizontal=8, vertical=2),
                                border_radius=4,
                                border=ft.Border.all(1, ft.Colors.PRIMARY if is_active else ft.Colors.OUTLINE)
                            ),
                            ft.FilledTonalButton("Use Profile", icon=ft.Icons.CHECK if is_active else ft.Icons.SWITCH_ACCOUNT, on_click=lambda ev, a=acc: switch_account(a))
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                    ])
                )
            )
            accounts_grid.controls.append(card)
        page.update()

    def add_acc_action(e):
        val = new_acc_username_field.value.strip()
        if not val:
            return
        if any(a["username"].lower() == val.lower() for a in accounts_list):
            notify("Account already exists!", is_error=True)
            return
        new_acc = {
            "id": str(uuid.uuid4())[:8],
            "username": val,
            "uuid": str(uuid.uuid4()),
            "type": "offline",
            "skin": "default",
            "created_at": time.strftime("%Y-%m-%d")
        }
        accounts_list.append(new_acc)
        save_accounts(accounts_list)
        new_acc_username_field.value = ""
        switch_account(new_acc)
        refresh_accounts_view()
        notify(f"Added profile '{val}'")

    def delete_acc_action(acc):
        nonlocal current_account
        if acc in accounts_list:
            accounts_list.remove(acc)
            save_accounts(accounts_list)
            if current_account == acc and accounts_list:
                switch_account(accounts_list[0])
            refresh_accounts_view()
            notify(f"Deleted profile '{acc['username']}'")

    refresh_accounts_view()

    accounts_page_view = ft.Container(
        padding=24,
        expand=True,
        content=ft.Column([
            ft.Row([
                ft.Column([
                    ft.Text("Multi-User Account Manager", size=24, weight=ft.FontWeight.BOLD),
                    ft.Text("Create, configure, and switch between offline player profiles seamlessly", size=13, color=ft.Colors.ON_SURFACE_VARIANT)
                ], spacing=2),
                ft.Row([
                    new_acc_username_field,
                    ft.FilledButton("Add Profile", icon=ft.Icons.PERSON_ADD, on_click=add_acc_action)
                ], spacing=8)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Container(height=12),
            accounts_grid
        ], expand=True)
    )

    # --- VIEW 5: LOGS ---
    log_view = ft.ListView(expand=True, spacing=2, auto_scroll=True)

    def clear_logs(e):
        log_view.controls.clear()
        logs_buffer.clear()
        page.update()
        notify("Console logs cleared.")

    def export_logs(e):
        export_file = APP_DIR / f"craftpulse_log_{int(time.time())}.txt"
        with open(export_file, "w", encoding="utf-8") as f:
            f.write("\n".join(logs_buffer))
        notify(f"Exported logs to {export_file}")

    def rebuild_log_view(e=None):
        log_view.controls.clear()
        for line in logs_buffer[-500:]:
            clr = ft.Colors.ON_SURFACE_VARIANT
            if "ERROR" in line or "Exception" in line or "FATAL" in line:
                clr = ft.Colors.RED_ACCENT
            elif "WARN" in line:
                clr = ft.Colors.AMBER_ACCENT
            elif "[CraftPulse]" in line:
                clr = ft.Colors.PRIMARY
            log_view.controls.append(
                ft.Text(line, size=12, font_family="Consolas, monospace", color=clr, selectable=True)
            )
        try:
            log_view.update()
        except Exception:
            pass
        page.update()
        if e:
            notify("Refreshed log output.")

    auto_refresh_switch = ft.Switch(
        value=config.get("auto_refresh_logs", True),
        label="Auto-scroll",
        tooltip="Automatically scroll to the latest log line",
        on_change=lambda e: [
            config.__setitem__("auto_refresh_logs", e.control.value),
            save_config(config),
            notify("Auto-scroll " + ("enabled" if e.control.value else "disabled"))
        ]
    )

    logs_page_view = ft.Container(
        padding=24,
        expand=True,
        content=ft.Column([
            ft.Row([
                ft.Column([
                    ft.Text("Game & Launch Logs", size=24, weight=ft.FontWeight.BOLD),
                    ft.Text("Real-time stdout/stderr stream from Java Virtual Machine", size=13, color=ft.Colors.ON_SURFACE_VARIANT)
                ], spacing=2),
                ft.Row([
                    auto_refresh_switch,
                    ft.FilledTonalButton("Refresh Logs", icon=ft.Icons.REFRESH, on_click=rebuild_log_view),
                    ft.OutlinedButton("Clear Logs", icon=ft.Icons.CLEAR_ALL, on_click=clear_logs),
                    ft.FilledButton("Export Logs", icon=ft.Icons.SAVE_ALT, on_click=export_logs),
                ], spacing=10)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Container(height=10),
            ft.Container(
                content=log_view,
                expand=True,
                bgcolor=ft.Colors.BLACK,
                border_radius=10,
                border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
                padding=14
            )
        ], expand=True)
    )


    # --- VIEW 6: MATERIAL YOU SETTINGS & JVM OPTIMIZATION ---
    def update_seed_color(clr_hex: str):
        config["theme_seed_color"] = clr_hex
        save_config(config)
        page.theme = ft.Theme(color_scheme_seed=clr_hex, use_material3=True)
        page.dark_theme = ft.Theme(color_scheme_seed=clr_hex, use_material3=True)
        page.update()
        notify(f"Material You seed updated to {clr_hex}")

    def toggle_dark_light(e):
        is_dark = e.control.value
        page.theme_mode = ft.ThemeMode.DARK if is_dark else ft.ThemeMode.LIGHT
        config["theme_mode"] = "dark" if is_dark else "light"
        save_config(config)
        page.update()

    theme_chips_row = ft.Row(wrap=True, spacing=10)
    for p in THEME_PRESETS:
        btn = ft.Container(
            content=ft.Row([
                ft.Container(width=16, height=16, border_radius=8, bgcolor=p["color"]),
                ft.Text(p["name"], size=12, weight=ft.FontWeight.W_500)
            ], spacing=8),
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border_radius=20,
            ink=True,
            on_click=lambda ev, c=p["color"]: update_seed_color(c)
        )
        theme_chips_row.controls.append(btn)

    ram_slider = ft.Slider(
        min=1024,
        max=16384,
        divisions=15,
        value=config.get("jvm_max_ram", 4096),
        label="{value} MB",
        on_change=lambda e: ram_label.__setattr__("value", f"{int(e.control.value)} MB ({round(e.control.value/1024, 1)} GB)") or page.update()
    )
    ram_label = ft.Text(f"{config.get('jvm_max_ram', 4096)} MB ({round(config.get('jvm_max_ram', 4096)/1024, 1)} GB)", weight=ft.FontWeight.BOLD)

    custom_jvm_input = ft.TextField(
        label="Global JVM Arguments",
        value=config.get("jvm_args", ""),
        dense=True
    )
    java_path_input = ft.TextField(
        label="Global Fallback Java Path (Leave empty for Auto Mojang JDK)",
        value=config.get("global_java_path", ""),
        dense=True
    )
    res_dropdown = ft.Dropdown(
        label="Game Window Resolution",
        dense=True,
        value=config.get("game_resolution", "854x480"),
        options=[
            ft.dropdown.Option("854x480", "854x480 (Default Standard)"),
            ft.dropdown.Option("1280x720", "1280x720 (720p HD)"),
            ft.dropdown.Option("1920x1080", "1920x1080 (1080p Full HD)"),
            ft.dropdown.Option("2560x1440", "2560x1440 (2K QHD)")
        ]
    )

    def save_settings_btn(e):
        config["jvm_max_ram"] = int(ram_slider.value)
        config["jvm_args"] = custom_jvm_input.value.strip()
        config["global_java_path"] = java_path_input.value.strip()
        config["game_resolution"] = res_dropdown.value
        save_config(config)
        notify("Launcher settings saved successfully!")

    def reset_config_action(e):
        from lib.mc_core import DEFAULT_CONFIG, save_config as _sc, CONFIG_FILE
        _sc(DEFAULT_CONFIG.copy())
        notify("Config reset to defaults. Restart the launcher to apply.")

    settings_page_view = ft.Container(
        padding=24,
        expand=True,
        content=ft.ListView(
            expand=True,
            spacing=16,
            controls=[
                ft.Text("Settings & Personalization", size=24, weight=ft.FontWeight.BOLD),
                ft.Text(f"Installation Root: {APP_DIR} • System: {platform.system()} ({platform.architecture()[0]})", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Divider(),

                ft.Text("Material You Color Scheme Seed", size=16, weight=ft.FontWeight.BOLD),
                ft.Text("Click a dynamic palette seed to instantly restyle the entire launcher:", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                theme_chips_row,
                ft.Row([
                    ft.Text("Dark Mode Theme", size=14, weight=ft.FontWeight.W_500),
                    ft.Switch(value=(config.get("theme_mode", "dark") == "dark"), on_change=toggle_dark_light)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),

                ft.Divider(),
                ft.Text("Java & Memory Allocation", size=16, weight=ft.FontWeight.BOLD),
                ft.Row([
                    ft.Text("Allocated Memory (Max RAM): ", size=14),
                    ram_label
                ]),
                ram_slider,
                custom_jvm_input,
                java_path_input,
                res_dropdown,

                ft.Divider(),
                ft.Text("Launcher Behavior", size=16, weight=ft.FontWeight.BOLD),
                ft.Row([
                    ft.Text("Auto-scroll console logs", size=14, weight=ft.FontWeight.W_500),
                    ft.Switch(
                        value=config.get("auto_refresh_logs", True),
                        on_change=lambda e: [
                            config.__setitem__("auto_refresh_logs", e.control.value),
                            save_config(config),
                            auto_refresh_switch.__setattr__("value", e.control.value),
                            auto_refresh_switch.update()
                        ]
                    )
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),

                ft.Container(height=10),
                ft.Row([
                    ft.FilledButton("Save Configuration", icon=ft.Icons.SAVE, on_click=save_settings_btn),
                    ft.FilledTonalButton("Open App Folder", icon=ft.Icons.FOLDER_OPEN, on_click=lambda e: os.startfile(APP_DIR)),
                    ft.OutlinedButton("Reset to Defaults", icon=ft.Icons.RESTORE, on_click=reset_config_action),
                ], spacing=10, wrap=True),
                ft.Text(
                    f"CraftPulse v2.0 • Press F5 to launch • Ctrl+F2 to force-stop",
                    size=11, color=ft.Colors.OUTLINE
                ),
                ft.Container(height=30)
            ]
        )
    )

    # --- VIEW 0: HOME / DASHBOARD ---
    def render_dashboard_view():
        total_time_mins = sum(i.get("playtime_seconds", 0) for i in instances_list) // 60
        total_instances = len(instances_list)
        total_mods = sum(len(list((Path(i["path"]) / "mods").glob("*.jar"))) for i in instances_list if Path(i["path"]).exists())
        total_accounts = len(accounts_list)

        return ft.Container(
            padding=24,
            expand=True,
            content=ft.ListView(
                expand=True,
                spacing=18,
                controls=[
                    ft.Row([
                        ft.Column([
                            ft.Text("Daily Pulse Dashboard", size=24, weight=ft.FontWeight.BOLD),
                            ft.Text(f"Storage: {APP_DIR}", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
                        ], spacing=2),
                        ft.FilledTonalButton("Quick Launch", icon=ft.Icons.FLASH_ON, on_click=launch_current_instance)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    
                    ft.Row([
                        ft.Card(
                            expand=True,
                            content=ft.Container(
                                padding=18,
                                content=ft.Column([
                                    ft.Row([ft.Icon(ft.Icons.FOLDER_SPECIAL, color=ft.Colors.PRIMARY), ft.Text("Instances", size=13, color=ft.Colors.ON_SURFACE_VARIANT)], spacing=8),
                                    ft.Text(str(total_instances), size=28, weight=ft.FontWeight.BOLD)
                                ], spacing=4)
                            )
                        ),
                        ft.Card(
                            expand=True,
                            content=ft.Container(
                                padding=18,
                                content=ft.Column([
                                    ft.Row([ft.Icon(ft.Icons.EXTENSION, color=ft.Colors.TERTIARY), ft.Text("Installed Mods", size=13, color=ft.Colors.ON_SURFACE_VARIANT)], spacing=8),
                                    ft.Text(str(total_mods), size=28, weight=ft.FontWeight.BOLD)
                                ], spacing=4)
                            )
                        ),
                        ft.Card(
                            expand=True,
                            content=ft.Container(
                                padding=18,
                                content=ft.Column([
                                    ft.Row([ft.Icon(ft.Icons.PEOPLE_ALT, color=ft.Colors.SECONDARY), ft.Text("Profiles", size=13, color=ft.Colors.ON_SURFACE_VARIANT)], spacing=8),
                                    ft.Text(str(total_accounts), size=28, weight=ft.FontWeight.BOLD)
                                ], spacing=4)
                            )
                        ),
                        ft.Card(
                            expand=True,
                            content=ft.Container(
                                padding=18,
                                content=ft.Column([
                                    ft.Row([ft.Icon(ft.Icons.TIMER, color=ft.Colors.AMBER), ft.Text("Total Playtime", size=13, color=ft.Colors.ON_SURFACE_VARIANT)], spacing=8),
                                    ft.Text(f"{round(total_time_mins/60, 1)} hrs", size=28, weight=ft.FontWeight.BOLD)
                                ], spacing=4)
                            )
                        ),
                    ], spacing=14),

                    ft.Text("Quick Launch & Actions", size=16, weight=ft.FontWeight.BOLD),
                    ft.Row([
                        ft.FilledTonalButton("Instance Java / Settings", icon=ft.Icons.TUNE, on_click=lambda e: open_instance_settings_dialog(current_instance)),
                        ft.FilledTonalButton("Install Mod Loader", icon=ft.Icons.BUILD, on_click=lambda e: open_install_modloader_dialog(current_instance)),
                        ft.FilledTonalButton("Create New Instance", icon=ft.Icons.ADD_BOX, on_click=open_create_instance_dialog),
                        ft.FilledTonalButton("Explore Modrinth Mods", icon=ft.Icons.TRAVEL_EXPLORE, on_click=lambda e: [setattr(nav_rail, 'selected_index', 2), switch_view(2)]),
                        ft.FilledTonalButton("Switch Player Profile", icon=ft.Icons.PEOPLE, on_click=open_accounts_dialog),
                    ], wrap=True, spacing=10),

                    ft.Card(
                        content=ft.Container(
                            padding=18,
                            content=ft.Column([
                                ft.Row([ft.Icon(ft.Icons.AUTO_AWESOME, color=ft.Colors.PRIMARY), ft.Text("Active Instance Status", weight=ft.FontWeight.BOLD)], spacing=8),
                                ft.Text(
                                    f"Current Target: {current_instance.get('name', 'None')} • Loader: {current_instance.get('loader', 'vanilla').upper()} • Java: {current_instance.get('custom_java_path') or 'Auto Mojang JDK'}"
                                    if current_instance
                                    else "Current Target: None • Loader: None • Java: Auto Mojang JDK",
                                    size=12,
                                    color=ft.Colors.ON_SURFACE_VARIANT
                                )
                            ], spacing=6)
                        )
                    )
                ]
            )
        )

    # --- VIEW 7: SCREENSHOTS ---
    screenshots_grid_view = ft.GridView(expand=True, max_extent=240, spacing=10, run_spacing=10)

    def refresh_screenshots():
        screenshots_grid_view.controls.clear()
        if not current_instance:
            screenshots_grid_view.controls.append(
                ft.Container(
                    content=ft.Text("Select an instanfce to view its screenshots.", color=ft.Colors.ON_SURFACE_VARIANT),
                    padding=30
                )
            )
        else:
            ss_dir = Path(current_instance["path"]) / "screenshots"
            ss_dir.mkdir(parents=True, exist_ok=True)
            images = list(ss_dir.glob("*.png")) + list(ss_dir.glob("*.jpg"))
            if not images:
                screenshots_grid_view.controls.append(
                    ft.Container(
                        content=ft.Column([
                            ft.Icon(ft.Icons.PHOTO_CAMERA_BACK, size=48, color=ft.Colors.OUTLINE),
                            ft.Text("No screenshots yet — press F2 in Minecraft to take one!", color=ft.Colors.ON_SURFACE_VARIANT)
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        padding=40,
                        alignment=ft.Alignment(0, 0)
                    )
                )
            else:
                for img in sorted(images, key=lambda f: f.stat().st_mtime, reverse=True):
                    screenshots_grid_view.controls.append(
                        ft.Card(
                            elevation=2,
                            content=ft.Container(
                                padding=8,
                                content=ft.Column([
                                    ft.Image(src=str(img), fit=ft.BoxFit.COVER, height=140, border_radius=8),
                                    ft.Text(img.name, size=10, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, color=ft.Colors.ON_SURFACE_VARIANT),
                                    ft.Row([
                                        ft.IconButton(ft.Icons.OPEN_IN_NEW, tooltip="Open Image", icon_size=16, on_click=lambda ev, p=img: os.startfile(p)),
                                        ft.IconButton(ft.Icons.FOLDER_OPEN, tooltip="Open Folder", icon_size=16, on_click=lambda ev, d=ss_dir: os.startfile(d)),
                                        ft.IconButton(ft.Icons.DELETE_OUTLINE, tooltip="Delete", icon_color=ft.Colors.RED_400, icon_size=16,
                                                      on_click=lambda ev, p=img: [os.remove(p), refresh_screenshots(), page.update(), notify(f"Deleted {p.name}")]),
                                    ], spacing=0)
                                ], spacing=4)
                            )
                        )
                    )
        page.update()

    screenshots_page_view = ft.Container(
        padding=24,
        expand=True,
        content=ft.Column([
            ft.Row([
                ft.Column([
                    ft.Text("Screenshots", size=24, weight=ft.FontWeight.BOLD),
                    ft.Text("Screenshots saved by Minecraft (press F2 in-game)", size=13, color=ft.Colors.ON_SURFACE_VARIANT)
                ], spacing=2),
                ft.Row([
                    ft.FilledTonalButton("Refresh", icon=ft.Icons.REFRESH, on_click=lambda e: [refresh_screenshots()]),
                    ft.FilledButton("Open Folder", icon=ft.Icons.FOLDER_OPEN, on_click=lambda e: os.startfile(Path(current_instance["path"]) / "screenshots") if current_instance else notify("No instance selected", is_error=True))
                ], spacing=10)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Container(height=10),
            screenshots_grid_view
        ], expand=True)
    )

    # ROUTING
    views = [
        render_dashboard_view(),   # 0: Home Dashboard
        instances_view,            # 1: Instances
        mod_browser_view,          # 2: Modrinth Browser
        instance_content_view,     # 3: Instance Files
        accounts_page_view,        # 4: Accounts Manager
        logs_page_view,            # 5: Console Logs
        settings_page_view,        # 6: Settings & Theming
        screenshots_page_view,     # 7: Screenshots
    ]

    content_holder = ft.Container(expand=True, content=views[0])

    def switch_view(idx: int):
        if idx == 0:
            views[0] = render_dashboard_view()
        elif idx == 1:
            refresh_instances_grid()
        elif idx == 3:
            refresh_instance_mods_tab()
            refresh_instance_resourcepacks_tab()
            refresh_instance_worlds_tab()
        elif idx == 4:
            refresh_accounts_view()
        elif idx == 5:
            rebuild_log_view()
        elif idx == 7:
            refresh_screenshots()
        content_holder.content = views[idx]
        page.update()


    nav_rail = ft.NavigationRail(
        selected_index=0,
        label_type=ft.NavigationRailLabelType.ALL,
        min_width=80,
        min_extended_width=180,
        group_alignment=-0.9,
        destinations=[
            ft.NavigationRailDestination(icon=ft.Icons.DASHBOARD_OUTLINED, selected_icon=ft.Icons.DASHBOARD, label="Home"),
            ft.NavigationRailDestination(icon=ft.Icons.GRID_VIEW_OUTLINED, selected_icon=ft.Icons.GRID_VIEW, label="Instances"),
            ft.NavigationRailDestination(icon=ft.Icons.TRAVEL_EXPLORE_OUTLINED, selected_icon=ft.Icons.TRAVEL_EXPLORE, label="Modrinth"),
            ft.NavigationRailDestination(icon=ft.Icons.EXTENSION_OUTLINED, selected_icon=ft.Icons.EXTENSION, label="Files"),
            ft.NavigationRailDestination(icon=ft.Icons.PEOPLE_OUTLINE, selected_icon=ft.Icons.PEOPLE, label="Accounts"),
            ft.NavigationRailDestination(icon=ft.Icons.TERMINAL_OUTLINED, selected_icon=ft.Icons.TERMINAL, label="Logs"),
            ft.NavigationRailDestination(icon=ft.Icons.SETTINGS_OUTLINED, selected_icon=ft.Icons.SETTINGS, label="Settings"),
            ft.NavigationRailDestination(icon=ft.Icons.PHOTO_LIBRARY_OUTLINED, selected_icon=ft.Icons.PHOTO_LIBRARY, label="Screenshots"),
        ],
        on_change=lambda e: switch_view(e.control.selected_index)
    )

    top_header = ft.Container(
        padding=ft.Padding.symmetric(horizontal=20, vertical=10),
        bgcolor=ft.Colors.SURFACE_CONTAINER,
        border=ft.Border(bottom=ft.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
        content=ft.Row([
            ft.Row([
                ft.Icon(ft.Icons.TOKEN, color=ft.Colors.PRIMARY, size=28),
                ft.Text("CraftPulse", size=20, weight=ft.FontWeight.BOLD),
                ft.Container(
                    content=ft.Text("MATERIAL YOU 2.0", size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                    padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                    border_radius=4,
                    border=ft.Border.all(1, ft.Colors.PRIMARY)
                )
            ], spacing=10),
            ft.Row([
                ft.Container(
                    content=ft.Row([
                        ft.CircleAvatar(content=account_avatar_text, radius=14, bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH),
                        account_dropdown_label,
                        ft.Icon(ft.Icons.ARROW_DROP_DOWN, size=18)
                    ], spacing=8),
                    padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                    border_radius=24,
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    ink=True,
                    tooltip="Switch Player Account",
                    on_click=open_accounts_dialog
                )
            ], spacing=12)
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
    )

    body = ft.Row([
        nav_rail,
        ft.VerticalDivider(width=1),
        content_holder
    ], expand=True, spacing=0)

    page.add(
        ft.Column([
            top_header,
            body,
            bottom_play_dock
        ], expand=True, spacing=0)
    )

if __name__ == "__main__":
    if hasattr(ft, "run"):
        ft.run(main)
    else:
        ft.app(target=main)
