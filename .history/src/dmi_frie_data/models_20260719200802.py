from __future__ import annotations

from io import BytesIO
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np

try:
    import h5py
except ImportError:  # pragma: no cover - optional dependency for HDF5 workflows
    h5py = None

if TYPE_CHECKING:
    from .http import DMIHTTPClient


@dataclass
class Link:
    href: str
    rel: str
    type: str | None = None
    title: str | None = None


@dataclass
class Asset:
    href: str
    title: str | None = None
    type: str | None = None
    roles: list[str] = field(default_factory=list)


@dataclass
class Feature:
    id: str
    type: str = "Feature"
    geometry: dict[str, Any] | None = None
    properties: dict[str, Any] = field(default_factory=dict)
    collection: str | None = None
    assets: dict[str, Asset] = field(default_factory=dict)
    bbox: list[float] | None = None
    stac_version: str | None = None

    def get_asset(self, name: str) -> Asset | None:
        return self.assets.get(name)

    def get_asset_url(self, name: str) -> str | None:
        asset = self.get_asset(name)
        if asset is None:
            return None
        return asset.href

    def download_asset(self, name: str, *, http_client: "DMIHTTPClient", destination: str) -> str:
        asset = self.get_asset(name)
        if asset is None:
            raise KeyError(f"Asset '{name}' is not present on this feature")
        return http_client.download(asset.href, destination=destination)

    def _get_data_asset(self) -> Asset | None:
        return self.get_asset("data") or self.get_asset("x-hdf5")

    def load_hdf5(
        self,
        path: str | None = None,
        *,
        http_client: "DMIHTTPClient | None" = None,
    ):
        if h5py is None:
            raise ImportError("h5py is required to load the native HDF5 asset")

        asset_path = path
        if asset_path is None:
            asset = self._get_data_asset()
            if asset is None:
                raise KeyError("This feature does not expose a radar data asset")
            asset_path = asset.href

        if asset_path.startswith(("http://", "https://")):
            if http_client is None:
                raise ValueError("An http_client is required when the HDF5 asset is remote")
            content = http_client.get_bytes(asset_path)
            return h5py.File(BytesIO(content), "r")

        return h5py.File(asset_path, "r")

    def as_array(
        self,
        *,
        path: str | None = None,
        dataset_name: str | None = None,
        http_client: "DMIHTTPClient | None" = None,
    ) -> np.ndarray:
        if h5py is None:
            raise ImportError("h5py is required to load the native HDF5 array")

        dataset_path = dataset_name or "dataset1/data1/data"
        with self.load_hdf5(path=path, http_client=http_client) as handle:
            dataset = handle.get(dataset_path)
            if dataset is None:
                candidates = ["data", "dataset1/data1/data", "dataset1/data1/values"]
                for candidate in candidates:
                    if candidate in handle:
                        dataset = handle[candidate]
                        break
                if dataset is None:
                    raise KeyError(f"Dataset '{dataset_path}' is not available in the HDF5 file")

            array = np.asarray(dataset)
            if array.ndim != 2:
                raise ValueError("Only 2D array datasets can be represented as a native radar array")
            return array

    def to_geojson(
        self,
        *,
        path: str | None = None,
        dataset_name: str | None = None,
        http_client: "DMIHTTPClient | None" = None,
        array: np.ndarray | None = None,
    ) -> dict[str, Any]:
        if self.bbox is None or len(self.bbox) != 4:
            raise ValueError("A feature bbox is required to fit the HDF5 array into GeoJSON coordinates")

        if array is None:
            array = self.as_array(path=path, dataset_name=dataset_name, http_client=http_client)

        if array.ndim != 2:
            raise ValueError("Only 2D array datasets can be converted into radar GeoJSON polygons")

        min_x, min_y, max_x, max_y = self.bbox
        x_edges = np.linspace(min_x, max_x, num=array.shape[1] + 1, dtype=float)
        y_edges = np.linspace(max_y, min_y, num=array.shape[0] + 1, dtype=float)

        features = []
        for row_index in range(array.shape[0]):
            y_top = float(y_edges[row_index])
            y_bottom = float(y_edges[row_index + 1])
            for col_index in range(array.shape[1]):
                if np.isnan(array[row_index, col_index]):
                    continue
                x_left = float(x_edges[col_index])
                x_right = float(x_edges[col_index + 1])
                features.append(
                    {
                        "type": "Feature",
                        "id": f"{self.id}-{row_index}-{col_index}",
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [
                                    [x_left, y_top],
                                    [x_right, y_top],
                                    [x_right, y_bottom],
                                    [x_left, y_bottom],
                                    [x_left, y_top],
                                ]
                            ],
                        },
                        "properties": {
                            "value": float(array[row_index, col_index]),
                            "datetime": self.properties.get("datetime")
                        },
                    }
                )

        return {
            "type": "FeatureCollection",
            "features": features,
            "bbox": [min_x, min_y, max_x, max_y],
        }

    @property
    def download_url(self) -> str | None:
        return self.get_asset_url("data")

    @property
    def data_asset(self) -> Asset | None:
        return self._get_data_asset()

    @property
    def data_url(self) -> str | None:
        return self.get_asset_url("data")

    @property
    def x_hdf5_asset(self) -> Asset | None:
        return self.get_asset("x-hdf5") or self._get_data_asset()

    @property
    def x_hdf5_url(self) -> str | None:
        if self.x_hdf5_asset is None:
            return None
        return self.x_hdf5_asset.href

    @property
    def hdf5_asset(self) -> Asset | None:
        return self.data_asset


@dataclass
class FeatureCollection:
    type: str = "FeatureCollection"
    features: list[Feature] = field(default_factory=list)
    timestamp: str | None = None
    number_returned: int | None = None
    links: list[Link] = field(default_factory=list)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "FeatureCollection":
        features = []
        for raw_feature in payload.get("features", []):
            assets_payload = raw_feature.get("assets") or {}
            if not assets_payload and "asset" in raw_feature:
                assets_payload = raw_feature.get("asset")

            assets = {
                name: Asset(
                    href=asset.get("href", ""),
                    title=asset.get("title"),
                    type=asset.get("type"),
                    roles=asset.get("roles", []),
                )
                for name, asset in assets_payload.items()
            }
            features.append(
                Feature(
                    id=raw_feature.get("id", ""),
                    type=raw_feature.get("type", "Feature"),
                    geometry=raw_feature.get("geometry"),
                    properties=raw_feature.get("properties", {}),
                    collection=raw_feature.get("collection"),
                    assets=assets,
                    bbox=raw_feature.get("bbox"),
                    stac_version=raw_feature.get("stac_version"),
                )
            )

        return cls(
            type=payload.get("type", "FeatureCollection"),
            features=features,
            timestamp=payload.get("timeStamp"),
            number_returned=payload.get("numberReturned"),
            links=[
                Link(
                    href=link.get("href", ""),
                    rel=link.get("rel", ""),
                    type=link.get("type"),
                    title=link.get("title"),
                )
                for link in payload.get("links", [])
            ],
        )
