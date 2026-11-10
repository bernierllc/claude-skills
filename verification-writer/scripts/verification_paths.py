"""Resolve the project's shared verification resource location."""
import json
from pathlib import Path


def verification_directory(repo_root: Path) -> Path:
    config = repo_root / ".aec" / "directories.json"
    settings = json.loads(config.read_text()) if config.exists() else {}
    value = settings.get("verification", "docs/verification")
    if not isinstance(value, str):
        raise ValueError("verification directory must be a string")
    path = repo_root / value
    if Path(value).is_absolute() or not path.resolve().is_relative_to(repo_root.resolve()):
        raise ValueError("verification directory must be inside the repository")
    return path
