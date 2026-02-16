"""Cron scheduling helpers for Beacon automation."""

import logging
import shutil
import subprocess
import sys

logger = logging.getLogger("beacon.automation.cron")

CRON_MARKER = "# beacon-automation"


def generate_crontab_entry(every_hours: int = 6) -> str:
    """Generate a crontab entry for beacon automation."""
    python = sys.executable
    beacon_cmd = f"{python} -m beacon.cli automation run"
    # Run at minute 0, every N hours
    return f"0 */{every_hours} * * * {beacon_cmd} {CRON_MARKER}"


def install_crontab(entry: str) -> bool:
    """Install a crontab entry. Returns True if successful."""
    if not shutil.which("crontab"):
        logger.error("crontab not found")
        return False

    try:
        # Get existing crontab
        result = subprocess.run(
            ["crontab", "-l"], capture_output=True, text=True, timeout=5
        )
        existing = result.stdout if result.returncode == 0 else ""

        # Remove any existing beacon entries
        lines = [line for line in existing.strip().split("\n") if CRON_MARKER not in line]
        lines = [line for line in lines if line.strip()]  # Remove empty lines

        # Add new entry
        lines.append(entry)
        new_crontab = "\n".join(lines) + "\n"

        # Install
        proc = subprocess.run(
            ["crontab", "-"], input=new_crontab, capture_output=True, text=True, timeout=5
        )
        return proc.returncode == 0

    except Exception as e:
        logger.error("Failed to install crontab: %s", e)
        return False


def uninstall_crontab() -> bool:
    """Remove beacon crontab entries. Returns True if an entry was removed."""
    if not shutil.which("crontab"):
        return False

    try:
        result = subprocess.run(
            ["crontab", "-l"], capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return False

        existing = result.stdout
        if CRON_MARKER not in existing:
            return False

        lines = [line for line in existing.strip().split("\n") if CRON_MARKER not in line]
        lines = [line for line in lines if line.strip()]

        if lines:
            new_crontab = "\n".join(lines) + "\n"
            subprocess.run(
                ["crontab", "-"], input=new_crontab, capture_output=True, text=True, timeout=5
            )
        else:
            subprocess.run(["crontab", "-r"], capture_output=True, timeout=5)

        return True

    except Exception as e:
        logger.error("Failed to uninstall crontab: %s", e)
        return False


def show_crontab_status() -> str:
    """Show current beacon crontab status."""
    if not shutil.which("crontab"):
        return "crontab not available on this system"

    try:
        result = subprocess.run(
            ["crontab", "-l"], capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return "No crontab configured"

        beacon_lines = [line for line in result.stdout.split("\n") if CRON_MARKER in line]
        if beacon_lines:
            return f"Beacon cron active:\n  {beacon_lines[0]}"
        return "No beacon cron entry found"

    except Exception as e:
        return f"Error checking crontab: {e}"
