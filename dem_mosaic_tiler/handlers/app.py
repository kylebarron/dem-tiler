"""dem_mosaic_tiler.handlers.app: handle request for cogeo-mosaic-tiler endpoints."""

import json
from io import BytesIO
import os
import random
import urllib.parse
import warnings
from typing import Any, Tuple, Union

import mercantile
import rasterio
from boto3.session import Session as boto3_session
from lambda_proxy.proxy import API
from rasterio.session import AWSSession
from rio_tiler.profiles import img_profiles
from rio_tiler.reader import multi_point
from rio_tiler.utils import geotiff_options, render, mapzen_elevation_rgb

from cogeo_mosaic import version as mosaic_version
from cogeo_mosaic.backends import MosaicBackend
from cogeo_mosaic.backends.utils import get_hash
from cogeo_mosaic.mosaic import MosaicJSON
from dem_mosaic_tiler.utils import _get_layer_names
from pymartini import Martini, rescale_positions
from quantized_mesh_encoder import encode
from dem_mosaic_tiler.reader import tile_assets

session = boto3_session()
s3_client = session.client("s3")
aws_session = AWSSession(session=session)

app = API(name="cogeo-mosaic-tiler")

params = dict(payload_compression_method="gzip", binary_b64encode=True)
if os.environ.get("CORS"):
    params["cors"] = True


@app.post("/add", tag=["mosaic"], **params)
def _add(body: str, url: str) -> Tuple:
    mosaic_definition = MosaicJSON(**json.loads(body))
    with MosaicBackend(url, mosaic_def=mosaic_definition) as mosaic:
        mosaic.write()

    return (
        "OK",
        "application/json",
        json.dumps({
            "id": url,
            "status": "READY"}, separators=(",", ":")),
    )


params["cache_control"] = os.environ.get("CACHE_CONTROL", None)


@app.get("/info", tag=["metadata"], **params)
def _info(url: str = None) -> Tuple:
    """Handle /info requests."""
    if not url:
        return ("NOK", "text/plain", "Missing URL parameter")

    with MosaicBackend(url) as mosaic:
        meta = mosaic.metadata
        response = {
            "bounds": meta["bounds"],
            "center": meta["center"],
            "maxzoom": meta["maxzoom"],
            "minzoom": meta["minzoom"],
            "name": url, }

        if not url.startswith("dynamodb://"):
            mosaic_quadkeys = set(mosaic._quadkeys)
            tile = mercantile.quadkey_to_tile(
                random.sample(mosaic_quadkeys, 1)[0])
            assets = mosaic.tile(*tile)
            with rasterio.open(assets[0]) as src_dst:
                layer_names = _get_layer_names(src_dst)
                dtype = src_dst.dtypes[0]

            response["quadkeys"] = list(mosaic_quadkeys)
            response["layers"] = layer_names
            response["dtype"] = dtype
        else:
            warnings.warn(
                "Cannot retrieve 'quadkeys,layers and dtype' from dynamoDB mosaic."
            )

        return (
            "OK", "application/json", json.dumps(
                response, separators=(",", ":")))


@app.get("/geojson", tag=["metadata"], **params)
def _geojson(url: str = None) -> Tuple:
    """Handle /geojson requests."""
    if not url:
        return ("NOK", "text/plain", "Missing URL parameter")

    with MosaicBackend(url) as mosaic:
        geojson = {
            "type":
                "FeatureCollection",
            "features": [
                mercantile.feature(
                    mercantile.quadkey_to_tile(qk), props=dict(files=files))
                for qk, files in mosaic.mosaic_def.tiles.items()], }

    return (
        "OK", "application/json", json.dumps(geojson, separators=(",", ":")))


params["tag"] = ["tiles"]


@app.get("/tilejson.json", **params)
def _tilejson(
        url: str = None,
        tile_scale: int = 1,
        tile_format: str = None,
        **kwargs: Any,
) -> Tuple:
    """Handle /tilejson.json requests."""
    if not url:
        return ("NOK", "text/plain", "Missing URL parameter")

    kwargs.update(dict(url=url))
    host = app.host

    if tile_format in ["pbf", "mvt"]:
        tile_url = f"{host}/{{z}}/{{x}}/{{y}}.{tile_format}"
    elif tile_format in ["png", "jpg", "webp", "tif", "npy"]:
        tile_url = f"{host}/{{z}}/{{x}}/{{y}}@{tile_scale}x.{tile_format}"
    else:
        tile_url = f"{host}/{{z}}/{{x}}/{{y}}@{tile_scale}x"

    qs = urllib.parse.urlencode(list(kwargs.items()))
    if qs:
        tile_url += f"?{qs}"

    with MosaicBackend(url) as mosaic:
        meta = mosaic.metadata
        response = {
            "bounds": meta["bounds"],
            "center": meta["center"],
            "maxzoom": meta["maxzoom"],
            "minzoom": meta["minzoom"],
            "name": url,
            "tilejson": "2.1.0",
            "tiles": [tile_url], }
    return (
        "OK", "application/json", json.dumps(response, separators=(",", ":")))


