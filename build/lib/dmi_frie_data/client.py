from __future__ import annotations

from .http import DMIHTTPClient, HTTPConfig
from .services import (
    ClimateService,
    ForecastEDRService,
    ForecastSTACService,
    LightningService,
    ObservationService,
    RadarService,
)


class DMIClient:
    """High-level entrypoint for the public DMI Frie Data APIs.

    The client keeps the public interface small while exposing the main
    service families cleanly:

    - radar: STAC-style radar file downloads
    - forecast_stac: STAC-style forecast file downloads
    - forecast_edr: OGC EDR-style forecast queries
    - lightning: lightning observation features
    - observation: meteorological/oceanographic observation APIs
    - climate: climate observation APIs
    """

    def __init__(self, *, config: HTTPConfig | None = None) -> None:
        self._http = DMIHTTPClient(config=config)
        self._services = []

        self.radar = RadarService(self._http, prefix="/v1/radardata")
        self.forecast_stac = ForecastSTACService(self._http, prefix="/v1/forecastdata")
        self.forecast_edr = ForecastEDRService(self._http, prefix="/v1/forecastedr")
        self.lightning = LightningService(self._http, prefix="/v2/lightningdata")
        self.observation = ObservationService(self._http, prefix="/v1/meteorological-observation")
        self.climate = ClimateService(self._http, prefix="/v2/climateData")

        self._services.extend(
            [
                self.radar,
                self.forecast_stac,
                self.forecast_edr,
                self.lightning,
                self.observation,
                self.climate,
            ]
        )

    @property
    def http(self) -> DMIHTTPClient:
        return self._http

    @http.setter
    def http(self, value: DMIHTTPClient) -> None:
        self._http = value
        for service in self._services:
            service._http = value

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "DMIClient":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
