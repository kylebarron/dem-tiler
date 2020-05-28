"""tests cogeo_mosaic_tiler.handlers.app."""

import base64
import json
import os
import re
import urllib
from typing import Any
from unittest.mock import patch

import pytest

from cogeo_mosaic.backends.file import FileBackend
from cogeo_mosaic.mosaic import MosaicJSON

asset_above = os.path.join(os.path.dirname(__file__), "fixtures", "above_cog.tif")
above_mosaic_content = MosaicJSON.from_urls([asset_above])

asset1 = os.path.join(os.path.dirname(__file__), "fixtures", "cog1.tif")
asset2 = os.path.join(os.path.dirname(__file__), "fixtures", "cog2.tif")
mosaic_content = MosaicJSON.from_urls([asset1, asset2])
mosaic_dict = mosaic_content.dict(exclude_none=True)
request_json = os.path.join(os.path.dirname(__file__), "fixtures", "request.json")


class MosaicMockReadRaise(FileBackend):
    """Mock."""

    def __init__(self, *args, mosaic_def: MosaicJSON = None, **kwargs: Any):
        """Initialize FileBackend."""
        assert args[0].startswith("s3://my-bucket")

        if mosaic_def is not None:
            self.mosaic_def = mosaic_def
        else:
            raise Exception("Nope Nope Nope")

    def write(self, *args, **kwargs):
        """Write."""
        pass


class MosaicMock(FileBackend):
    """Mock."""

    def __init__(self, *args, mosaic_def: MosaicJSON = None, **kwargs: Any):
        """Initialize FileBackend."""
        assert args[0].startswith("s3://my-bucket")

        if mosaic_def is not None:
            self.mosaic_def = mosaic_def
        else:
            self.mosaic_def = (
                above_mosaic_content
                if args[0].endswith("/above.json")
                else mosaic_content
            )

    def write(self, *args, **kwargs):
        """Write."""
        pass


class MosaicMockDB(FileBackend):
    """Mock."""

    def __init__(self, *args, mosaic_def: MosaicJSON = None, **kwargs: Any):
        """Initialize FileBackend."""
        assert args[0].startswith("dynamodb://")

        if mosaic_def is not None:
            self.mosaic_def = mosaic_def
        else:
            self.mosaic_def = mosaic_content

    def write(self, *args, **kwargs):
        """Write."""
        pass


