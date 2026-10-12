"""Tests for AOI entry identity, connected LFPs and cumulative-area semantics."""

from pathlib import Path

import fiona
import numpy as np
import pytest
from numpy.typing import NDArray
from rasterio.crs import CRS
from rasterio.transform import from_origin
from shapely.geometry import box
from shapely.geometry.base import BaseGeometry

from tuflow_initialiser.catchment_outputs import write_inflow_products, write_inflow_summary
from tuflow_initialiser.catchments import delineate_inflows


def _base() -> tuple[NDArray[np.int16], NDArray[np.float64]]:
    directions = np.zeros((11, 11), dtype=np.int16)
    elevations = np.zeros((11, 11), dtype=np.float64)
    for row in range(11):
        elevations[row, :] = 20.0 - row
    return directions, elevations


def _aoi_cell(row: int, col: int) -> BaseGeometry:
    # Grid origin (0, 11), positive northing increasing upwards.
    return box(col + 0.15, 11 - row - 0.85, col + 0.85, 11 - row - 0.15)


def test_two_inflows_to_one_aoi_are_not_combined(tmp_path: Path) -> None:
    directions, elevations = _base()
    directions[2:6, 2] = 6
    directions[2:6, 7] = 6
    aoi = box(1.2, 4.2, 7.9, 4.8)  # row 6, two entry edges
    transform = from_origin(0, 11, 1, 1)
    catchments = delineate_inflows(directions, elevations, [aoi], transform=transform)
    assert len(catchments) == 2
    assert {item.inlet for item in catchments} == {(5, 2), (5, 7)}
    assert {item.aoi_id for item in catchments} == {1}
    assert {item.catchment_id for item in catchments} == {1, 2}
    assert all(item.local_area_m2 == pytest.approx(4.0) for item in catchments)
    assert sum(item.local_area_m2 for item in catchments) == pytest.approx(8.0)
    assert catchments[0].polygon.intersection(catchments[1].polygon).area == 0
    assert all(item.length_m == pytest.approx(4.0) for item in catchments)
    assert all(item.slope_ea == pytest.approx(1) for item in catchments)
    gpkg = tmp_path / "catchments.gpkg"
    write_inflow_products(
        gpkg, aois=[aoi], inflows=catchments, transform=transform, crs_wkt=CRS.from_epsg(28350).to_wkt()
    )
    assert set(fiona.listlayers(gpkg)) == {"aoi_inputs", "aoi_inflow_catchments", "longest_flow_paths"}
    with fiona.open(gpkg, layer="longest_flow_paths") as lines:
        records = list(lines)
        assert len(records) == 2
        assert all(feature.properties["origin"] == "inferred_D8" for feature in records)
    summary = tmp_path / "summary.json"
    write_inflow_summary(summary, catchments)
    assert '"cumulative_areas_may_overlap_between_aois": true' in summary.read_text(encoding="utf-8")


def test_maximum_geometric_length_not_tributary_size() -> None:
    directions, elevations = _base()
    directions[3:8, 5] = 6
    directions[7, 4] = 8
    directions[7, 3] = 8
    directions[6, 2] = 7
    directions[8, 2] = 1
    catchments = delineate_inflows(directions, elevations, [_aoi_cell(8, 5)], transform=from_origin(0, 11, 1, 1))
    assert len(catchments) == 1
    assert catchments[0].path[0] == (3, 5)
    assert catchments[0].path[-1] == (8, 5)
    assert catchments[0].length_m == pytest.approx(5.0)
    assert catchments[0].source_elevation_m == pytest.approx(17.0)
    assert catchments[0].outlet_elevation_m == pytest.approx(12.0)


def test_distinct_aois_and_nested_cumulative_areas() -> None:
    directions, elevations = _base()
    directions[2:9, 4] = 6
    upstream = _aoi_cell(5, 4)
    downstream = _aoi_cell(9, 4)
    catchments = delineate_inflows(directions, elevations, [upstream, downstream], transform=from_origin(0, 11, 1, 1))
    assert len(catchments) == 2
    assert catchments[0].aoi_id == 1
    assert catchments[1].aoi_id == 2
    assert catchments[1].aoi_cumulative_area_m2 > catchments[0].aoi_cumulative_area_m2
    assert catchments[1].local_area_m2 > catchments[0].local_area_m2
    # Same source contributes to both AOIs (cumulative totals may overlap).
    assert catchments[0].path[0] == catchments[1].path[0] == (2, 4)


def test_excluded_entry_is_retained_but_no_incomplete_lfp() -> None:
    directions, elevations = _base()
    directions[3:8, 5] = 6
    selected = np.ones_like(directions, dtype=bool)
    selected[5, 5] = False
    inflows = delineate_inflows(
        directions, elevations, [_aoi_cell(8, 5)], transform=from_origin(0, 11, 1, 1), analyse_cells=selected
    )
    assert len(inflows) == 1
    assert inflows[0].local_area_m2 == pytest.approx(5.0)
    assert inflows[0].status == "excluded_from_detailed_analysis"
    assert not inflows[0].path
    assert inflows[0].length_m is None
    complete = delineate_inflows(directions, elevations, [_aoi_cell(8, 5)], transform=from_origin(0, 11, 1, 1))
    assert complete[0].status == "complete"
    assert complete[0].length_m == pytest.approx(5.0)


def test_longest_path_preserves_signed_negative_slope() -> None:
    directions, elevations = _base()
    directions[3:8, 5] = 6
    elevations[3:9, 5] = np.arange(6.0)
    result = delineate_inflows(directions, elevations, [_aoi_cell(8, 5)], transform=from_origin(0, 11, 1, 1))
    assert result[0].slope_ea == pytest.approx(-1)


def test_multiple_disconnected_aois_keep_separate_ids() -> None:
    directions, elevations = _base()
    directions[3:7, 2] = 6
    directions[2:7, 8] = 6
    result = delineate_inflows(
        directions, elevations, [_aoi_cell(7, 2), _aoi_cell(7, 8)], transform=from_origin(0, 11, 1, 1)
    )
    assert len(result) == 2
    assert [x.aoi_id for x in result] == [1, 2]
    assert [x.catchment_id for x in result] == [1, 2]
    assert [x.local_area_m2 for x in result] == [4.0, 5.0]
