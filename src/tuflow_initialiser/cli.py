"""Standalone command-line entry point."""

import argparse
from pathlib import Path

from .project_setup import TuflowProjectConfig, initialize_tuflow_project


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Generate standalone TUFLOW project setup and hydrology")
    commands = p.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Create project directories and canonical TUFLOW empty GIS")
    init.add_argument("--output", required=True, type=Path)
    init.add_argument("--name", required=True)
    init.add_argument("--scenario", required=True)
    init.add_argument("--prj", required=True, type=Path)
    init.add_argument("--tuflow-exe", required=True, type=Path)
    init.add_argument("--ryan-tools-scripts", type=Path, default=None, help="Optional utility source root")
    init.add_argument("--overwrite", action="store_true")
    return p


def main() -> int:
    args = _parser().parse_args()
    if args.command == "init":
        templates_dir = Path(__file__).resolve().parent / "resources" / "tuflow_templates"
        initialize_tuflow_project(
            TuflowProjectConfig(
                output_dir=args.output,
                project_name=args.name,
                scenario_name=args.scenario,
                prj_file=args.prj,
                tuflow_executable=args.tuflow_exe,
                templates_dir=templates_dir,
                copy_utilities=args.ryan_tools_scripts is not None,
                utility_source_root=args.ryan_tools_scripts,
                overwrite=args.overwrite,
            )
        )
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
