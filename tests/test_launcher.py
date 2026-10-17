
import ctypes
import os
import sys
import shutil
import unittest
from pathlib import Path


# ─────────────────────────────────────────────
# Project setup
# ─────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lib.mc_core import (
    APP_DIR,
    INSTANCES_DIR,
    SHARED_MC_DIR,
    JDK_DIR,
    load_config,
    save_config,
    load_accounts,
    save_accounts,
    get_instances,
    save_instance_metadata,
    fetch_mojang_versions,
    search_modrinth,
    get_modrinth_project_versions,
    resolve_or_download_java,
    install_modloader_to_instance,
)


# ─────────────────────────────────────────────
# Real terminal colors, including Windows CMD
# ─────────────────────────────────────────────

RESET = "\033[0m"
GREEN = "\033[92m"
RED = "\033[91m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
DIM = "\033[2m"
BOLD = "\033[1m"

COLOR_ENABLED = False


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def enable_terminal_colors():
    """Enable ANSI escape sequences in Windows consoles."""
    global COLOR_ENABLED

    if os.environ.get("NO_COLOR") is not None:
        return

    if not sys.stdout.isatty():
        return

    if os.name == "nt":
        try:
            kernel32 = ctypes.windll.kernel32

            # STD_OUTPUT_HANDLE = -11
            # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            handle = kernel32.GetStdHandle(-11)
            mode = ctypes.c_uint()

            if handle in (0, -1):
                return

            if not kernel32.GetConsoleMode(
                handle, ctypes.byref(mode)
            ):
                return

            if not kernel32.SetConsoleMode(
                handle, mode.value | 0x0004
            ):
                return

            COLOR_ENABLED = True
            return
        except (AttributeError, OSError):
            return

    COLOR_ENABLED = True


def paint(text, color):
    if not COLOR_ENABLED:
        return text
    return f"{color}{text}{RESET}"


def heading(text):
    print(paint(text, BOLD + CYAN))


# ─────────────────────────────────────────────
# Test result reporter
# ─────────────────────────────────────────────

class CleanTestResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._test_number = 0

    def _report(self, status, color, test):
        self._test_number += 1
        name = test.shortDescription() or test._testMethodName
        print(
            f"  {paint('[' + status + ']', color):<24} {name}",
            file=sys.stdout,
            flush=True,
        )

    def addSuccess(self, test):
        super().addSuccess(test)
        self._report("OK", GREEN, test)

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._report("FAILED", RED, test)

    def addError(self, test, err):
        super().addError(test, err)
        self._report("ERROR", RED, test)

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._report("SKIP", YELLOW, test)


class CleanTestRunner(unittest.TextTestRunner):
    resultclass = CleanTestResult


# ─────────────────────────────────────────────
# CraftPulse core test suite
# ─────────────────────────────────────────────

