from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path
from typing import Dict, List, Optional, Type

from beru.plugins.base import Tool, ToolRegistry, get_tool_registry
from beru.utils.logger import get_logger

logger = get_logger("beru.plugins")


class PluginLoader:
    def __init__(self, plugin_dirs: Optional[List[str]] = None):
        self.plugin_dirs = plugin_dirs or ["./plugins", "./beru/plugins/tools"]
        self.registry = get_tool_registry()
        self._loaded_plugins: Dict[str, Path] = {}

    def discover_plugins(self) -> List[Path]:
        discovered = []

        for plugin_dir in self.plugin_dirs:
            plugin_path = Path(plugin_dir)
            if not plugin_path.exists():
                logger.debug(f"Plugin directory not found: {plugin_path}")
                continue

            for py_file in plugin_path.glob("**/*.py"):
                if py_file.name.startswith("_"):
                    continue
                discovered.append(py_file)

        logger.info(f"Discovered {len(discovered)} plugin files")
        return discovered

    def load_plugin(self, plugin_path: Path) -> List[Type[Tool]]:
        loaded_tools = []

        try:
            spec = importlib.util.spec_from_file_location(
                f"plugin_{plugin_path.stem}", plugin_path
            )

            if spec is None or spec.loader is None:
                logger.error(f"Failed to create spec for {plugin_path}")
                return loaded_tools

            module = importlib.util.module_from_spec(spec)
            sys.modules[f"plugin_{plugin_path.stem}"] = module
            if spec.loader:
                spec.loader.exec_module(module)

            for name, obj in inspect.getmembers(module):
                if (
                    inspect.isclass(obj)
                    and issubclass(obj, Tool)
                    and obj is not Tool
                    and hasattr(obj, "name")
                    and obj.name
                ):
                    loaded_tools.append(obj)
                    logger.info(f"Found tool class: {obj.name}")

                if inspect.isfunction(obj) and hasattr(obj, "_is_tool"):
                    self.registry.register_function(obj)
                    logger.info(
                        f"Registered function tool: {getattr(obj, '_tool_name', name)}"
                    )

            self._loaded_plugins[plugin_path.stem] = plugin_path

        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_path}: {e}")

        return loaded_tools

    def load_all(self) -> int:
        discovered = self.discover_plugins()
        total_tools = 0

        for plugin_path in discovered:
            tools = self.load_plugin(plugin_path)
            for tool_class in tools:
                try:
                    tool_instance = tool_class()
                    self.registry.register(tool_instance)
                    total_tools += 1
                    logger.info(f"Registered tool: {tool_instance.name}")
                except Exception as e:
                    logger.error(f"Failed to instantiate tool {tool_class}: {e}")

        logger.info(f"Loaded {total_tools} tools from {len(discovered)} plugin files")
        return total_tools

    def get_loaded_plugins(self) -> Dict[str, Path]:
        return self._loaded_plugins.copy()


def load_plugins(plugin_dirs: Optional[List[str]] = None) -> ToolRegistry:
    loader = PluginLoader(plugin_dirs)
    loader.load_all()
    return loader.registry
