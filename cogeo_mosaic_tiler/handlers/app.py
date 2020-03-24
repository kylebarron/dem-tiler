"""cogeo_mosaic_tiler.handlers.app: handle request for cogeo-mosaic-tiler endpoints."""

from typing import Any, BinaryIO, Tuple, Union

import os
import json
import urllib

import numpy

from boto3.session import Session as boto3_session
from botocore.errorfactory import ClientError

import mercantile
import rasterio
from rasterio.session import AWSSession
from rasterio.transform import from_bounds

from rio_color.utils import scale_dtype, to_math_type
from rio_color.operations import parse_operations

from rio_tiler.colormap import get_colormap
from rio_tiler.io.cogeo import tile as cogeoTiler
from rio_tiler.profiles import img_profiles
from rio_tiler.utils import render, linear_rescale

from rio_tiler_mvt.mvt import encoder as mvtEncoder
from rio_tiler_mosaic.mosaic import mosaic_tiler
from rio_tiler_mosaic.methods import defaults

from cogeo_mosaic import version as mosaic_version
from cogeo_mosaic.utils import (
    create_mosaic,
    fetch_mosaic_definition,
    fetch_and_find_assets,
    fetch_and_find_assets_point,
    get_point_values,
)

from cogeo_mosaic_tiler import custom_methods
from cogeo_mosaic_tiler.custom_cmaps import get_custom_cmap
from cogeo_mosaic_tiler.ogc import wmts_template
from cogeo_mosaic_tiler.utils import (
    _aws_put_data,
    _create_path,
    _compress_gz_json,
    get_hash,
)

from lambda_proxy.proxy import API

session = boto3_session()
s3_client = session.client("s3")
aws_session = AWSSession(session=session)

PIXSEL_METHODS = {
    "first": defaults.FirstMethod,
    "highest": defaults.HighestMethod,
    "lowest": defaults.LowestMethod,
    "mean": defaults.MeanMethod,
    "median": defaults.MedianMethod,
    "stdev": defaults.StdevMethod,
    "bdix_stdev": custom_methods.bidx_stddev,
}
app = API(name="cogeo-mosaic-tiler")


def _get_layer_names(src_dst):
    def _get_name(ix):
        name = src_dst.descriptions[ix - 1]
        if not name:
            name = f"band{ix}"
        return name

    return [_get_name(ix) for ix in src_dst.indexes]


@app.route(
    "/create",
    methods=["POST"],
    cors=True,
    payload_compression_method="gzip",
    binary_b64encode=True,
    tag=["mosaic"],
)
def _create(
    body: str,
    minzoom: Union[str, int] = None,
    maxzoom: Union[str, int] = None,
    min_tile_cover: Union[str, float] = None,
    tile_cover_sort: Union[str, bool] = False,
    tile_format: str = None,
    tile_scale: Union[str, int] = 1,
    **kwargs: Any,
) -> Tuple[str, str, str]:
    minzoom = int(minzoom) if isinstance(minzoom, str) else minzoom
    maxzoom = int(maxzoom) if isinstance(maxzoom, str) else maxzoom
    min_tile_cover = (
        float(min_tile_cover) if isinstance(min_tile_cover, float) else min_tile_cover
    )

    mosaicid = get_hash(body=body, version=mosaic_version)

    try:
        mosaic_definition = fetch_mosaic_definition(_create_path(mosaicid))
    except ClientError:
        body = json.loads(body)
        with rasterio.Env(aws_session):
            mosaic_definition = create_mosaic(
                body,
                minzoom=minzoom,
                maxzoom=maxzoom,
                minimum_tile_cover=min_tile_cover,
                tile_cover_sort=tile_cover_sort,
            )

            key = f"mosaics/{mosaicid}.json.gz"
            bucket = os.environ["MOSAIC_DEF_BUCKET"]
            _aws_put_data(
                key, bucket, _compress_gz_json(mosaic_definition), client=s3_client
            )

    if tile_format in ["pbf", "mvt"]:
        tile_url = f"{app.host}/{mosaicid}/{{z}}/{{x}}/{{y}}.{tile_format}"
    elif tile_format in ["png", "jpg", "webp", "tif", "npy"]:
        tile_url = (
            f"{app.host}/{mosaicid}/{{z}}/{{x}}/{{y}}@{tile_scale}x.{tile_format}"
        )
    else:
        tile_url = f"{app.host}/{mosaicid}/{{z}}/{{x}}/{{y}}@{tile_scale}x"

    qs = urllib.parse.urlencode(list(kwargs.items()))
    if qs:
        tile_url += f"?{qs}"

    meta = {
        "bounds": mosaic_definition["bounds"],
        "center": mosaic_definition["center"],
        "maxzoom": mosaic_definition["maxzoom"],
        "minzoom": mosaic_definition["minzoom"],
        "name": mosaicid,
        "tilejson": "2.1.0",
        "tiles": [tile_url],
    }

    return ("OK", "application/json", json.dumps(meta))