@pytest.fixture(autouse=True)
def testing_env_var(monkeypatch):
    """Set fake env to make sure we don't hit AWS services."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "jqt")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "rde")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-west-2")
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.setenv("AWS_CONFIG_FILE", "/tmp/noconfigheere")
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", "/tmp/noconfighereeither")
    monkeypatch.setenv("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
    monkeypatch.setenv("MOSAIC_DEF_BUCKET", "my-bucket")
    monkeypatch.setenv("CACHE_CONTROL", "max-age=3600")


@pytest.fixture()
def app():
    """cogeo-mosaic-tiler handler fixture."""
    # HACK: We import the app in a test function to make sure the boto3_session uses
    # the monkeypatched env
    from cogeo_mosaic_tiler.handlers.app import app

    return app


@pytest.fixture()
def event():
    """Event fixture."""
    return {
        "resource": "/",
        "path": "/",
        "httpMethod": "GET",
        "headers": {"Host": "somewhere-over-the-rainbow.com"},
        "queryStringParameters": {},
    }


def test_favicon(app, event):
    """Test /favicon.ico route."""
    event["path"] = "/favicon.ico"
    resp = {
        "body": "",
        "headers": {"Content-Type": "text/plain"},
        "statusCode": 204,
    }
    res = app(event, {})
    assert res == resp


@patch("cogeo_mosaic_tiler.handlers.app._aws_head_object")
@patch("cogeo_mosaic_tiler.handlers.app.MosaicBackend")
def test_add_mosaic(backend, head, app, event):
    """Test /add route."""
    event["path"] = "/add"
    event["httpMethod"] = "POST"
    event["body"] = json.dumps(mosaic_dict).encode()
    event["queryStringParameters"] = dict(
        mosaicid="b99dd7e8cc284c6da4d2899e16b6ff85c8ab97041ae7b459eb67e516"
    )
    headers = {
        "Content-Type": "application/json",
    }
    backend.side_effect = MosaicMock
    head.return_value = False

    res = app(event, {})
    assert res["headers"] == headers
    assert res["statusCode"] == 200
    body = json.loads(res["body"])
    assert body["id"] == "b99dd7e8cc284c6da4d2899e16b6ff85c8ab97041ae7b459eb67e516"
    assert body["status"] == "READY"
    backend.assert_called_once()
    backend.reset_mock()

    headers = {
        "Content-Type": "text/plain",
    }
    head.return_value = True
    res = app(event, {})
    assert res["headers"] == headers
    assert res["statusCode"] == 400
    assert (
        res["body"]
        == "Mosaic: b99dd7e8cc284c6da4d2899e16b6ff85c8ab97041ae7b459eb67e516 already exist."
    )
    backend.assert_not_called()


@patch("cogeo_mosaic_tiler.handlers.app.MosaicBackend")
def test_create_mosaic(backend, app, event):
    """Test /create route."""
    event["path"] = "/create"
    event["httpMethod"] = "POST"
    event["isBase64Encoded"] = "true"
    event["body"] = base64.b64encode(json.dumps([asset1, asset2]).encode()).decode(
        "utf-8"
    )

    headers = {
        "Content-Type": "application/json",
    }

    backend.side_effect = MosaicMockReadRaise

    res = app(event, {})
    assert res["headers"] == headers
    assert res["statusCode"] == 200
    tilejson = json.loads(res["body"])
    assert tilejson["bounds"]
    assert tilejson["center"]
    assert tilejson["name"]
    tileurl = tilejson["tiles"][0]
    url_info = urllib.parse.urlparse(tileurl)
    assert url_info.netloc == "somewhere-over-the-rainbow.com"
    assert re.match(r"/[0-9A-Fa-f]{56}/{z}/{x}/{y}@1x", url_info.path)
    assert backend.call_count == 2


@patch("cogeo_mosaic_tiler.handlers.app.MosaicBackend")
def test_create_mosaicPNG(backend, app, event):
    """Test /create route."""
    event["path"] = "/create"
    event["httpMethod"] = "POST"
    event["isBase64Encoded"] = "true"
    event["body"] = base64.b64encode(json.dumps([asset1, asset2]).encode()).decode(
        "utf-8"
    )
    event["queryStringParameters"] = dict(tile_format="png")

    headers = {
        "Content-Type": "application/json",
    }

    backend.side_effect = MosaicMock

    res = app(event, {})
    assert res["headers"] == headers
    assert res["statusCode"] == 200
    tilejson = json.loads(res["body"])
    assert tilejson["bounds"]
    assert tilejson["center"]
    assert tilejson["name"]
    tileurl = tilejson["tiles"][0]
    url_info = urllib.parse.urlparse(tileurl)
    assert url_info.netloc == "somewhere-over-the-rainbow.com"
    assert re.match(r"/[0-9A-Fa-f]{56}/{z}/{x}/{y}@1x.png", url_info.path)
    backend.assert_called_once()


@patch("cogeo_mosaic_tiler.handlers.app.MosaicBackend")
def test_create_mosaicMVT(backend, app, event):
    """Test /create route."""
    event["path"] = "/create"
    event["httpMethod"] = "POST"
    event["isBase64Encoded"] = "true"
    event["body"] = base64.b64encode(json.dumps([asset1, asset2]).encode()).decode(
        "utf-8"
    )
    event["queryStringParameters"] = dict(tile_format="mvt")

    headers = {
        "Content-Type": "application/json",
    }

    backend.side_effect = MosaicMock

    res = app(event, {})
    assert res["headers"] == headers
    assert res["statusCode"] == 200
    tilejson = json.loads(res["body"])
    assert tilejson["bounds"]
    assert tilejson["center"]
    assert tilejson["name"]
    tileurl = tilejson["tiles"][0]
    url_info = urllib.parse.urlparse(tileurl)
    assert url_info.netloc == "somewhere-over-the-rainbow.com"
    assert re.match(r"/[0-9A-Fa-f]{56}/{z}/{x}/{y}.mvt", url_info.path)
    backend.assert_called_once()


@patch("cogeo_mosaic_tiler.handlers.app.MosaicBackend")
def test_info(backend, app, event):
    """Test /info route."""
    event["path"] = "/info"
    event["queryStringParameters"] = dict(url="s3://my-bucket/mymosaic.json")

    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "max-age=3600",
    }

    backend.side_effect = MosaicMock

    res = app(event, {})
    assert res["headers"] == headers
    assert res["statusCode"] == 200
    body = json.loads(res["body"])
    assert body["bounds"]
    assert body["center"]
    assert body["maxzoom"] == 9
    assert body["minzoom"] == 7
    assert body["name"] == "s3://my-bucket/mymosaic.json"
    assert len(body["quadkeys"]) == 9
    assert body["layers"] == ["band1", "band2", "band3"]
    backend.assert_called_once()
    backend.reset_mock()

    event["queryStringParameters"] = dict(url="dynamodb://us-somewhere/table")
    backend.side_effect = MosaicMockDB

    res = app(event, {})
    assert res["headers"] == headers
    assert res["statusCode"] == 200
    body = json.loads(res["body"])
    assert body["bounds"]
    assert body["center"]
    assert body["maxzoom"] == 9
    assert body["minzoom"] == 7
    assert body["name"] == "dynamodb://us-somewhere/table"
    assert not body.get("quadkeys")
    assert not body.get("layers")
    assert not body.get("dtype")
    backend.assert_called_once()


@patch("cogeo_mosaic_tiler.handlers.app.MosaicBackend")
def test_info_mosaicid(backend, app, event):
    """Test /info route."""
    event["path"] = "/b99dd7e8cc284c6da4d2899e16b6ff85c8ab97041ae7b459eb67e516/info"

    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "max-age=3600",
    }
    backend.side_effect = MosaicMock

    res = app(event, {})
    assert res["headers"] == headers
    assert res["statusCode"] == 200
    body = json.loads(res["body"])
    assert body["bounds"]
    assert body["center"]
    assert body["maxzoom"] == 9
    assert body["minzoom"] == 7
    assert body["name"] == "b99dd7e8cc284c6da4d2899e16b6ff85c8ab97041ae7b459eb67e516"
    assert len(body["quadkeys"]) == 9
    assert body["layers"] == ["band1", "band2", "band3"]
    backend.assert_called_once()


@patch("cogeo_mosaic_tiler.handlers.app.MosaicBackend")
def test_info_MissingUrl(backend, app, event):
    """Test /info route."""
    event["path"] = "/info"

    res = app(event, {})
    assert res["statusCode"] == 400
    assert res["body"] == "Missing 'MosaicID or URL' parameter"
    backend.assert_not_called()


@patch("cogeo_mosaic_tiler.handlers.app.MosaicBackend")
def test_geojson_mosaicid(backend, app, event):
    """Test /geojson route."""
    event["path"] = "/b99dd7e8cc284c6da4d2899e16b6ff85c8ab97041ae7b459eb67e516/geojson"

    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "max-age=3600",
    }
    backend.side_effect = MosaicMock

    res = app(event, {})
    assert res["headers"] == headers
    assert res["statusCode"] == 200
    body = json.loads(res["body"])
    assert body["type"] == "FeatureCollection"
    assert len(body["features"]) == 9
    backend.assert_called_once()


@patch("cogeo_mosaic_tiler.handlers.app.MosaicBackend")
def test_geojson_MissingUrl(backend, app, event):
    """Test /geojson route."""
    event["path"] = "/geojson"

    res = app(event, {})
    assert res["statusCode"] == 400
    assert res["body"] == "Missing 'MosaicID or URL' parameter"
    backend.assert_not_called()


@patch("cogeo_mosaic_tiler.handlers.app.MosaicBackend")
def test_tilejson(backend, app, event):
    """Test /tilejson.json route."""
    event["path"] = "/tilejson.json"

    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "max-age=3600",
    }
    res = app(event, {})
    assert res["statusCode"] == 400
    assert res["body"] == "Missing 'MosaicID or URL' parameter"
    backend.assert_not_called()
    backend.reset_mock()

    # png 256px
    event["queryStringParameters"] = dict(
        url="s3://my-bucket/mymosaic.json", rescale="-1,1"
    )
    backend.side_effect = MosaicMock

    res = app(event, {})
    assert res["headers"] == headers
    assert res["statusCode"] == 200
    body = json.loads(res["body"])
    assert body["bounds"]
    assert body["center"]
    assert body["maxzoom"] == 9
    assert body["minzoom"] == 7
    assert body["name"] == "s3://my-bucket/mymosaic.json"
    assert body["tilejson"] == "2.1.0"

    url_info = urllib.parse.urlparse(body["tiles"][0])
    assert url_info.netloc == "somewhere-over-the-rainbow.com"
    assert url_info.path == "/{z}/{x}/{y}@1x"
    qs = urllib.parse.parse_qs(url_info.query)
    assert qs["url"][0] == "s3://my-bucket/mymosaic.json"
    assert qs["rescale"][0] == "-1,1"

    # Jpeg 512px
    event["queryStringParameters"] = dict(
        url="s3://my-bucket/mymosaic.json", tile_format="jpg", tile_scale=2
    )

    res = app(event, {})
    assert res["headers"] == headers
    assert res["statusCode"] == 200
    body = json.loads(res["body"])
    url_info = urllib.parse.urlparse(body["tiles"][0])
    assert url_info.netloc == "somewhere-over-the-rainbow.com"
    assert url_info.path == "/{z}/{x}/{y}@2x.jpg"
    qs = urllib.parse.parse_qs(url_info.query)
    assert qs["url"][0] == "s3://my-bucket/mymosaic.json"

    event["queryStringParameters"] = dict(
        url="s3://my-bucket/mymosaic.json", tile_format="pbf"
    )

    res = app(event, {})
    assert res["headers"] == headers
    assert res["statusCode"] == 200
    body = json.loads(res["body"])
    url_info = urllib.parse.urlparse(body["tiles"][0])
    assert url_info.netloc == "somewhere-over-the-rainbow.com"
    assert url_info.path == "/{z}/{x}/{y}.pbf"
    qs = urllib.parse.parse_qs(url_info.query)
    assert qs["url"][0] == "s3://my-bucket/mymosaic.json"


@patch("cogeo_mosaic_tiler.handlers.app.MosaicBackend")
def test_tilejson_mosaicid(backend, app, event):
    """Test /tilejson.json route."""
    event[
        "path"
    ] = "/b99dd7e8cc284c6da4d2899e16b6ff85c8ab97041ae7b459eb67e516/tilejson.json"
    event["queryStringParameters"] = dict(rescale="-1,1")

    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "max-age=3600",
    }
    backend.side_effect = MosaicMock

    res = app(event, {})
    assert res["headers"] == headers
    assert res["statusCode"] == 200
    body = json.loads(res["body"])
    assert body["bounds"]
    assert body["center"]
    assert body["maxzoom"] == 9
    assert body["minzoom"] == 7
    assert body["name"] == "b99dd7e8cc284c6da4d2899e16b6ff85c8ab97041ae7b459eb67e516"
    assert body["tilejson"] == "2.1.0"

    url_info = urllib.parse.urlparse(body["tiles"][0])
    assert url_info.netloc == "somewhere-over-the-rainbow.com"
    assert (
        url_info.path
        == "/b99dd7e8cc284c6da4d2899e16b6ff85c8ab97041ae7b459eb67e516/{z}/{x}/{y}@1x"
    )
    qs = urllib.parse.parse_qs(url_info.query)
    assert qs["rescale"][0] == "-1,1"


@patch("cogeo_mosaic_tiler.handlers.app.MosaicBackend")
def test_get_mosaic_wmts(backend, app, event):
    """Test WMTS."""
    event["path"] = "/wmts"

    res = app(event, {})
    assert res["statusCode"] == 400
    assert res["body"] == "Missing 'MosaicID or URL' parameter"
    backend.assert_not_called()

    event["queryStringParameters"] = dict(
        tile_scale="2", url="s3://my-bucket/mymosaic.json"
    )

    headers = {
        "Content-Type": "application/xml",
        "Cache-Control": "max-age=3600",
    }
    backend.side_effect = MosaicMock

    res = app(event, {})
    assert res["headers"] == headers
    assert res["statusCode"] == 200
    body = res["body"]
    assert "https://somewhere-over-the-rainbow.com/wmts" in body
    backend.assert_called_once()


@patch("cogeo_mosaic_tiler.handlers.app.MosaicBackend")
def test_get_mosaic_wmts_mosaicid(backend, app, event):
    """Test /wmts route."""
    event["path"] = "/b99dd7e8cc284c6da4d2899e16b6ff85c8ab97041ae7b459eb67e516/wmts"
    event["queryStringParameters"] = dict(tile_scale="2")

    headers = {
        "Content-Type": "application/xml",
        "Cache-Control": "max-age=3600",
    }
    backend.side_effect = MosaicMock

    res = app(event, {})
    assert res["headers"] == headers
    assert res["statusCode"] == 200
    body = res["body"]
    assert (
        "https://somewhere-over-the-rainbow.com/b99dd7e8cc284c6da4d2899e16b6ff85c8ab97041ae7b459eb67e516/wmts"
        in body
    )
    assert (
        "https://somewhere-over-the-rainbow.com/b99dd7e8cc284c6da4d2899e16b6ff85c8ab97041ae7b459eb67e516/{TileMatrix}/"
        in body
    )
    backend.assert_called_once()


@patch("cogeo_mosaic_tiler.handlers.app.MosaicBackend")
def test_API_errors(backend, app, event):
    """Test /tiles routes."""
    # missing URL
    event["path"] = "/9/150/182.png"
    res = app(event, {})
    assert res["statusCode"] == 400
    assert res["body"] == "Missing 'MosaicID or URL' parameter"
    backend.assert_not_called()
    backend.reset_mock()

    backend.side_effect = MosaicMock

    # empty assets
    event["path"] = "/9/300/182.png"
    event["queryStringParameters"] = dict(url="s3://my-bucket/mymosaic.json")
    res = app(event, {})
    assert res["statusCode"] == 204
    headers = res["headers"]
    assert headers["Content-Type"] == "text/plain"
    assert res["body"] == "No assets found for tile 9-300-182"


@patch("cogeo_mosaic_tiler.handlers.app.MosaicBackend")
def test_API_tiles(backend, app, event):
    """Test /tiles routes."""
    backend.side_effect = MosaicMock

    event["path"] = "/9/150/182.png"
    event["queryStringParameters"] = dict(url="s3://my-bucket/mymosaic.json")
    res = app(event, {})
    assert res["statusCode"] == 200
    assert res["headers"]["Content-Type"] == "image/png"
    assert res["headers"].get("Cache-Control")
    assert res["body"]

    event["path"] = "/9/150/182.png"
    event["queryStringParameters"] = dict(
        url="s3://my-bucket/mymosaic.json", pixel_selection="first"
    )
    res = app(event, {})
    assert res["statusCode"] == 200
    assert res["headers"]["Content-Type"] == "image/png"
    assert res["body"]

    event["path"] = "/9/150/182.png"
    event["queryStringParameters"] = dict(
        url="s3://my-bucket/mymosaic.json", pixel_selection="highest"
    )
    res = app(event, {})
    assert res["statusCode"] == 200
    assert res["headers"]["Content-Type"] == "image/png"
    assert res["body"]

    event["path"] = "/9/150/182.png"
    event["queryStringParameters"] = dict(
        url="s3://my-bucket/mymosaic.json", pixel_selection="lowest"
    )
    res = app(event, {})
    assert res["statusCode"] == 200
    assert res["headers"]["Content-Type"] == "image/png"
    assert res["body"]

    event["path"] = "/9/150/182.png"
    event["queryStringParameters"] = dict(
        url="s3://my-bucket/mymosaic.json", pixel_selection="mean"
    )
    res = app(event, {})
    assert res["statusCode"] == 200
    assert res["headers"]["Content-Type"] == "image/png"
    assert res["body"]

    event["path"] = "/9/150/182.png"
    event["queryStringParameters"] = dict(
        url="s3://my-bucket/mymosaic.json", pixel_selection="median"
    )
    res = app(event, {})
    assert res["statusCode"] == 200
    assert res["headers"]["Content-Type"] == "image/png"
    assert res["body"]

    event["path"] = "/9/150/182.png"
    event["queryStringParameters"] = dict(
        url="s3://my-bucket/mymosaic.json",
        rescale="0,10000",
        indexes="1",
        color_map="cfastie",
    )
    res = app(event, {})
    assert res["statusCode"] == 200
    assert res["headers"]["Content-Type"] == "image/png"
    assert res["body"]

    event["path"] = "/9/150/182@2x.png"
    event["queryStringParameters"] = dict(
        url="s3://my-bucket/mymosaic.json", rescale="0,10000"
    )
    res = app(event, {})
    assert res["statusCode"] == 200
    assert res["headers"]["Content-Type"] == "image/png"
    assert res["body"]

    event["path"] = "/9/155/182@2x"
    event["queryStringParameters"] = dict(
        url="s3://my-bucket/mymosaic.json", rescale="0,10000"
    )
    res = app(event, {})
    assert res["statusCode"] == 200
    assert res["headers"]["Content-Type"] == "image/png"
    assert res["body"]

    event["path"] = "/9/150/182"
    event["queryStringParameters"] = dict(
        url="s3://my-bucket/mymosaic.json", rescale="0,10000"
    )
    res = app(event, {})
    assert res["statusCode"] == 200
    assert res["headers"]["Content-Type"] == "image/jpg"
    assert res["body"]

    # Mosaic ID
    event[
        "path"
    ] = "/b99dd7e8cc284c6da4d2899e16b6ff85c8ab97041ae7b459eb67e516/9/150/182.png"
    event["queryStringParameters"] = dict(rescale="0,10000")
    res = app(event, {})
    assert res["statusCode"] == 200
    assert res["headers"]["Content-Type"] == "image/png"
    assert res["body"]

    event[
        "path"
    ] = "/b99dd7e8cc284c6da4d2899e16b6ff85c8ab97041ae7b459eb67e516/9/150/182"
    event["queryStringParameters"] = dict(rescale="0,10000")
    res = app(event, {})
    assert res["statusCode"] == 200
    assert res["headers"]["Content-Type"] == "image/jpg"
    assert res["body"]

    event[
        "path"
    ] = "/b99dd7e8cc284c6da4d2899e16b6ff85c8ab97041ae7b459eb67e516/9/150/182@2x.png"
    event["queryStringParameters"] = dict(rescale="0,10000")
    res = app(event, {})
    assert res["statusCode"] == 200
    assert res["headers"]["Content-Type"] == "image/png"
    assert res["body"]

    event[
        "path"
    ] = "/b99dd7e8cc284c6da4d2899e16b6ff85c8ab97041ae7b459eb67e516/9/150/182@2x"
    event["queryStringParameters"] = dict(rescale="0,10000")
    res = app(event, {})
    assert res["statusCode"] == 200
    assert res["headers"]["Content-Type"] == "image/jpg"
    assert res["body"]


@patch("cogeo_mosaic_tiler.handlers.app.MosaicBackend")
def test_API_MVTtiles(backend, app, event):
    """Test /tiles routes."""
    backend.side_effect = MosaicMock

    event["path"] = "/9/150/182.pbf"
    event["queryStringParameters"] = {}
    res = app(event, {})
    assert res["statusCode"] == 400

    event["path"] = "/9/150/182.pbf"
    event["queryStringParameters"] = dict(
        url="s3://my-bucket/mymosaic.json", tile_size="64"
    )
    res = app(event, {})
    assert res["statusCode"] == 200
    assert res["headers"]["Content-Type"] == "application/x-protobuf"
    assert res["body"]

    event[
        "path"
    ] = "/b99dd7e8cc284c6da4d2899e16b6ff85c8ab97041ae7b459eb67e516/9/150/182.pbf"
    event["queryStringParameters"] = dict(tile_size="64")
    res = app(event, {})
    assert res["statusCode"] == 200
    assert res["headers"]["Content-Type"] == "application/x-protobuf"
    assert res["body"]


@patch("cogeo_mosaic_tiler.handlers.app.MosaicBackend")
def test_API_points(backend, app, event):
    """Test /point routes."""
    backend.side_effect = MosaicMock

    event["path"] = "/point"
    event["queryStringParameters"] = dict(
        url="s3://my-bucket/mymosaic.json", lng="-73", lat="45"
    )
    res = app(event, {})
    assert res["statusCode"] == 200
    assert res["headers"]["Content-Type"] == "application/json"
    body = json.loads(res["body"])
    assert body["coordinates"]
    assert body["values"]
    assert len(body["values"]) == 2


@patch("cogeo_mosaic_tiler.handlers.app.MosaicBackend")
def test_API_tilesCustomCmap(backend, app, event):
    """Test /tiles routes."""
    backend.side_effect = MosaicMock

    event["path"] = "/8/53/50.png"
    event["queryStringParameters"] = dict(
        url="s3://my-bucket/above.json", indexes="1", color_map="custom_above",
    )
    res = app(event, {})
    assert res["statusCode"] == 200
    assert res["headers"]["Content-Type"] == "image/png"
    assert res["headers"].get("Cache-Control")
    assert res["body"]
