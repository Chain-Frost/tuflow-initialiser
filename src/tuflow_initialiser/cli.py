"""Standalone command-line interface; hydrology GUI is not required."""

import argparse
from pathlib import Path

from .project_setup import TuflowProjectConfig, initialize_tuflow_project
from .workflow import BuildConfig, build


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Initialise standalone 2D ROG TUFLOW models")
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="Create empty TUFLOW project from canonical templates")
    init.add_argument("--output", required=True, type=Path)
    init.add_argument("--name", required=True)
    init.add_argument("--scenario", required=True)
    init.add_argument("--prj", required=True, type=Path)
    init.add_argument("--tuflow-exe", required=True, type=Path)
    init.add_argument("--ryan-tools-scripts", type=Path, default=None)
    init.add_argument("--overwrite", action="store_true")

    make = commands.add_parser("build", help="Build project from DEM/AOI via GRASS and canonical TUFLOW GIS")
    make.add_argument("--dem", required=True, type=Path)
    make.add_argument("--aoi", required=True, type=Path, help="Vector AOI, in DEM CRS")
    make.add_argument("--output", required=True, type=Path)
    make.add_argument("--name", required=True)
    make.add_argument("--scenario", required=True)
    make.add_argument("--prj", required=True, type=Path)
    make.add_argument("--tuflow-exe", required=True, type=Path)
    make.add_argument("--grass-exe", default="grass")
    make.add_argument("--buffer-m", type=float, default=500)
    make.add_argument("--stream-area-m2", type=float, default=100000)
    make.add_argument("--rainfall-name", required=True)
    make.add_argument("--fill-depressions", action="store_true")
    make.add_argument("--max-fill-depth-m", type=float, default=2)
    make.add_argument("--ryan-tools-scripts", type=Path, default=None)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.command == "init":
        initialize_tuflow_project(
            TuflowProjectConfig(
                output_dir=args.output,
                project_name=args.name,
                scenario_name=args.scenario,
                prj_file=args.prj,
                tuflow_executable=args.tuflow_exe,
                templates_dir=Path(__file__).resolve().parent / "resources" / "tuflow_templates",
                copy_utilities=args.ryan_tools_scripts is not None,
                utility_source_root=args.ryan_tools_scripts,
                overwrite=args.overwrite,
            )
        )
    elif args.command == "build":
        build(
            BuildConfig(
                dem=args.dem, aoi=args.aoi, output=args.output,
                name=args.name, scenario=args.scenario,
                prj=args.prj, tuflow_executable=args.tuflow_exe,
                rainfall_name=args.rainfall_name,
                grass_executable=args.grass_exe,
                buffer_m=args.buffer_m,
                stream_threshold_m2=args.stream_area_m2,
                fill_depressions=args.fill_depressions,
                max_fill_depth_m=args.max_fill_depth_m,
                utility_source_root=args.ryan_tools_scripts,
            )
        )
    else:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
