from dataclasses import dataclass, field
from typing import Any

from .storage import AppPaths, Database


@dataclass
class Services:
    paths: AppPaths
    db: Database
    registry: dict[str, Any] = field(default_factory=dict)
    capabilities: dict[str, dict] = field(default_factory=dict)
    on_startup: list = field(default_factory=list)
    on_shutdown: list = field(default_factory=list)

    def get(self, name: str):
        from .contracts import ApiError
        if name not in self.registry:
            raise ApiError("capability_unavailable", f"{name.capitalize()} is not ready", 503, True)
        return self.registry[name]
