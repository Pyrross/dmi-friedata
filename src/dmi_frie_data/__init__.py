"""DMI Frie Data client package."""

from .client import DMIClient
from .models import Asset, Feature, FeatureCollection, Link
from .query import ForecastQuery, RadarQuery

__all__ = ["DMIClient", "ForecastQuery", "RadarQuery", "Asset", "Feature", "FeatureCollection", "Link"]
