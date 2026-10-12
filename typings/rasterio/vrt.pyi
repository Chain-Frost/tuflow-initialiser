from affine import Affine

from .crs import CRS
from .enums import Resampling
from .io import DatasetReader

class WarpedVRT(DatasetReader):
    def __init__(
        self,
        src_dataset: DatasetReader,
        *,
        crs: CRS,
        transform: Affine = ...,
        width: int = ...,
        height: int = ...,
        resampling: Resampling = ...,
        add_alpha: bool = ...,
        nodata: float = ...,
    ) -> None: ...
