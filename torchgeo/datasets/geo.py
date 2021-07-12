import abc
from typing import Any, Dict, Iterable

from rtree.index import Index, Property
from torch.utils.data import Dataset

from .utils import BoundingBox

# https://github.com/pytorch/pytorch/issues/60979
# https://github.com/pytorch/pytorch/pull/61045
Dataset.__module__ = "torch.utils.data"


class GeoDataset(Dataset[Dict[str, Any]], abc.ABC):
    """Abstract base class for datasets containing geospatial information.

    Geospatial information includes things like:

    * latitude, longitude
    * time
    * :term:`coordinate reference system (CRS)`

    These kind of datasets are special because they can be combined. For example:

    * Combine Landsat8 and CDL to train a model for crop classification
    * Combine Sentinel2 and Chesapeake to train a model for land cover mapping

    This isn't true for :class:`VisionDataset`, where the lack of geospatial information
    prohibits swapping image sources or target labels.
    """

    #: R-tree to index geospatial data. Subclasses must insert data into this index in
    #: order for the sampler to index it properly.
    index = Index(properties=Property(dimension=3, interleaved=False))

    @abc.abstractmethod
    def __getitem__(self, query: BoundingBox) -> Dict[str, Any]:
        """Retrieve image and metadata indexed by query.

        Parameters:
            query: (minx, maxx, miny, maxy, mint, maxt) coordinates to index

        Returns:
            sample of data/labels and metadata at that index
        """

    def __add__(self, other: "GeoDataset") -> "ZipDataset":  # type: ignore[override]
        """Merge two GeoDatasets.

        Parameters:
            other: another dataset

        Returns:
            a single dataset
        """
        return ZipDataset([self, other])

    def __str__(self) -> str:
        """Return the informal string representation of the object.

        Returns:
            informal string representation
        """
        return f"""\
{self.__class__.__name__} Dataset
    type: GeoDataset"""


@property
def bounds(self) -> BoundingBox:
    """Bounds of the index.

    Returns:
        (minx, maxx, miny, maxy, mint, maxt) of the dataset
    """
    return self.index.bounds


class VisionDataset(Dataset[Dict[str, Any]], abc.ABC):
    """Abstract base class for datasets lacking geospatial information.

    This base class is designed for datasets with pre-defined image chips.
    """

    @abc.abstractmethod
    def __getitem__(self, index: int) -> Dict[str, Any]:
        """Return an index within the dataset.

        Parameters:
            index: index to return

        Returns:
            data and labels at that index
        """

    @abc.abstractmethod
    def __len__(self) -> int:
        """Return the length of the dataset.

        Returns:
            length of the dataset
        """

    def __str__(self) -> str:
        """Return the informal string representation of the object.

        Returns:
            informal string representation
        """
        return f"""\
{self.__class__.__name__} Dataset
    type: VisionDataset
    size: {len(self)}"""


class ZipDataset(GeoDataset):
    """Dataset for merging two or more GeoDatasets.

    For example, this allows you to combine an image source like Landsat8 with a target
    label like CDL.
    """

    def __init__(self, datasets: Iterable[GeoDataset]) -> None:
        """Initialize a new Dataset instance.

        Parameters:
            datasets: list of datasets to merge
        """
        for ds in datasets:
            assert isinstance(ds, GeoDataset), "ZipDataset only supports GeoDatasets"

        self.datasets = datasets

    def __getitem__(self, query: BoundingBox) -> Dict[str, Any]:
        """Retrieve image and metadata indexed by query.

        Parameters:
            query: (minx, maxx, miny, maxy, mint, maxt) coordinates to index

        Returns:
            sample of data/labels and metadata at that index
        """
        sample = {}
        for ds in self.datasets:
            sample.update(ds[query])
        return sample

    def __str__(self) -> str:
        """Return the informal string representation of the object.

        Returns:
            informal string representation
        """
        return f"""\
{self.__class__.__name__} Dataset
    type: ZipDataset"""

    @property
    def bounds(self) -> BoundingBox:
        """Bounds of the index.

        Returns:
            (minx, maxx, miny, maxy, mint, maxt) of the dataset
        """
        # We want to compute the intersection of all dataset bounds, not the union
        minx = max([ds.index.bounds[0] for ds in self.datasets])
        maxx = min([ds.index.bounds[1] for ds in self.datasets])
        miny = max([ds.index.bounds[2] for ds in self.datasets])
        maxy = min([ds.index.bounds[3] for ds in self.datasets])
        mint = max([ds.index.bounds[4] for ds in self.datasets])
        maxt = min([ds.index.bounds[5] for ds in self.datasets])

        return BoundingBox(minx, maxx, miny, maxy, mint, maxt)