@app.get("/contour/<int:z>/<int:x>/<int:y>.pbf", **params)
def _contour(
        z: int = None,
        x: int = None,
        y: int = None,
        url: str = None,
        tile_size: Union[str, int] = 256,
        pixel_selection: str = "first",
        resampling_method: str = "nearest",
) -> Tuple:
    """Handle MVT requests."""
    if not url:
        return ("NOK", "text/plain", "Missing URL parameter")

    tile_size = int(tile_size)
    tile, mask = tile_assets(
        x, y, z, url, tile_size, pixel_selection, resampling_method)

    if tile is None:
        return ("EMPTY", "text/plain", "empty tiles")

    # TODO: shell out to gdal_contour, then to tippecanoe

    return ("OK", "application/x-protobuf", "")


@app.get("/rgb/<int:z>/<int:x>/<int:y>.<ext>", **params)
@app.get("/rgb/<int:z>/<int:x>/<int:y>", **params)
def _img(
        z: int = None,
        x: int = None,
        y: int = None,
        tile_size: Union[str, int] = 256,
        ext: str = 'png',
        url: str = None,
        encoding: str = 'terrarium',
        pixel_selection: str = "first",
        resampling_method: str = "nearest",
) -> Tuple:
    """Handle tile requests."""
    if not url:
        return ("NOK", "text/plain", "Missing URL parameter")

    tile_size = int(tile_size)
    tile, mask = tile_assets(
        x, y, z, url, tile_size, pixel_selection, resampling_method)

    if tile is None:
        return ("EMPTY", "text/plain", "empty tiles")

    if encoding == 'terrarium':
        rgb = mapzen_elevation_rgb(tile)
    else:
        raise ValueError('Invalid encoding')

    driver = ext
    options = img_profiles.get(driver, {})

    if ext == "tif":
        ext = "tiff"
        driver = "GTiff"
        options = geotiff_options(x, y, z, tile_size)

    return (
        "OK",
        f"image/{ext}",
        # NOTE: Do I need to include mask?
        # render(rgb, mask, img_format=driver, **options),
        render(rgb, img_format=driver, **options),
    )


@app.get("/mesh/<int:z>/<int:x>/<int:y>.terrain", **params)
@app.get("/mesh/<int:z>/<int:x>/<int:y>@<int:scale>x.terrain", **params)
def _mesh(
        z: int = None,
        x: int = None,
        y: int = None,
        scale: int = 1,
        url: str = None,
        mesh_max_error: float = 10,
        pixel_selection: str = "first",
        resampling_method: str = "nearest",
) -> Tuple:
    """Handle tile requests."""
    if not url:
        return ("NOK", "text/plain", "Missing URL parameter")

    tile_size = 256 * int(scale)
    tile, mask = tile_assets(
        x, y, z, url, tile_size, pixel_selection, resampling_method)

    if tile is None:
        return ("EMPTY", "text/plain", "empty tiles")

    martini = Martini(tile_size + 1)
    terrain = tile.flatten()
    mar_tile = martini.create_tile(terrain)

    mesh_max_error = float(mesh_max_error)
    vertices, triangles = mar_tile.get_mesh(mesh_max_error)
    bounds = mercantile.bounds(mercantile.Tile(x, y, z))

    rescaled = rescale_positions(
        vertices, terrain, tile_size=tile_size, bounds=bounds, flip_y=True)

    buf = BytesIO()
    encode(buf, rescaled, triangles)
    buf.seek(0)
    return ("OK", "application/vnd.quantized-mesh", buf.read())


@app.get("/point", **params)
def _point(lng: float = None, lat: float = None,
           url: str = None) -> Tuple[str, str, str]:
    """Handle point requests."""
    if not url:
        return ("NOK", "text/plain", "Missing URL parameter")

    if not lat or not lng:
        return ("NOK", "text/plain", "Missing 'Lon/Lat' parameter")

    lng = float(lng)
    lat = float(lat)

    with MosaicBackend(url) as mosaic:
        assets = mosaic.point(lng, lat)
        if not assets:
            return (
                "EMPTY",
                "text/plain",
                f"No assets found for lat/lng ({lat}, {lng})",
            )

    with rasterio.Env(aws_session):
        meta = {
            "coordinates": [lng, lat],
            "values": [{
                "asset": assets[ix],
                "values": value} for ix, value in enumerate(
                    multi_point(assets, coordinates=(lng, lat)))], }
        return (
            "OK", "application/json", json.dumps(meta, separators=(",", ":")))


@app.get("/favicon.ico", tag=["other"])
def favicon() -> Tuple[str, str, str]:
    """Favicon."""
    return ("EMPTY", "text/plain", "")
