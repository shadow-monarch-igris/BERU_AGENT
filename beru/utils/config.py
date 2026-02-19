from __future__ import annotations

import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass, field


@dataclass
class ModelConfig:
    provider: str = "ollama"
    name: str = "gemma"
    temperature: float = 0.2
    max_tokens: int = 4096
    timeout: int = 120
    base_url: str = "http://localhost:11434"


@dataclass
class MemoryConfig:
    type: str = "chromadb"
    persist_directory: str = "./data/chromadb"
    collection_name: str = "beru_memory"
    embedding_model: str = "all-MiniLM-L6-v2"


@dataclass
class AgentConfig:
    enabled: bool = True
    max_concurrent: int = 3
    tools: list = field(default_factory=list)


@dataclass
class WorkflowConfig:
    parallel_timeout: int = 300
    max_parallel_tasks: int = 5
    retry_attempts: int = 3
    retry_delay: int = 2


@dataclass
class SafetyConfig:
    sandbox_enabled: bool = True
    audit_log: bool = True
    audit_log_path: str = "./logs/audit.log"
    forbidden_commands: list = field(default_factory=list)
    forbidden_paths: list = field(default_factory=list)
    allowed_paths: list = field(default_factory=list)
    max_file_size_mb: int = 100


@dataclass
class ApiConfig:
    host: str = "0.0.0.0"
    port: int = 8080
    cors_origins: list = field(default_factory=lambda: ["*"])
    websocket_enabled: bool = True


@dataclass
class LoggingConfig:
    level: str = "INFO"
    file: str = "./logs/beru.log"
    max_size_mb: int = 50
    backup_count: int = 5
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


@dataclass
class Config:
    model: ModelConfig = field(default_factory=ModelConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    agents: Dict[str, AgentConfig] = field(default_factory=dict)
    workflows: WorkflowConfig = field(default_factory=WorkflowConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    api: ApiConfig = field(default_factory=ApiConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    @classmethod
    def from_yaml(cls, path: str = "config.yaml") -> Config:
        config_path = Path(path)
        if not config_path.exists():
            return cls()

        with open(config_path, "r") as f:
            data = yaml.safe_load(f) or {}

        config = cls()

        if "model" in data:
            config.model = ModelConfig(**data["model"])

        if "memory" in data:
            config.memory = MemoryConfig(**data["memory"])

        if "agents" in data:
            for name, agent_data in data["agents"].items():
                config.agents[name] = AgentConfig(
                    enabled=agent_data.get("enabled", True),
                    max_concurrent=agent_data.get("max_concurrent", 3),
                    tools=agent_data.get("tools", []),
                )

        if "workflows" in data:
            config.workflows = WorkflowConfig(**data["workflows"])

        if "safety" in data:
            config.safety = SafetyConfig(**data["safety"])

        if "api" in data:
            config.api = ApiConfig(**data["api"])

        if "logging" in data:
            config.logging = LoggingConfig(**data["logging"])

        return config

    def get_agent_config(self, name: str) -> AgentConfig:
        return self.agents.get(name, AgentConfig())


_config: Optional[Config] = None


def get_config() -> Config:
    global _config
    if _config is None:
        config_path = os.environ.get("BERU_CONFIG", "config.yaml")
        _config = Config.from_yaml(config_path)
    return _config


def reload_config(path: str = "config.yaml") -> Config:
    global _config
    _config = Config.from_yaml(path)
    return _config