class TestCraftPulseCore(unittest.TestCase):

    def test_01_directories_exist(self):
        """Application storage directories exist."""
        load_config()

        for directory in (
            APP_DIR,
            INSTANCES_DIR,
            SHARED_MC_DIR,
            JDK_DIR,
        ):
            with self.subTest(directory=directory):
                self.assertTrue(directory.exists())
                self.assertTrue(directory.is_dir())

    def test_02_config_has_required_keys(self):
        """Configuration contains required settings."""
        cfg = load_config()

        self.assertIsInstance(cfg, dict)
        self.assertIn("theme_seed_color", cfg)
        self.assertIn("jvm_max_ram", cfg)

    def test_03_config_persistence(self):
        """Configuration survives a save and reload."""
        original = load_config()

        try:
            updated = dict(original)
            updated["theme_seed_color"] = "#2E7D32"

            save_config(updated)

            reloaded = load_config()
            self.assertEqual(
                reloaded["theme_seed_color"], "#2E7D32"
            )
        finally:
            save_config(original)

    def test_04_config_ram_is_valid(self):
        """Configured JVM memory is a positive integer."""
        ram = load_config()["jvm_max_ram"]

        self.assertIsInstance(ram, int)
        self.assertGreater(ram, 0)

    def test_05_accounts_have_valid_structure(self):
        """Account storage contains valid account records."""
        accounts = load_accounts()

        self.assertIsInstance(accounts, list)

        for account in accounts:
            with self.subTest(account=account):
                self.assertIsInstance(account, dict)
                self.assertIn("username", account)
                self.assertIsInstance(account["username"], str)
                self.assertTrue(account["username"].strip())

    def test_06_account_save_reload(self):
        """Existing account data survives a save and reload."""
        original = load_accounts()

        try:
            save_accounts(original)
            reloaded = load_accounts()
            self.assertEqual(reloaded, original)
        finally:
            save_accounts(original)

    def test_07_instances_have_valid_structure(self):
        """Instance metadata has the expected structure."""
        instances = get_instances()

        self.assertIsInstance(instances, list)

        for instance in instances:
            with self.subTest(instance=instance):
                self.assertIsInstance(instance, dict)
                self.assertIn("id", instance)
                self.assertIn("name", instance)

    def test_08_instance_metadata_roundtrip(self):
        """Instance metadata saves and reloads correctly."""
        instance_id = "craftpulse_test_instance"
        test_dir = INSTANCES_DIR / instance_id

        # Remove any stale test data before starting.
        shutil.rmtree(test_dir, ignore_errors=True)

        self.addCleanup(
            lambda: shutil.rmtree(test_dir, ignore_errors=True)
        )

        metadata = {
            "id": instance_id,
            "name": "CraftPulse Test Instance",
            "version": "1.20.4",
            "loader": "fabric",
            "custom_java_path": "",
            "custom_jvm_ram": 2048,
            "playtime_seconds": 120,
        }

        save_instance_metadata(instance_id, metadata)

        matching = [
            item for item in get_instances()
            if item.get("id") == instance_id
        ]

        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["name"], metadata["name"])
        self.assertEqual(matching[0]["version"], "1.20.4")
        self.assertEqual(matching[0]["loader"], "fabric")
        self.assertEqual(matching[0]["custom_jvm_ram"], 2048)

    def test_09_mojang_manifest(self):
        """Official Mojang version manifest is reachable."""
        versions = fetch_mojang_versions()

        self.assertIsInstance(versions, list)
        self.assertGreater(len(versions), 0)

        for version in versions[:5]:
            with self.subTest(version=version):
                self.assertIsInstance(version, dict)
                self.assertIn("id", version)
                self.assertIn("type", version)
                self.assertIn("url", version)

    def test_10_mojang_version_ids_are_unique(self):
        """Mojang manifest contains unique version IDs."""
        versions = fetch_mojang_versions()
        ids = [version["id"] for version in versions]

        self.assertEqual(len(ids), len(set(ids)))

    def test_11_modrinth_search(self):
        """Modrinth search returns valid project records."""
        results = search_modrinth("fabric-api", limit=3)

        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)

        for project in results:
            with self.subTest(project=project):
                self.assertIsInstance(project, dict)
                self.assertIn("title", project)
                self.assertIn("project_id", project)
                self.assertTrue(project["project_id"])

    def test_12_modrinth_project_versions(self):
        """Modrinth returns versions for Fabric API."""
        versions = get_modrinth_project_versions("fabric-api")

        self.assertIsInstance(versions, list)
        self.assertGreater(len(versions), 0)

        for version in versions:
            with self.subTest(version=version):
                self.assertIsInstance(version, dict)
                self.assertIn("id", version)
                self.assertIn("version_number", version)
                self.assertIn("game_versions", version)

    def test_13_modrinth_search_resourcepack(self):
        """Modrinth search supports resource packs."""
        results = search_modrinth("faithful", project_type="resourcepack", limit=3)

        self.assertIsInstance(results, list)
        for project in results:
            with self.subTest(project=project):
                self.assertIsInstance(project, dict)
                self.assertIn("title", project)
                self.assertEqual(project.get("project_type"), "resourcepack")

    def test_14_account_addition_and_cleanup(self):
        """New accounts can be appended and saved cleanly."""
        original = load_accounts()

        test_account = {
            "id": "test_player_unit_id",
            "username": "CraftPulseTester",
            "uuid": "00000000-0000-0000-0000-000000000000",
            "type": "offline",
            "skin": "default",
            "created_at": "2026-10-17"
        }

        try:
            updated = list(original) + [test_account]
            save_accounts(updated)
            reloaded = load_accounts()
            usernames = [acc.get("username") for acc in reloaded]
            self.assertIn("CraftPulseTester", usernames)
        finally:
            save_accounts(original)

    def test_15_resolve_java_prefers_instance_custom_path(self):
        """Java resolver honors custom Java path configured on an instance."""
        custom_exec = sys.executable  # using running python as a valid existing executable
        logs = []
        progress = []

        resolved = resolve_or_download_java(
            minecraft_version="1.20.4",
            instance_custom_java=custom_exec,
            progress_cb=lambda msg, val: progress.append((msg, val)),
            log_cb=lambda msg: logs.append(msg),
        )

        self.assertEqual(resolved, custom_exec)
        self.assertTrue(any("custom Java configured" in log for log in logs))

    def test_16_install_modloader_vanilla_switch(self):
        """Reverting an instance to vanilla clears loader_version_id and sets loader to vanilla."""
        instance_id = "craftpulse_vanilla_test"
        test_dir = INSTANCES_DIR / instance_id
        shutil.rmtree(test_dir, ignore_errors=True)
        self.addCleanup(lambda: shutil.rmtree(test_dir, ignore_errors=True))

        inst_data = {
            "id": instance_id,
            "name": "Vanilla Test",
            "version": "1.20.4",
            "loader": "fabric",
            "loader_version_id": "fabric-loader-0.15.7-1.20.4",
            "custom_java_path": "",
            "custom_jvm_ram": 0
        }
        save_instance_metadata(instance_id, inst_data)

        logs = []
        progress = []
        success = install_modloader_to_instance(
            instance=inst_data,
            loader_type="vanilla",
            progress_cb=lambda msg, val: progress.append((msg, val)),
            log_cb=lambda msg: logs.append(msg)
        )

        self.assertTrue(success)
        self.assertEqual(inst_data["loader"], "vanilla")
        self.assertIsNone(inst_data["loader_version_id"])

        # Check saved file reflects change
        instances = [i for i in get_instances() if i.get("id") == instance_id]
        self.assertEqual(len(instances), 1)
        self.assertEqual(instances[0]["loader"], "vanilla")
        self.assertIsNone(instances[0]["loader_version_id"])

    def test_17_config_game_resolution_format(self):
        """Configuration contains valid game resolution dimensions."""
        cfg = load_config()
        self.assertIn("game_resolution", cfg)
        res = cfg["game_resolution"]
        self.assertIn("x", res)
        parts = res.split("x")
        self.assertEqual(len(parts), 2)
        width, height = int(parts[0]), int(parts[1])
        self.assertGreater(width, 0)
        self.assertGreater(height, 0)


