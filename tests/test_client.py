import h5py
import numpy as np

from dmi_frie_data import Asset, DMIClient, Feature
from dmi_frie_data.query import ForecastQuery, RadarQuery


class StubHTTP:
    def __init__(self):
        self.calls = []

    def get(self, path, *, params=None):
        self.calls.append((path, params))
        return {
            "type": "CollectionList",
            "links": [{"rel": "self", "href": path}],
            "features": [
                {
                    "id": "sample-item",
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [12.0, 55.0]},
                    "properties": {"datetime": "2024-01-01T00:00:00Z"},
                    "collection": "harmonie_dini_sf",
                    "assets": {"data": {"href": "https://example.test/file.grib", "type": "application/x-grib"}},
                }
            ],
        }

    def download(self, path, *, destination):
        self.calls.append((path, destination))
        return destination

    def close(self):
        return None


def test_client_builds_services_and_calls_collection_endpoint():
    client = DMIClient(config=None)
    client.http = StubHTTP()

    result = client.radar.list_collections()

    assert result["type"] == "CollectionList"
    assert client.http.calls == [("/v1/radardata/collections", None)]

    client.close()


def test_forecast_stac_lists_items_with_expected_filters():
    client = DMIClient(config=None)
    client.http = StubHTTP()

    items = client.forecast_stac.list_items(
        collection="harmonie_dini_sf",
        limit=5,
        modelRun="2024-01-01T00:00:00Z",
    )

    assert items.features[0].id == "sample-item"
    assert items.features[0].collection == "harmonie_dini_sf"
    assert client.http.calls[-1] == (
        "/v1/forecastdata/collections/harmonie_dini_sf/items",
        {"limit": 5, "modelRun": "2024-01-01T00:00:00Z"},
    )

    client.close()


def test_forecast_edr_position_builds_expected_query():
    client = DMIClient(config=None)
    client.http = StubHTTP()

    response = client.forecast_edr.position(
        collection="harmonie_dini_sf",
        coords="POINT(12.561 55.715)",
        parameter_name="temperature-0m",
        crs="crs84",
    )

    assert response["type"] == "CollectionList"
    assert client.http.calls[-1] == (
        "/v1/forecastedr/collections/harmonie_dini_sf/position",
        {"coords": "POINT(12.561 55.715)", "parameter-name": "temperature-0m", "crs": "crs84"},
    )

    client.close()


def test_forecast_query_builder_is_pythonic_and_normalizes_parameters():
    query = ForecastQuery(
        collection="harmonie_dini_sf",
        parameter_name="temperature-0m",
        coords="POINT(12.561 55.715)",
        crs="crs84",
        datetime="2024-01-01T00:00:00Z",
    )

    params = query.as_params()

    assert params == {
        "coords": "POINT(12.561 55.715)",
        "parameter-name": "temperature-0m",
        "crs": "crs84",
        "datetime": "2024-01-01T00:00:00Z",
    }


def test_forecast_service_can_run_a_prebuilt_query_object():
    client = DMIClient(config=None)
    client.http = StubHTTP()

    query = ForecastQuery(
        collection="harmonie_dini_sf",
        parameter_name="temperature-0m",
        coords="POINT(12.561 55.715)",
        crs="crs84",
    )

    response = client.forecast_edr.query(query)

    assert response["type"] == "CollectionList"
    assert client.http.calls[-1] == (
        "/v1/forecastedr/collections/harmonie_dini_sf/position",
        {"coords": "POINT(12.561 55.715)", "parameter-name": "temperature-0m", "crs": "crs84"},
    )

    client.close()


def test_radar_query_builder_is_pythonic_and_normalizes_parameters():
    query = RadarQuery(
        collection="pseudoCappi",
        station_id="06194",
        scan_type="fullRange",
        datetime="2024-01-01T00:00:00Z",
    )

    params = query.as_params()

    assert params == {
        "stationId": "06194",
        "scanType": "fullRange",
        "datetime": "2024-01-01T00:00:00Z",
    }


