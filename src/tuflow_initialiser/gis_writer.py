"""Canonical-schema TUFLOW GIS and analysis GeoPackage writers."""

from pathlib import Path

import fiona
from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from .geometry import Domain


def _parts(geometry: BaseGeometry) -> list[BaseGeometry]:
    if geometry.geom_type == "Polygon":
        return [geometry]
    if geometry.geom_type == "MultiPolygon":
        return list(geometry.geoms)
    raise ValueError(f"Unsupported model polygon geometry: {geometry.geom_type}")


def _write_features(target: Path, geom: BaseGeometry, properties: dict[str, float | int | str]) -> None:
    """Append to scenario GIS created from canonical TUFLOW empties."""
    if not target.is_file():
        raise FileNotFoundError(f"Missing canonical working TUFLOW layer: {target}")
    with fiona.open(target, mode="a") as collection:
        if collection.schema["geometry"] != "Polygon":
            raise ValueError(f"Expected Polygon layer: {target}")
        schema = collection.schema["properties"]
        unknown = set(properties) - set(schema)
        if unknown:
            raise ValueError(f"TUFLOW empty schema lacks required attributes: {unknown}")
        for polygon in _parts(geom):
            if polygon.is_empty or not polygon.is_valid or polygon.area <= 0:
                raise ValueError("Invalid output polygon")
            values = dict.fromkeys(schema)
            values.update(properties)
            collection.write({"geometry": mapping(polygon), "properties": values})
    with fiona.open(target) as collection:
        features = list(collection)
        if not features:
            raise ValueError(f"Writing to {target} produced an empty layer")
        actual = unary_union([__shape_feature(f) for f in features])
        if not actual.equals(geom):
            raise ValueError(f"Written geometry differs from requested geometry: {target}")


def __shape_feature(feature: fiona.model.Feature) -> BaseGeometry:
    from shapely.geometry import shape

    return shape(feature.geometry)


def write_tuflow_layers(
    project_dir: Path, *, scenario: str, domain: Domain, rainfall_name: str
) -> dict[str, Path]:
    """Populate canonical code/rainfall/location layers, with geometry checks."""
    if not rainfall_name or not rainfall_name.strip():
        raise ValueError("Nonempty rainfall name required")
    directory = project_dir / "model" / "gis" / scenario
    paths = {
        name: directory / f"{name}_{scenario}_01_R.gpkg" for name in ("2d_code", "2d_rf", "2d_loc")
    }
    _write_features(paths["2d_code"], domain.active, {"Code": 1})
    with fiona.open(paths["2d_rf"]) as rainfall_layer:
        rf_fields = rainfall_layer.schema["properties"]
        attributes: dict[str, float | int | str] = {"Name": rainfall_name, "f1": 1.0}
        if "f2" in rf_fields:
            attributes["f2"] = 1.0
    _write_features(paths["2d_rf"], domain.active, attributes)
    _write_features(paths["2d_loc"], domain.location, {})
    return paths


def write_analysis(
    path: Path, *, domain: Domain, crs_wkt: str,
    analyse_exclusions: bool = False,
) -> None:
    """Write plain analysis geometries separate from canonical TUFLOW GIS."""
    outputs = {
        "aoi": domain.aoi,
        "contributing_area": domain.contributing,
        "aoi_buffer": domain.buffer,
        "active_extent": domain.active,
        "detailed_analysis_extent": (
            domain.contributing
            if analyse_exclusions or domain.excluded_area is None
            else domain.contributing.difference(domain.excluded_area)
        ),
    }
    if domain.exclusions is not None:
        outputs["exclusions_supplied"] = domain.exclusions
    if domain.excluded_area is not None:
        outputs["exclusions_applied"] = domain.excluded_area
        if not analyse_exclusions:
            outputs["exclusions_analysis_skipped"] = domain.excluded_area
    for name, geom in outputs.items():
        with fiona.open(
            path, mode="w",
            driver="GPKG", layer=name,
            schema={"geometry": "MultiPolygon", "properties": {"area_km2": "float"}},
            crs_wkt=crs_wkt,
        ) as dst:
            from shapely.geometry import MultiPolygon

            polygons = _parts(geom)
            dst.write({
                "geometry": mapping(MultiPolygon(polygons)),
                "properties": {"area_km2": geom.area / 1_000_000.0},
            })