@app.route(
    "/add",
    methods=["POST"],
    cors=True,
    payload_compression_method="gzip",
    binary_b64encode=True,
    tag=["mosaic"],
)
def _add(body: str, mosaicid: str = None) -> Tuple[str, str, str]:
    # TODO: Need validation
    mosaic_definition = json.loads(body)

    if not mosaicid:
        mosaicid = get_hash(body=body)

    key = f"mosaics/{mosaicid}.json.gz"
    bucket = os.environ["MOSAIC_DEF_BUCKET"]
    _aws_put_data(key, bucket, _compress_gz_json(mosaic_definition), client=s3_client)

    return (
        "OK",
        "application/json",
        json.dumps({"id": mosaicid, "url": f"s3://{bucket}/{key}"}),
    )


@app.route(
    "/info",
    methods=["GET"],
    cors=True,
    payload_compression_method="gzip",
    binary_b64encode=True,
    tag=["metadata"],
)
@app.route(
    "/<regex([0-9A-Fa-f]{56}):mosaicid>/info",
    methods=["GET"],
    cors=True,
    payload_compression_method="gzip",
    binary_b64encode=True,
    tag=["metadata"],
)
def _info(mosaicid: str = None, url: str = None) -> Tuple[str, str, str]:
    """Handle /info requests."""
    if mosaicid:
        url = _create_path(mosaicid)
    elif url is None:
        return ("NOK", "text/plain", "Missing 'URL' parameter")

    mosaic_def = fetch_mosaic_definition(url)

    bounds = mosaic_def["bounds"]
    center = [
        (bounds[0] + bounds[2]) / 2,
        (bounds[1] + bounds[3]) / 2,
        mosaic_def["minzoom"],
    ]
    quadkeys = list(mosaic_def["tiles"].keys())

    # read layernames from the first file
    src_path = mosaic_def["tiles"][quadkeys[0]][0]
    with rasterio.open(src_path) as src_dst:
        layer_names = _get_layer_names(src_dst)
        dtype = src_dst.dtypes[0]

    meta = {
        "bounds": bounds,
        "center": center,
        "maxzoom": mosaic_def["maxzoom"],
        "minzoom": mosaic_def["minzoom"],
        "name": mosaicid if mosaicid else url,
        "quadkeys": quadkeys,
        "layers": layer_names,
        "dtype": dtype,
    }
    return ("OK", "application/json", json.dumps(meta))


@app.route(
    "/geojson",
    methods=["GET"],
    cors=True,
    payload_compression_method="gzip",
    binary_b64encode=True,
    tag=["metadata"],
)
@app.route(
    "/<regex([0-9A-Fa-f]{56}):mosaicid>/geojson",
    methods=["GET"],
    cors=True,
    payload_compression_method="gzip",
    binary_b64encode=True,
    tag=["metadata"],
)
def _geojson(mosaicid: str = None, url: str = None) -> Tuple[str, str, str]:
    """Handle /geojson requests."""
    if mosaicid:
        url = _create_path(mosaicid)
    elif url is None:
        return ("NOK", "text/plain", "Missing 'URL' parameter")

    mosaic_def = fetch_mosaic_definition(url)
    geojson = {
        "type": "FeatureCollection",
        "features": [
            mercantile.feature(mercantile.quadkey_to_tile(qk), props=dict(files=files))
            for qk, files in mosaic_def["tiles"].items()
        ],
    }

    return ("OK", "application/json", json.dumps(geojson))


