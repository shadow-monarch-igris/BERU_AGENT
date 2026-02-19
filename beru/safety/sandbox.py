from __future__ import annotations

import os
import re
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from beru.utils.config import get_config
from beru.utils.logger import get_logger

logger = get_logger("beru.safety")


@dataclass
class SandboxResult:
    allowed: bool
    reason: str = ""
    sanitized: Optional[str] = None


class CommandSandbox:
    def __init__(self):
        config = get_config().safety
        self.forbidden_commands = config.forbidden_commands
        self.forbidden_patterns = [
            r"rm\s+-rf\s+/",
            r"rm\s+-rf\s+~",
            r">\s*/dev/sd[a-z]",
            r"mkfs\.",
            r"dd\s+if=",
            r":\(\)\s*\{\s*:\|:&\s*\};\s*:",
            r"sudo\s+rm",
            r"chmod\s+777",
            r"chown\s+.*\s+/",
        ]
        self.allowed_commands = [
            "ls",
            "cat",
            "grep",
            "find",
            "head",
            "tail",
            "wc",
            "echo",
            "pwd",
            "cd",
            "mkdir",
            "touch",
            "cp",
            "mv",
            "python",
            "python3",
            "pip",
            "pip3",
            "npm",
            "node",
            "git",
            "docker",
            "curl",
            "wget",
        ]

    def validate(self, command: str) -> SandboxResult:
        if not command or not command.strip():
            return SandboxResult(allowed=False, reason="Empty command")

        command_lower = command.lower().strip()

        for forbidden in self.forbidden_commands:
            if forbidden.lower() in command_lower:
                logger.warning(f"Blocked forbidden command: {command}")
                return SandboxResult(
                    allowed=False,
                    reason=f"Command contains forbidden pattern: {forbidden}",
                )

        for pattern in self.forbidden_patterns:
            if re.search(pattern, command_lower):
                logger.warning(f"Blocked command matching forbidden pattern: {command}")
                return SandboxResult(
                    allowed=False,
                    reason=f"Command matches forbidden pattern: {pattern}",
                )

        base_cmd = command.split()[0] if command.split() else ""
        if base_cmd and base_cmd not in self.allowed_commands:
            logger.debug(f"Command not in allowed list: {base_cmd}")

        return SandboxResult(allowed=True, sanitized=command)

    def safe_execute(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: int = 60,
        capture_output: bool = True,
    ) -> Tuple[int, str, str]:
        validation = self.validate(command)
        if not validation.allowed:
            raise PermissionError(validation.reason)

        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                timeout=timeout,
                capture_output=capture_output,
                text=True,
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out: {command}")
            return -1, "", "Command timed out"
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            return -1, "", str(e)


class PathValidator:
    def __init__(self):
        config = get_config().safety
        self.allowed_paths = [
            Path(p).expanduser().resolve() for p in config.allowed_paths
        ]
        self.allowed_paths_raw = config.allowed_paths
        self.forbidden_paths = [
            Path(p).expanduser().resolve() for p in config.forbidden_paths
        ]
        self.max_file_size_mb = config.max_file_size_mb

    def _is_permissive_mode(self) -> bool:
        if not self.allowed_paths_raw:
            return True
        permissive_indicators = [".", "./", "~/", "~/projects", "~"]
        has_permissive = any(
            p in permissive_indicators or p.startswith("./") or p.startswith("~/")
            for p in self.allowed_paths_raw
        )
        return has_permissive or len(self.allowed_paths_raw) == 0

    def validate(self, path: str, must_exist: bool = False) -> SandboxResult:
        try:
            resolved = Path(path).expanduser().resolve()
        except Exception as e:
            return SandboxResult(allowed=False, reason=f"Invalid path: {e}")

        for forbidden in self.forbidden_paths:
            try:
                resolved.relative_to(forbidden)
                logger.warning(f"Access to forbidden path: {path}")
                return SandboxResult(
                    allowed=False, reason=f"Access to forbidden path: {forbidden}"
                )
            except ValueError:
                pass

        # In permissive mode, allow all paths except forbidden ones
        if self._is_permissive_mode():
            if must_exist and not resolved.exists():
                return SandboxResult(
                    allowed=False, reason=f"Path does not exist: {path}"
                )
            return SandboxResult(allowed=True, sanitized=str(resolved))

        if self.allowed_paths:
            is_allowed = False
            for allowed in self.allowed_paths:
                try:
                    resolved.relative_to(allowed)
                    is_allowed = True
                    break
                except ValueError:
                    pass

            if not is_allowed:
                return SandboxResult(
                    allowed=False, reason=f"Path outside allowed directories: {path}"
                )

        if must_exist and not resolved.exists():
            return SandboxResult(allowed=False, reason=f"Path does not exist: {path}")

        return SandboxResult(allowed=True, sanitized=str(resolved))

    def validate_file_size(self, path: str) -> SandboxResult:
        try:
            resolved = Path(path).expanduser().resolve()
            if resolved.is_file():
                size_mb = resolved.stat().st_size / (1024 * 1024)
                if size_mb > self.max_file_size_mb:
                    return SandboxResult(
                        allowed=False,
                        reason=f"File too large: {size_mb:.2f}MB > {self.max_file_size_mb}MB",
                    )
        except Exception as e:
            return SandboxResult(allowed=False, reason=f"Cannot check file size: {e}")

        return SandboxResult(allowed=True)


class AuditLogger:
    def __init__(self, log_path: Optional[str] = None):
        config = get_config().safety
        self.enabled = config.audit_log
        self.log_path = Path(log_path or config.audit_log_path)

        if self.enabled:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        action: str,
        details: Dict[str, Any],
        user: Optional[str] = None,
        success: bool = True,
    ) -> None:
        if not self.enabled:
            return

        import json
        from datetime import datetime

        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "details": details,
            "user": user or "system",
            "success": success,
        }

        try:
            with open(self.log_path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")

    def log_tool_execution(
        self,
        tool_name: str,
        params: Dict[str, Any],
        result: Optional[Any] = None,
        error: Optional[str] = None,
    ) -> None:
        self.log(
            action="tool_execution",
            details={
                "tool": tool_name,
                "params": params,
                "result": str(result)[:500] if result else None,
                "error": error,
            },
            success=error is None,
        )

    def log_command(
        self,
        command: str,
        allowed: bool,
        reason: str = "",
    ) -> None:
        self.log(
            action="command_validation",
            details={
                "command": command,
                "allowed": allowed,
                "reason": reason,
            },
            success=allowed,
        )


class SafetyManager:
    def __init__(self):
        self.sandbox = CommandSandbox()
        self.path_validator = PathValidator()
        self.audit_logger = AuditLogger()

    def validate_command(self, command: str) -> SandboxResult:
        result = self.sandbox.validate(command)
        self.audit_logger.log_command(command, result.allowed, result.reason)
        return result

    def validate_path(
        self,
        path: str,
        must_exist: bool = False,
        check_size: bool = False,
    ) -> SandboxResult:
        result = self.path_validator.validate(path, must_exist)
        if result.allowed and check_size:
            size_result = self.path_validator.validate_file_size(path)
            if not size_result.allowed:
                return size_result
        return result

    def execute_command(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: int = 60,
    ) -> Tuple[int, str, str]:
        self.audit_logger.log(
            action="command_execution",
            details={"command": command, "cwd": cwd},
        )
        return self.sandbox.safe_execute(command, cwd, timeout)


_safety_manager: Optional[SafetyManager] = None


def get_safety_manager() -> SafetyManager:
    global _safety_manager
    if _safety_manager is None:
        _safety_manager = SafetyManager()
    return _safety_manager