# ─────────────────────────────────────────────
# Execution and final summary
# ─────────────────────────────────────────────

def run_tests():
    enable_terminal_colors()

    print()
    heading("  CRAFTPULSE  /  CORE TEST SUITE")
    print(paint("  " + "─" * 48, DIM))
    print()

    suite = unittest.TestLoader().loadTestsFromTestCase(
        TestCraftPulseCore
    )

    runner = CleanTestRunner(
        stream=sys.stdout,
        verbosity=0,
        failfast=False,
        buffer=False,
    )

    result = runner.run(suite)

    total = result.testsRun
    failed = len(result.failures)
    errors = len(result.errors)
    skipped = len(result.skipped)
    passed = total - failed - errors - skipped

    print()
    print(paint("  " + "─" * 48, DIM))
    heading("  TEST SUMMARY")
    print()

    print(f"  Total tests : {total}")
    print(f"  {paint('[OK]', GREEN):<24} {passed} passed")
    print(f"  {paint('[FAILED]', RED):<24} {failed} failed")
    print(f"  {paint('[ERROR]', RED):<24} {errors} errors")
    print(f"  {paint('[SKIP]', YELLOW):<24} {skipped} skipped")
    print()

    if failed or errors:
        print(paint("  RESULT: TESTS FAILED", BOLD + RED))
        print()
        result.printErrors()
    elif skipped:
        print(paint("  RESULT: PASSED WITH SKIPS", BOLD + YELLOW))
    else:
        print(paint("  RESULT: ALL TESTS PASSED", BOLD + GREEN))

    print()
    return result.wasSuccessful()


if __name__ == "__main__":
    sys.exit(0 if run_tests() else 1)
