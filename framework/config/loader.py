"""File-system based configuration loading for the first release."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import (
    ConfigFileNotFoundError,
    ProfileNotSupportedError,
    SchemaValidationError,
)
from .models import BoardProfile, CaseSpec, FixtureSpec, GlobalConfig
from .validator import (
    validate_board_profile_data,
    validate_case_data,
    validate_fixture_data,
    validate_global_config_data,
)

_BUILTIN_GLOBAL_CONFIG: dict[str, Any] = {
    "product": {"default_board_profile": None},
    "runtime": {"default_timeout": 60, "default_retry": 0, "default_retry_interval": 0},
    "observability": {
        "report_enabled": True,
        "dashboard_enabled": False,
        "dashboard_auto_exit_on_success_seconds": 3,
        "dashboard_auto_exit_on_failure_seconds": None,
    },
}


class ConfigLoader:
    def __init__(self, workspace_root: str | Path) -> None:
        self.workspace_root = Path(workspace_root).resolve()

    def load_global_config(
        self, file_path: str | Path | None = None
    ) -> tuple[GlobalConfig, str]:
        if file_path is None:
            default_path = self.workspace_root / "config" / "global_config.json"
            if not default_path.exists():
                validate_global_config_data(
                    _BUILTIN_GLOBAL_CONFIG, source="<builtin:global_config>"
                )
                return GlobalConfig.from_dict(
                    _BUILTIN_GLOBAL_CONFIG
                ), "<builtin:global_config>"
            source_path = default_path
        else:
            source_path = self.resolve_path(file_path)

        raw = self._load_json(source_path)
        validate_global_config_data(raw, source=str(source_path))
        return GlobalConfig.from_dict(raw), str(source_path)

    def load_board_profile(
        self,
        *,
        profile_name: str | None = None,
        file_path: str | Path | None = None,
    ) -> tuple[BoardProfile, str]:
        if file_path is not None:
            source_path = self.resolve_path(file_path)
        else:
            if not profile_name:
                raise ProfileNotSupportedError(
                    "board profile is required", field_path="product.board_profile"
                )
            source_path = (
                self.workspace_root / "config" / "boards" / f"{profile_name}.json"
            )
            if not source_path.exists():
                raise ProfileNotSupportedError(
                    f"board profile '{profile_name}' does not exist",
                    field_path="product.board_profile",
                    source=str(source_path),
                )

        raw = self._load_json(source_path)
        validate_board_profile_data(raw, source=str(source_path))
        return BoardProfile.from_dict(raw), str(source_path)

    def load_case(
        self, file_path: str | Path, *, base_dir: str | Path | None = None
    ) -> tuple[CaseSpec, str]:
        source_path = self.resolve_path(file_path, base_dir=base_dir)
        raw = self._load_json(source_path)
        validate_case_data(raw, source=str(source_path))
        return CaseSpec.from_dict(raw), str(source_path)

    def load_fixture(
        self, file_path: str | Path, *, base_dir: str | Path | None = None
    ) -> tuple[FixtureSpec, str]:
        source_path = self.resolve_path(file_path, base_dir=base_dir)
        raw = self._load_json(source_path)
        validate_fixture_data(raw, source=str(source_path))
        return FixtureSpec.from_dict(raw), str(source_path)

    def resolve_path(
        self,
        file_path: str | Path,
        *,
        base_dir: str | Path | None = None,
    ) -> Path:
        candidate = Path(file_path)
        if candidate.is_absolute():
            if candidate.exists():
                return candidate.resolve()
            raise ConfigFileNotFoundError(
                "configuration file does not exist", source=str(candidate)
            )

        search_roots: list[Path] = []
        if base_dir is not None:
            search_roots.append(Path(base_dir).resolve())
        search_roots.append(self.workspace_root)

        seen: set[Path] = set()
        for root in search_roots:
            resolved = (root / candidate).resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            if resolved.exists():
                return resolved

        raise ConfigFileNotFoundError(
            "configuration file does not exist", source=str(candidate)
        )

    def _load_json(self, path: Path) -> dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise ConfigFileNotFoundError(
                "configuration file does not exist", source=str(path)
            ) from error
        except json.JSONDecodeError as error:
            raise SchemaValidationError(
                f"invalid JSON: {error.msg}",
                field_path=f"line {error.lineno} column {error.colno}",
                source=str(path),
            ) from error