@app.route(
    "/tilejson.json",
    methods=["GET"],
    cors=True,
    payload_compression_method="gzip",
    binary_b64encode=True,
    tag=["tiles"],
)
@app.route(
    "/<regex([0-9A-Fa-f]{56}):mosaicid>/tilejson.json",
    methods=["GET"],
    cors=True,
    payload_compression_method="gzip",
    binary_b64encode=True,
    tag=["tiles"],
)
def _tilejson(
    mosaicid: str = None,
    url: str = None,
    tile_scale: int = 1,
    tile_format: str = None,
    **kwargs: Any,
) -> Tuple[str, str, str]:
    """Handle /tilejson.json requests."""
    if mosaicid:
        url = _create_path(mosaicid)
    elif url is None:
        return ("NOK", "text/plain", "Missing 'URL' parameter")

    mosaic_def = fetch_mosaic_definition(url)

    bounds = mosaic_def["bounds"]
    center = [
        (bounds[0] + bounds[2]) / 2,
        (bounds[1] + bounds[3]) / 2,
        mosaic_def["minzoom"],
    ]
    if not mosaicid:
        kwargs.update(dict(url=url))
        host = app.host
    else:
        host = f"{app.host}/{mosaicid}"

    if tile_format in ["pbf", "mvt"]:
        tile_url = f"{host}/{{z}}/{{x}}/{{y}}.{tile_format}"
    elif tile_format in ["png", "jpg", "webp", "tif", "npy"]:
        tile_url = f"{host}/{{z}}/{{x}}/{{y}}@{tile_scale}x.{tile_format}"
    else:
        tile_url = f"{host}/{{z}}/{{x}}/{{y}}@{tile_scale}x"

    qs = urllib.parse.urlencode(list(kwargs.items()))
    if qs:
        tile_url += f"?{qs}"

    meta = {
        "bounds": bounds,
        "center": center,
        "maxzoom": mosaic_def["maxzoom"],
        "minzoom": mosaic_def["minzoom"],
        "name": url,
        "tilejson": "2.1.0",
        "tiles": [tile_url],
    }
    return ("OK", "application/json", json.dumps(meta))


@app.route(
    "/wmts",
    methods=["GET"],
    cors=True,
    payload_compression_method="gzip",
    binary_b64encode=True,
    tag=["tiles"],
)
@app.route(
    "/<regex([0-9A-Fa-f]{56}):mosaicid>/wmts",
    methods=["GET"],
    cors=True,
    payload_compression_method="gzip",
    binary_b64encode=True,
    tag=["tiles"],
)
def _wmts(
    mosaicid: str = None,
    url: str = None,
    tile_format: str = "png",
    tile_scale: int = 1,
    title: str = "Cloud Optimizied GeoTIFF Mosaic",
    **kwargs: Any,
) -> Tuple[str, str, str]:
    """Handle /wmts requests."""
    if mosaicid:
        url = _create_path(mosaicid)
    elif url is None:
        return ("NOK", "text/plain", "Missing 'URL' parameter")

    if tile_scale is not None and isinstance(tile_scale, str):
        tile_scale = int(tile_scale)

    mosaic_def = fetch_mosaic_definition(url)

    kwargs.pop("SERVICE", None)
    kwargs.pop("REQUEST", None)
    kwargs.update(dict(url=url))
    query_string = urllib.parse.urlencode(list(kwargs.items()))
    query_string = query_string.replace(
        "&", "&amp;"
    )  # & is an invalid character in XML

    return (
        "OK",
        "application/xml",
        wmts_template(
            f"{app.host}",
            query_string,
            minzoom=mosaic_def["minzoom"],
            maxzoom=mosaic_def["maxzoom"],
            bounds=mosaic_def["bounds"],
            tile_scale=tile_scale,
            tile_format=tile_format,
            title=title,
        ),
    )


