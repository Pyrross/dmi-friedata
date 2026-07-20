from __future__ import annotations

from typing import Any

from .http import DMIHTTPClient
from .models import FeatureCollection
from .query import ForecastQuery, RadarQuery


class BaseService:
    def __init__(self, http_client: DMIHTTPClient, prefix: str) -> None:
        self._http = http_client
        self._prefix = prefix

    def _clean_params(self, params: dict[str, Any] | None) -> dict[str, Any] | None:
        if params is None:
            return None
        return {key: value for key, value in params.items() if value is not None}

    def _get(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._http.get(f"{self._prefix}/{path.lstrip('/')}", params=self._clean_params(params))


class RadarService(BaseService):
    """Service helper for the STAC-style radar data API."""

    def list_collections(self) -> dict[str, Any]:
        return self._get("collections")

    def query(self, query: RadarQuery) -> FeatureCollection:
        payload = self._get(query.path(), params=query.as_params())
        return FeatureCollection.from_payload(payload)

    def list_items(self, *, collection: str, limit: int = 1000, **params: Any) -> FeatureCollection:
        payload = self._get(
            f"collections/{collection}/items",
            params={"limit": limit, **params},
        )
        return FeatureCollection.from_payload(payload)

    def list_station_items(self, *, station_id: str | None = None, **params: Any) -> FeatureCollection:
        return self.list_items(collection="volume", stationId=station_id, **params)

    def download(self, filename: str, *, destination: str) -> str:
        return self._http.download(f"{self._prefix}/download/{filename}", destination=destination)


class ForecastSTACService(BaseService):
    """Service helper for the STAC-style forecast download API."""

    def list_collections(self) -> dict[str, Any]:
        return self._get("collections")

    def list_items(self, *, collection: str, limit: int = 1000, **params: Any) -> FeatureCollection:
        payload = self._get(
            f"collections/{collection}/items",
            params={"limit": limit, **params},
        )
        return FeatureCollection.from_payload(payload)

    def list_latest_items(self, *, collection: str, limit: int = 10, **params: Any) -> FeatureCollection:
        return self.list_items(collection=collection, limit=limit, sortorder="datetime,DESC", **params)

    def download(self, filename: str, *, destination: str) -> str:
        return self._http.download(f"{self._prefix}/download/{filename}", destination=destination)


class ForecastEDRService(BaseService):
    """Service helper for the EDR-style forecast data API."""

    def list_collections(self) -> dict[str, Any]:
        return self._get("collections")

    def get_collection(self, collection: str) -> dict[str, Any]:
        return self._get(f"collections/{collection}")

    def list_instances(self, collection: str) -> dict[str, Any]:
        return self._get(f"collections/{collection}/instances")

    def get_instance(self, collection: str, instance_id: str) -> dict[str, Any]:
        return self._get(f"collections/{collection}/instances/{instance_id}")

    def query(self, query: ForecastQuery) -> dict[str, Any]:
        endpoint = query.path(endpoint="position")
        return self._get(endpoint, params=query.as_params())

    def position(
        self,
        *,
        collection: str,
        coords: str,
        parameter_name: str,
        **params: Any,
    ) -> dict[str, Any]:
        return self._get(
            f"collections/{collection}/position",
            params={"coords": coords, "parameter-name": parameter_name, **params},
        )

    def cube(
        self,
        *,
        collection: str,
        bbox: str,
        parameter_name: str,
        **params: Any,
    ) -> dict[str, Any]:
        return self._get(
            f"collections/{collection}/cube",
            params={"bbox": bbox, "parameter-name": parameter_name, **params},
        )

    def bbox(
        self,
        *,
        collection: str,
        bbox: str,
        parameter_name: str,
        **params: Any,
    ) -> dict[str, Any]:
        return self._get(
            f"collections/{collection}/bbox",
            params={"bbox": bbox, "parameter-name": parameter_name, **params},
        )

    def grib(self, *, collection: str, parameter_name: str, **params: Any) -> dict[str, Any]:
        return self._get(
            f"collections/{collection}/grib",
            params={"parameter-name": parameter_name, **params},
        )


class LightningService(BaseService):
    """Service helper for the Lightning API."""

    def list_collections(self) -> dict[str, Any]:
        return self._get("collections")

    def list_items(self, *, collection: str, limit: int = 1000, **params: Any) -> FeatureCollection:
        payload = self._get(f"collections/{collection}/items", params={"limit": limit, **params})
        return FeatureCollection.from_payload(payload)


class ObservationService(BaseService):
    """Service helper for the JSON OGC Features observation APIs."""

    def list_collections(self) -> dict[str, Any]:
        return self._get("collections")

    def list_items(self, *, collection: str, limit: int = 1000, **params: Any) -> FeatureCollection:
        payload = self._get(f"collections/{collection}/items", params={"limit": limit, **params})
        return FeatureCollection.from_payload(payload)


class ClimateService(BaseService):
    """Service helper for the climate API."""

    def list_collections(self) -> dict[str, Any]:
        return self._get("collections")

    def list_items(self, *, collection: str, limit: int = 1000, **params: Any) -> FeatureCollection:
        payload = self._get(f"collections/{collection}/items", params={"limit": limit, **params})
        return FeatureCollection.from_payload(payload)
