from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any


@dataclass
class ForecastQuery:
    """A small Pythonic helper for building EDR forecast requests.

    The class keeps the public API easy to read while translating the more
    verbose DMI parameter names into the exact query keys required by the
    EDR endpoint.
    """

    collection: str
    parameter_name: str | None = None
    coords: str | None = None
    bbox: str | None = None
    crs: str | None = None
    datetime: str | None = None
    f: str | None = None
    instance_id: str | None = None
    extra_params: dict[str, Any] = field(default_factory=dict)

    def as_params(self) -> dict[str, Any]:
        params: dict[str, Any] = {}

        if self.coords is not None:
            params["coords"] = self.coords
        if self.bbox is not None:
            params["bbox"] = self.bbox
        if self.parameter_name is not None:
            params["parameter-name"] = self.parameter_name
        if self.datetime is not None:
            params["datetime"] = self.datetime
        if self.crs is not None:
            params["crs"] = self.crs
        if self.f is not None:
            params["f"] = self.f

        params.update(self.extra_params)
        return params

    def path(self, *, endpoint: str = "position") -> str:
        collection = self.collection
        if self.instance_id:
            return f"collections/{collection}/instances/{self.instance_id}/{endpoint}"
        return f"collections/{collection}/{endpoint}"


@dataclass
class RadarQuery:
    """Small Pythonic helper for radar item filtering.

    The query model intentionally focuses on the DMI radar API shape,
    including the pagination parameters that are needed to page through
    large radar archives with a predictable offset-based flow.
    """

    collection: str
    station_id: str | None = None
    scan_type: str | None = None
    datetime: str | None = None
    period: str | None = None
    reference_time: str | None = None
    bbox: str | None = None
    bbox_crs: str | None = None
    limit: int | None = None
    offset: int | None = None
    sortorder: str | None = None
    extra_params: dict[str, Any] = field(default_factory=dict)

    _allowed_scan_types = {"fullRange", "doppler"}
    _station_id_collections = {"volume", "pseudoCappi"}
    _allowed_collections = {"volume", "pseudoCappi", "composite"}

    @staticmethod
    def _parse_isotime(value: str) -> datetime:
        timestamp = value.strip()
        if timestamp.endswith("Z"):
            timestamp = timestamp[:-1] + "+00:00"
        return datetime.fromisoformat(timestamp)

    @staticmethod
    def _format_isotime(value: datetime) -> str:
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def _parse_period(period: str) -> timedelta:
        match = re.fullmatch(r"(?i)(\d+)([dhms])", period.strip())
        if match is None:
            raise ValueError("period must use a compact form such as '1D', '2H', or '30M'")

        amount = int(match.group(1))
        unit = match.group(2).upper()
        if unit == "D":
            return timedelta(days=amount)
        if unit == "H":
            return timedelta(hours=amount)
        if unit == "M":
            return timedelta(minutes=amount)
        return timedelta(seconds=amount)

    def _use_period_window(self) -> str | None:
        if self.period is None:
            return self.datetime

        if self.datetime is not None:
            raise ValueError("Use either 'datetime' or 'period', not both")

        reference = self._parse_isotime(self.reference_time) if self.reference_time else datetime.now(timezone.utc)
        span = self._parse_period(self.period)
        start = reference - span
        return f"{self._format_isotime(start)}/{self._format_isotime(reference)}"

    def _validate(self) -> None:
        if self.scan_type is not None and self.scan_type not in self._allowed_scan_types:
            raise ValueError("scan_type must be either 'fullRange' or 'doppler'")

        if self.collection not in self._allowed_collections:
            raise ValueError("collection must be either 'volume', 'pseudoCappi' or 'composite'")

        if self.station_id is not None and self.collection not in self._station_id_collections:
            raise ValueError("station_id can only be used for the 'volume' and 'pseudoCappi' collections")

        if self.sortorder is not None and self.sortorder != "datetime,DESC":
            raise ValueError("sortorder can only be 'datetime,DESC'")

    def as_params(self) -> dict[str, Any]:
        self._validate()

        params: dict[str, Any] = {}

        if self.station_id is not None:
            params["stationId"] = self.station_id
        if self.scan_type is not None:
            params["scanType"] = self.scan_type

        resolved_datetime = self._use_period_window()
        if resolved_datetime is not None:
            params["datetime"] = resolved_datetime

        if self.bbox is not None:
            params["bbox"] = self.bbox
        if self.bbox_crs is not None:
            params["bbox-crs"] = self.bbox_crs
        if self.limit is not None:
            params["limit"] = self.limit
        if self.offset is not None:
            params["offset"] = self.offset
        if self.sortorder is not None:
            params["sortorder"] = self.sortorder

        params.update(self.extra_params)
        return params

    def path(self) -> str:
        return f"collections/{self.collection}/items"

    def next_page(self) -> "RadarQuery":
        """Return the next page by increasing the offset automatically.

        If the current query does not specify a limit, the DMI service default
        of 1000 items is assumed. The offset is advanced by that page size.
        """
        step = self.limit if self.limit is not None else 1000
        offset = self.offset if self.offset is not None else 0
        return RadarQuery(
            collection=self.collection,
            station_id=self.station_id,
            scan_type=self.scan_type,
            datetime=self.datetime,
            period=self.period,
            reference_time=self.reference_time,
            bbox=self.bbox,
            bbox_crs=self.bbox_crs,
            limit=self.limit,
            offset=offset + step,
            sortorder=self.sortorder,
            extra_params=dict(self.extra_params),
        )
