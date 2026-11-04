"""Extract an ordered terrain stack from a TUFLOW geometry control file."""

from dataclasses import dataclass
from pathlib import Path

from pytuflow import TGC

from .terrain import TerrainLayer


@dataclass(frozen=True, slots=True)
class TgcTerrainStack:
    """PyTUFLOW-derived terrain layers and unsupported active commands."""

    layers: tuple[TerrainLayer, ...]
    commands: tuple[str, ...]
    skipped_commands: tuple[str, ...]


def _active(
    scope_list: object, scenarios: tuple[str, ...], *, global_only: bool
) -> bool:
    """Return whether a PyTUFLOW scope is active for the requested scenarios."""
    scopes = tuple(scope_list)  # type: ignore[arg-type]
    if all(type(scope).__name__ == "GlobalScope" for scope in scopes):
        return True
    if global_only:
        return False
    for scope in scopes:
        if type(scope).__name__ == "GlobalScope":
            continue
        if type(scope).__name__ != "ScenarioScope":
            return False
        names = {str(name).casefold() for name in getattr(scope, "names", ())}
        matched = any(scenario.casefold() in names for scenario in scenarios)
        if bool(scope.is_neg()):
            matched = not matched
        if not matched:
            return False
    return True


def read_tgc_terrain_stack(
    tgc_path: Path,
    *,
    scenarios: tuple[str, ...] = (),
    global_only: bool = False,
) -> TgcTerrainStack:
    """Parse active ``Read Grid Zpts`` commands using PyTUFLOW.

    TUFLOW applies sequential elevation grids from low to high priority. The
    returned layers are reversed into the high-to-low order used by the
    initialiser's mosaic builder.
    """
    path = tgc_path.absolute()
    if not path.is_file():
        raise FileNotFoundError(path)
    if not scenarios and not global_only:
        msg = "Supply at least one scenario or select global-only TGC terrain"
        raise ValueError(msg)

    tgc = TGC(path)
    low_to_high: list[TerrainLayer] = []
    commands: list[str] = []
    skipped: list[str] = []
    for item in tgc.inputs:
        lhs = str(getattr(item, "lhs", "")).strip().lower()
        if lhs not in {"read grid zpts", "read gis zpts"}:
            continue
        if not _active(item.scope, scenarios, global_only=global_only):
            continue
        command = str(item)
        if lhs == "read gis zpts":
            skipped.append(command)
            continue
        files = tuple(Path(str(value)).absolute() for value in item.files)
        if not files:
            skipped.append(command)
            continue
        if len(files) > 2:
            msg = (
                f"Unsupported Read Grid Zpts command with more than one clip: {command}"
            )
            raise ValueError(msg)
        low_to_high.append(
            TerrainLayer(files[0], files[1] if len(files) == 2 else None)
        )
        commands.append(command)
    if not low_to_high:
        msg = f"No active Read Grid Zpts commands found in {path}"
        raise ValueError(msg)
    return TgcTerrainStack(
        tuple(reversed(low_to_high)), tuple(reversed(commands)), tuple(skipped)
    )
