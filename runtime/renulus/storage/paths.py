"""All writable engine and application paths descend from one explicit profile."""
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppPaths:
    root: Path
    source_root: Path

    @classmethod
    def create(cls, root: str | Path, source_root: str | Path | None = None) -> "AppPaths":
        target = Path(root).expanduser().resolve()
        source = Path(source_root).resolve() if source_root else Path(__file__).parents[3]
        result = cls(target, source)
        for name in ("state", "library", "indexes", "cache", "helpers"):
            (target / name).mkdir(parents=True, exist_ok=True)
        return result

    @property
    def state(self) -> Path:
        return self.root / "state"

    @property
    def library(self) -> Path:
        return self.root / "library"

    @property
    def indexes(self) -> Path:
        return self.root / "indexes"

    @property
    def cache(self) -> Path:
        return self.root / "cache"

    @property
    def helpers(self) -> Path:
        return self.root / "helpers"

    @property
    def database(self) -> Path:
        return self.state / "renulus.sqlite3"

    def owned(self, relative: str) -> Path:
        candidate = (self.root / relative).resolve()
        if not candidate.is_relative_to(self.root):
            raise ValueError("Path leaves the app profile")
        return candidate