def test_radar_query_supports_pagination_and_next_page_navigation():
    query = RadarQuery(
        collection="pseudoCappi",
        station_id="06194",
        scan_type="fullRange",
        limit=100,
        offset=0,
    )

    next_query = query.next_page()

    assert next_query.as_params() == {
        "stationId": "06194",
        "scanType": "fullRange",
        "limit": 100,
        "offset": 100,
    }


def test_radar_query_period_creates_a_recent_datetime_window():
    reference_time = "2024-01-02T12:00:00Z"

    query = RadarQuery(
        collection="pseudoCappi",
        station_id="06194",
        scan_type="fullRange",
        period="1D",
        reference_time=reference_time,
    )

    params = query.as_params()

    assert params["datetime"] == "2024-01-01T12:00:00Z/2024-01-02T12:00:00Z"


def test_feature_exposes_the_x_hdf5_asset_natively():
    feature = Feature(
        id="demo",
        assets={
            "x-hdf5": Asset(
                href="https://example.com/radar/file.hdf5",
                title="x-hdf5",
                type="application/x-hdf5",
            )
        },
    )

    assert feature.get_asset("x-hdf5") is not None
    assert feature.get_asset_url("x-hdf5") == "https://example.com/radar/file.hdf5"
    assert feature.x_hdf5_asset is not None
    assert feature.x_hdf5_url == "https://example.com/radar/file.hdf5"


def test_feature_as_array_and_to_geojson_use_bbox_fit(tmp_path):
    hdf5_path = tmp_path / "radar.hdf5"
    with h5py.File(hdf5_path, "w") as handle:
        handle.create_dataset("data", data=np.array([[1.0, 2.0], [3.0, 4.0]]))

    feature = Feature(
        id="demo",
        assets={
            "data": Asset(
                href=str(hdf5_path),
                title="data",
                type="application/x-hdf5",
            )
        },
        bbox=[12.0, 55.0, 13.0, 56.0],
    )

    array = feature.as_array(path=str(hdf5_path), dataset_name="data")
    assert array.shape == (2, 2)
    assert array[0, 0] == 1.0

    geojson_from_file = feature.to_geojson(path=str(hdf5_path), dataset_name="data")

    assert geojson_from_file["type"] == "FeatureCollection"
    assert len(geojson_from_file["features"]) == 4
    assert geojson_from_file["features"][0]["geometry"]["type"] == "Polygon"
    assert geojson_from_file["features"][0]["properties"]["value"] == 1.0

    geojson_from_array = feature.to_geojson(array=array)

    assert geojson_from_array["type"] == "FeatureCollection"
    assert len(geojson_from_array["features"]) == 4
    assert geojson_from_array["features"][0]["geometry"]["type"] == "Polygon"
    assert geojson_from_array["features"][0]["properties"]["value"] == 1.0


def test_radar_query_validates_only_allowed_scan_type_and_sortorder():
    try:
        RadarQuery(collection="pseudoCappi", scan_type="invalid").as_params()
        assert False
    except ValueError:
        pass

    try:
        RadarQuery(collection="pseudoCappi", sortorder="observed,DESC").as_params()
        assert False
    except ValueError:
        pass


def test_stac_feature_download_url_is_exposed_from_assets():
    collection = DMIClient(config=None)
    collection.http = StubHTTP()

    feature_collection = collection.forecast_stac.list_items(collection="harmonie_dini_sf", limit=1)

    assert feature_collection.features[0].download_url == "https://example.test/file.grib"
    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "id": "sample-item",
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [12.0, 55.0]},
                "properties": {"datetime": "2024-01-01T00:00:00Z"},
                "collection": "harmonie_dini_sf",
                "assets": {"data": {"href": "https://example.test/file.grib", "type": "application/x-grib"}},
            }
        ],
    }

    collection = DMIClient(config=None)
    items = collection.forecast_stac.list_items(collection="harmonie_dini_sf")
    items = DMIClient(config=None)
    collection = DMIClient(config=None)
    collection._http = StubHTTP()
    item = DMIClient(config=None)

    feature_collection = DMIClient(config=None)
    feature_collection = None