@app.route(
    "/<int:z>/<int:x>/<int:y>.pbf",
    methods=["GET"],
    cors=True,
    payload_compression_method="gzip",
    binary_b64encode=True,
    tag=["tiles"],
)
@app.route(
    "/<regex([0-9A-Fa-f]{56}):mosaicid>/<int:z>/<int:x>/<int:y>.pbf",
    methods=["GET"],
    cors=True,
    payload_compression_method="gzip",
    binary_b64encode=True,
    tag=["tiles"],
)
def _mvt(
    mosaicid: str = None,
    z: int = None,
    x: int = None,
    y: int = None,
    url: str = None,
    tile_size: Union[str, int] = 256,
    pixel_selection: str = "first",
    feature_type: str = "point",
    resampling_method: str = "nearest",
) -> Tuple[str, str, BinaryIO]:
    """Handle MVT requests."""
    if mosaicid:
        url = _create_path(mosaicid)
    elif url is None:
        return ("NOK", "text/plain", "Missing 'URL' parameter")

    assets = fetch_and_find_assets(url, x, y, z)
    if not assets:
        return ("EMPTY", "text/plain", f"No assets found for tile {z}-{x}-{y}")

    if tile_size is not None and isinstance(tile_size, str):
        tile_size = int(tile_size)

    if pixel_selection == "last":
        pixel_selection = "first"
        assets = list(reversed(assets))

    with rasterio.Env(aws_session):
        pixsel_method = PIXSEL_METHODS[pixel_selection]
        tile, mask = mosaic_tiler(
            assets,
            x,
            y,
            z,
            cogeoTiler,
            tilesize=tile_size,
            pixel_selection=pixsel_method(),
            resampling_method=resampling_method,
        )
        if tile is None:
            return ("EMPTY", "text/plain", "empty tiles")

        with rasterio.open(assets[0]) as src_dst:
            band_descriptions = _get_layer_names(src_dst)

        return (
            "OK",
            "application/x-protobuf",
            mvtEncoder(
                tile,
                mask,
                band_descriptions,
                os.path.basename(url),
                feature_type=feature_type,
            ),
        )


def _postprocess(
    tile: numpy.ndarray,
    mask: numpy.ndarray,
    rescale: str = None,
    color_formula: str = None,
) -> numpy.ndarray:
    """Tile data post processing."""
    if rescale:
        rescale_arr = (tuple(map(float, rescale.split(","))),) * tile.shape[0]
        for bdx in range(tile.shape[0]):
            tile[bdx] = numpy.where(
                mask,
                linear_rescale(
                    tile[bdx], in_range=rescale_arr[bdx], out_range=[0, 255]
                ),
                0,
            )
        tile = tile.astype(numpy.uint8)

    if color_formula:
        # make sure one last time we don't have
        # negative value before applying color formula
        tile[tile < 0] = 0
        for ops in parse_operations(color_formula):
            tile = scale_dtype(ops(to_math_type(tile)), numpy.uint8)

    return tile


