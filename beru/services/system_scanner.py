"""
System Scanner for BERU
Automatically collects system information for better assistance
"""

from __future__ import annotations

import json
import subprocess
import platform
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict, field

from beru.utils.logger import get_logger

logger = get_logger("beru.system_scanner")


@dataclass
class SystemInfo:
    os: str = ""
    distro: str = ""
    hostname: str = ""
    username: str = ""
    home_dir: str = ""
    shell: str = ""


@dataclass
class InstalledApp:
    name: str
    path: str
    version: str = ""


class SystemScanner:
    def __init__(self, output_dir: str = "beru/data"):
        self.output_dir = Path(output_dir)
        self.output_file = self.output_dir / "system.json"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.apps_to_check = {
            "editors": [
                "code",
                "code-insiders",
                "pycharm",
                "vim",
                "nano",
                "subl",
                "atom",
                "gedit",
            ],
            "browsers": [
                "firefox",
                "google-chrome",
                "chromium-browser",
                "brave-browser",
                "microsoft-edge",
            ],
            "terminals": [
                "gnome-terminal",
                "konsole",
                "xterm",
                "alacritty",
                "tilix",
                "terminator",
            ],
            "tools": [
                "git",
                "docker",
                "python3",
                "python",
                "node",
                "npm",
                "pip",
                "pip3",
                "cargo",
                "go",
            ],
        }

    def _run_command(self, cmd: List[str], timeout: int = 5) -> Optional[str]:
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            logger.debug(f"Command failed: {cmd} - {e}")
        return None

    def _check_app_installed(self, app_name: str) -> Optional[InstalledApp]:
        path = self._run_command(["which", app_name])
        if path:
            version = self._get_app_version(app_name)
            return InstalledApp(name=app_name, path=path, version=version or "")
        return None

    def _get_app_version(self, app_name: str) -> Optional[str]:
        version_flags = {
            "python": "--version",
            "python3": "--version",
            "node": "--version",
            "npm": "--version",
            "git": "--version",
            "docker": "--version",
            "code": "--version",
            "vim": "--version",
            "cargo": "--version",
            "go": "version",
        }

        flag = version_flags.get(app_name, "--version")
        try:
            output = self._run_command([app_name, flag])
            if output:
                return output.split("\n")[0][:60]
        except Exception:
            pass
        return None

    def scan_system_info(self) -> SystemInfo:
        info = SystemInfo()
        info.os = platform.system()
        info.hostname = platform.node()
        info.username = os.environ.get("USER", os.environ.get("USERNAME", "unknown"))
        info.home_dir = str(Path.home())
        info.shell = os.environ.get("SHELL", "bash")

        if info.os == "Linux":
            try:
                with open("/etc/os-release") as f:
                    for line in f:
                        if line.startswith("PRETTY_NAME="):
                            info.distro = line.split("=")[1].strip('"')
                            break
            except Exception:
                info.distro = "Linux"
        elif info.os == "Darwin":
            info.distro = f"macOS {platform.mac_ver()[0]}"
        elif info.os == "Windows":
            info.distro = f"Windows {platform.win_ver()[0]}"

        return info

    def scan_installed_apps(self) -> Dict[str, List[Dict]]:
        apps = {}

        for category, app_list in self.apps_to_check.items():
            apps[category] = []
            for app_name in app_list:
                app = self._check_app_installed(app_name)
                if app:
                    apps[category].append(asdict(app))

        return apps

    def scan_languages(self) -> Dict[str, Any]:
        languages = {}

        python_path = self._run_command(["which", "python3"]) or self._run_command(
            ["which", "python"]
        )
        if python_path:
            version = self._run_command(["python3", "--version"]) or self._run_command(
                ["python", "--version"]
            )
            try:
                packages = self._run_command(["pip", "list", "--format=freeze"]) or ""
                package_count = len(
                    [p for p in packages.split("\n") if p and "==" in p]
                )
            except Exception:
                package_count = 0

            languages["python"] = {
                "version": version.split()[-1] if version else "unknown",
                "path": python_path,
                "packages_count": package_count,
            }

        node_path = self._run_command(["which", "node"])
        if node_path:
            version = self._run_command(["node", "--version"])
            languages["node"] = {
                "version": version.lstrip("v") if version else "unknown",
                "path": node_path,
            }

        go_path = self._run_command(["which", "go"])
        if go_path:
            version = self._run_command(["go", "version"])
            languages["go"] = {
                "version": version.split()[2] if version else "unknown",
                "path": go_path,
            }

        return languages

    def scan_directories(self) -> Dict[str, Any]:
        home = Path.home()
        dirs = {
            "home": str(home),
            "downloads": str(home / "Downloads"),
            "documents": str(home / "Documents"),
            "desktop": str(home / "Desktop"),
            "pictures": str(home / "Pictures"),
            "music": str(home / "Music"),
            "videos": str(home / "Videos"),
            "projects": str(home / "projects"),
            "workspace": str(home / "workspace"),
        }

        existing = {}
        for name, path in dirs.items():
            if Path(path).exists():
                try:
                    items = list(Path(path).iterdir())
                    existing[name] = {
                        "path": path,
                        "exists": True,
                        "items_count": len(items),
                    }
                except Exception:
                    existing[name] = {"path": path, "exists": True, "items_count": 0}

        return existing

    def scan_recent_projects(self) -> List[Dict[str, str]]:
        projects = []
        home = Path.home()

        search_paths = [
            home / "projects",
            home / "workspace",
            home / "code",
            home / "dev",
            home / "Documents",
            home / "Downloads",
        ]

        for search_path in search_paths:
            if not search_path.exists():
                continue
            try:
                for item in list(search_path.iterdir())[:20]:
                    if item.is_dir() and not item.name.startswith("."):
                        is_project = any(
                            (item / f).exists()
                            for f in [
                                ".git",
                                "package.json",
                                "requirements.txt",
                                "setup.py",
                                "Cargo.toml",
                                "go.mod",
                            ]
                        )
                        if is_project:
                            projects.append(
                                {
                                    "name": item.name,
                                    "path": str(item),
                                    "type": self._detect_project_type(item),
                                }
                            )
            except Exception:
                pass

        return projects[:15]

    def _detect_project_type(self, path: Path) -> str:
        if (path / "requirements.txt").exists() or (path / "setup.py").exists():
            return "python"
        if (path / "package.json").exists():
            return "node"
        if (path / "Cargo.toml").exists():
            return "rust"
        if (path / "go.mod").exists():
            return "go"
        return "unknown"

    def scan_all(self) -> Dict[str, Any]:
        logger.info("Starting system scan...")

        return {
            "scan_date": datetime.now().isoformat(),
            "system": asdict(self.scan_system_info()),
            "installed_apps": self.scan_installed_apps(),
            "languages": self.scan_languages(),
            "directories": self.scan_directories(),
            "recent_projects": self.scan_recent_projects(),
        }

    def save(self, data: Dict[str, Any]) -> None:
        with open(self.output_file, "w") as f:
            json.dump(data, f, indent=2)
        logger.info(f"System scan saved to {self.output_file}")

    def load(self) -> Optional[Dict[str, Any]]:
        if self.output_file.exists():
            with open(self.output_file, "r") as f:
                return json.load(f)
        return None

    def needs_rescan(self) -> bool:
        if not self.output_file.exists():
            return True

        try:
            data = self.load()
            if not data:
                return True

            scan_date = datetime.fromisoformat(data.get("scan_date", ""))
            days_old = (datetime.now() - scan_date).days
            return days_old > 7
        except Exception:
            return True

    def run_and_save(self) -> Dict[str, Any]:
        data = self.scan_all()
        self.save(data)
        return data


def get_system_scanner() -> SystemScanner:
    return SystemScanner()


async def run_system_scan() -> Dict[str, Any]:
    scanner = SystemScanner()
    return scanner.run_and_save()
