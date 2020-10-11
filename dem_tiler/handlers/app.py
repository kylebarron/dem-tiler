"""dem_tiler.handlers.app: handle request for dem-tiler endpoints."""

import json
import os
import urllib.parse
from io import BytesIO
from tempfile import TemporaryDirectory
from typing import Any, Tuple, Union

import mercantile
import quantized_mesh_encoder
import rasterio
from boto3.session import Session as boto3_session
from lambda_proxy.proxy import API
from pymartini import Martini, rescale_positions as martini_rescale_positions
from pydelatin import Delatin
from pydelatin.util import rescale_positions as delatin_rescale_positions
from rasterio import transform
from rasterio.session import AWSSession
from rio_tiler.profiles import img_profiles
from rio_tiler.reader import multi_point
from rio_tiler.utils import geotiff_options, render

from cogeo_mosaic.backends import MosaicBackend
from cogeo_mosaic.mosaic import MosaicJSON
from dem_tiler.gdal import arr_to_gdal_image, create_contour, run_tippecanoe
from dem_tiler.reader import find_assets, load_assets

session = boto3_session()
s3_client = session.client("s3")
aws_session = AWSSession(session=session)

app = API(name="dem-tiler")

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


# While in development, only apply cache control headers to selected endpoints
# params["cache_control"] = os.environ.get("CACHE_CONTROL", None)


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


@app.get("/contour/<int:z>/<int:x>/<int:y>", **params)
def _contour(
        z: int = None,
        x: int = None,
        y: int = None,
        url: str = None,
        scale: int = 1,
        unit: str = 'meters',
        interval: int = 10,
        offset: int = 0,
        pixel_selection: str = "first",
        resampling_method: str = "nearest",
) -> Tuple:
    """Handle MVT requests."""
    if not url:
        return ("NOK", "text/plain", "Missing URL parameter")

    tile_size = int(scale) * 256
    assets = find_assets(x, y, z, url, tile_size)

    if assets is None:
        return ("NOK", "text/plain", "no assets found")

    tile = load_assets(
        x,
        y,
        z,
        assets,
        tile_size,
        input_format=url,
        pixel_selection=pixel_selection,
        resampling_method=resampling_method)

    if tile is None:
        return ("EMPTY", "text/plain", "empty tiles")

    # Convert meters to feet
    if unit == 'feet':
        tile *= 3.28084

    bounds = mercantile.bounds(x, y, z)
    gdal_transform = transform.from_bounds(*bounds, tile_size,
                                           tile_size).to_gdal()

    gdal_image = arr_to_gdal_image(tile.T, gdal_transform)

    features = list(create_contour(gdal_image, interval, offset))

    with TemporaryDirectory() as tmpdir:
        return (
            "OK", "application/x-protobuf",
            run_tippecanoe(features, x, y, z, tmpdir=tmpdir))


# z, x, y = 14, 3090, 6430
# tile_size: Union[str, int] = 256
# ext = 'png'
# url = 'terrarium'
# encoding: str = 'terrarium'
# pixel_selection: str = "first"
# resampling_method: str = "nearest"


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
    assets = find_assets(x, y, z, url, tile_size)

    if assets is None:
        return ("NOK", "text/plain", "no assets found")

    rgb = load_assets(
        x,
        y,
        z,
        assets,
        tile_size,
        input_format=url,
        output_format=encoding,
        pixel_selection=pixel_selection,
        resampling_method=resampling_method)

    if rgb is None:
        return ("EMPTY", "text/plain", "empty tiles")

    driver = ext
    options = img_profiles.get(driver, {})

    if ext == "tif":
        ext = "tiff"
        driver = "GTiff"
        options = geotiff_options(x, y, z, tile_size)

    return (
        "OK",
        f"image/{ext}",
        render(rgb, img_format=driver, **options),
    )


@app.get(
    "/mesh/<int:z>/<int:x>/<int:y>.terrain",
    cache_control=os.getenv("CACHE_CONTROL", None),
    **params)
@app.get(
    "/mesh/<int:z>/<int:x>/<int:y>@<int:scale>x.terrain",
    cache_control=os.getenv("CACHE_CONTROL", None),
    **params)
def _mesh(
        z: int = None,
        x: int = None,
        y: int = None,
        scale: int = 1,
        url: str = None,
        mesh_max_error: float = 10,
        pixel_selection: str = "first",
        resampling_method: str = "nearest",
        mesh_algorithm: str = "pydelatin",
        flip_y: str = "True",
) -> Tuple:
    """Handle tile requests."""
    if not url:
        return ("NOK", "text/plain", "Missing URL parameter")

    # Coerce flip_y to bool
    if not isinstance(flip_y, bool):
        flip_y = flip_y in ['True', 'true']

    use_delatin = 'delatin' in mesh_algorithm.lower()

    tile_size = 256 * int(scale)
    assets = find_assets(x, y, z, url, tile_size)

    if assets is None:
        return ("NOK", "text/plain", "no assets found")

    tile = load_assets(
        x,
        y,
        z,
        assets,
        tile_size,
        # Only need to backfill for martini, not delatin
        backfill=not use_delatin,
        input_format=url,
        pixel_selection=pixel_selection,
        resampling_method=resampling_method)

    # Need to transpose; must be before passing to Martini
    tile = tile.T

    if tile is None:
        return ("EMPTY", "text/plain", "empty tiles")

    bounds = mercantile.bounds(mercantile.Tile(x, y, z))
    mesh_max_error = float(mesh_max_error)

    if use_delatin:
        tin = Delatin(tile, max_error=mesh_max_error)
        vertices, triangles = tin.vertices, tin.triangles.flatten()
        rescaled = delatin_rescale_positions(vertices, bounds, flip_y=flip_y)

    else:
        martini = Martini(tile_size + 1)
        mar_tile = martini.create_tile(tile)

        vertices, triangles = mar_tile.get_mesh(mesh_max_error)
        rescaled = martini_rescale_positions(vertices, tile, bounds=bounds, flip_y=flip_y)

    with BytesIO() as f:
        quantized_mesh_encoder.encode(f, rescaled, triangles)
        f.seek(0)
        return ("OK", "application/vnd.quantized-mesh", f.read())


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