@app.route(
    "/<int:z>/<int:x>/<int:y>.<ext>",
    methods=["GET"],
    cors=True,
    payload_compression_method="gzip",
    binary_b64encode=True,
    tag=["tiles"],
)
@app.route(
    "/<int:z>/<int:x>/<int:y>",
    methods=["GET"],
    cors=True,
    payload_compression_method="gzip",
    binary_b64encode=True,
    tag=["tiles"],
)
@app.route(
    "/<int:z>/<int:x>/<int:y>@<int:scale>x.<ext>",
    methods=["GET"],
    cors=True,
    payload_compression_method="gzip",
    binary_b64encode=True,
    tag=["tiles"],
)
@app.route(
    "/<int:z>/<int:x>/<int:y>@<int:scale>x",
    methods=["GET"],
    cors=True,
    payload_compression_method="gzip",
    binary_b64encode=True,
    tag=["tiles"],
)
@app.route(
    "/<regex([0-9A-Fa-f]{56}):mosaicid>/<int:z>/<int:x>/<int:y>.<ext>",
    methods=["GET"],
    cors=True,
    payload_compression_method="gzip",
    binary_b64encode=True,
    tag=["tiles"],
)
@app.route(
    "/<regex([0-9A-Fa-f]{56}):mosaicid>/<int:z>/<int:x>/<int:y>",
    methods=["GET"],
    cors=True,
    payload_compression_method="gzip",
    binary_b64encode=True,
    tag=["tiles"],
)
@app.route(
    "/<regex([0-9A-Fa-f]{56}):mosaicid>/<int:z>/<int:x>/<int:y>@<int:scale>x.<ext>",
    methods=["GET"],
    cors=True,
    payload_compression_method="gzip",
    binary_b64encode=True,
    tag=["tiles"],
)
@app.route(
    "/<regex([0-9A-Fa-f]{56}):mosaicid>/<int:z>/<int:x>/<int:y>@<int:scale>x",
    methods=["GET"],
    cors=True,
    payload_compression_method="gzip",
    binary_b64encode=True,
    tag=["tiles"],
)
def _img(
    mosaicid: str = None,
    z: int = None,
    x: int = None,
    y: int = None,
    scale: int = 1,
    ext: str = None,
    url: str = None,
    indexes: str = None,
    rescale: str = None,
    color_ops: str = None,
    color_map: str = None,
    pixel_selection: str = "first",
    resampling_method: str = "nearest",
) -> Tuple[str, str, BinaryIO]:
    """Handle tile requests."""
    if mosaicid:
        url = _create_path(mosaicid)
    elif url is None:
        return ("NOK", "text/plain", "Missing 'URL' parameter")

    assets = fetch_and_find_assets(url, x, y, z)
    if not assets:
        return ("EMPTY", "text/plain", f"No assets found for tile {z}-{x}-{y}")

    if indexes:
        indexes = list(map(int, indexes.split(",")))

    tilesize = 256 * scale

    if pixel_selection == "last":
        pixel_selection = "first"
        assets = list(reversed(assets))

    with rasterio.Env(aws_session):
        pixsel_method = PIXSEL_METHODS[pixel_selection]
        tile, mask = mosaic_tiler(
            assets,
            x,
            y,
            z,
            cogeoTiler,
            indexes=indexes,
            tilesize=tilesize,
            pixel_selection=pixsel_method(),
            resampling_method=resampling_method,
        )

    if tile is None:
        return ("EMPTY", "text/plain", "empty tiles")

    rtile = _postprocess(tile, mask, rescale=rescale, color_formula=color_ops)
    if color_map:
        if color_map.startswith("custom_"):
            color_map = get_custom_cmap(color_map)
        else:
            color_map = get_colormap(color_map, format="gdal")

    if not ext:
        ext = "jpg" if mask.all() else "png"

    driver = "jpeg" if ext == "jpg" else ext
    options = img_profiles.get(driver, {})

    if ext == "tif":
        ext = "tiff"
        driver = "GTiff"
        tile_bounds = mercantile.xy_bounds(mercantile.Tile(x=x, y=y, z=z))
        options = dict(
            crs={"init": "EPSG:3857"},
            transform=from_bounds(*tile_bounds, tilesize, tilesize),
        )

    return (
        "OK",
        f"image/{ext}",
        render(rtile, mask, img_format=driver, color_map=color_map, **options),
    )


@app.route(
    "/point",
    methods=["GET"],
    cors=True,
    payload_compression_method="gzip",
    binary_b64encode=True,
    tag=["tiles"],
)
@app.route(
    "/<regex([0-9A-Fa-f]{56}):mosaicid>/point",
    methods=["GET"],
    cors=True,
    payload_compression_method="gzip",
    binary_b64encode=True,
    tag=["tiles"],
)
def _point(
    mosaicid: str = None, lng: float = None, lat: float = None, url: str = None
) -> Tuple[str, str, str]:
    """Handle point requests."""
    if mosaicid:
        url = _create_path(mosaicid)
    elif url is None:
        return ("NOK", "text/plain", "Missing 'URL' parameter")

    if not lat or not lng:
        return ("NOK", "text/plain", "Missing 'Lon/Lat' parameter")

    if isinstance(lng, str):
        lng = float(lng)

    if isinstance(lat, str):
        lat = float(lat)

    assets = fetch_and_find_assets_point(url, lng, lat)
    if not assets:
        return ("EMPTY", "text/plain", f"No assets found for lat/lng ({lat}, {lng})")

    with rasterio.Env(aws_session):
        meta = {"coordinates": [lng, lat], "values": get_point_values(assets, lng, lat)}
        return ("OK", "application/json", json.dumps(meta))


@app.route("/favicon.ico", methods=["GET"], cors=True, tag=["other"])
def favicon() -> Tuple[str, str, str]:
    """Favicon."""
    return ("EMPTY", "text/plain", "")
