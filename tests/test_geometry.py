"""AOI union/circular-buffer behaviour and cardinal location tests."""

import numpy as np
import pytest
from affine import Affine
from shapely.geometry import box

from tuflow_initialiser.geometry import make_domain, mask_to_polygon


def test_mask_vectorisation():
    mask = np.zeros((4, 4), dtype=bool)
    mask[1, 1] = True
    polygon = mask_to_polygon(mask, Affine.translation(0, 4) @ Affine.scale(1, -1))
    assert polygon.area == pytest.approx(1.0)


def test_buffer_requires_terrain_coverage():
    directions = np.full((8, 8), 6, dtype=np.int16)
    directions[0, :] = 0
    directions[:, 0] = 0
    with pytest.raises(ValueError, match="buffer"):
        make_domain(
            directions,
            aoi=box(3, 3, 4, 4),
            transform=Affine.translation(0, 8) @ Affine.scale(1, -1),
            raster_bounds=(0, 0, 8, 8),
            buffer_m=500,
        )
