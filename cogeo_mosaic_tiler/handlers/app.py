"""cogeo_mosaic_tiler.handlers.app: handle request for cogeo-mosaic-tiler endpoints."""

import json
import os
import random
import urllib.parse
import warnings
from typing import Any, Optional, Sequence, Tuple, Union

import mercantile
import rasterio
from boto3.session import Session as boto3_session
from lambda_proxy.proxy import API
from rasterio.session import AWSSession
from rio_tiler.colormap import cmap
from rio_tiler.io.cogeo import tile as cogeoTiler
from rio_tiler.profiles import img_profiles
from rio_tiler.reader import multi_point
from rio_tiler.utils import geotiff_options, render
from rio_tiler_mosaic.methods import defaults
from rio_tiler_mosaic.mosaic import mosaic_tiler

from cogeo_mosaic import version as mosaic_version
from cogeo_mosaic.backends import MosaicBackend
from cogeo_mosaic.backends.utils import get_hash
from cogeo_mosaic.mosaic import MosaicJSON
from cogeo_mosaic_tiler import custom_cmaps, custom_methods
from cogeo_mosaic_tiler.ogc import wmts_template
from cogeo_mosaic_tiler.utils import _aws_head_object, _get_layer_names, _postprocess

cmap.register("custom_above", custom_cmaps.above_cmap)

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

params = dict(payload_compression_method="gzip", binary_b64encode=True)
if os.environ.get("CORS"):
    params["cors"] = True

# We are storing new mosaicjson on AWS S3, if a user wants to change the storage
# You could just change this function
# e.g
# def _create_mosaic_path(mosaicid: str,) -> str:
#     """Translate mosaicid to dynamoDB path."""
#     return f"dynamodb:///{mosaicid}"


def _create_mosaic_path(
    mosaicid: str,
    bucket: str = os.environ["MOSAIC_DEF_BUCKET"],
    prefix: str = os.environ.get("MOSAIC_PREFIX", "mosaics"),
) -> str:
    """Translate mosaicid to s3 path."""
    key = f"{prefix}/{mosaicid}.json.gz" if prefix else f"{mosaicid}.json.gz"
    return f"s3://{bucket}/{key}"


@app.post("/create", tag=["mosaic"], **params)
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
        float(min_tile_cover) if isinstance(min_tile_cover, str) else min_tile_cover
    )

    mosaicid = get_hash(
        body=body,
        minzoom=minzoom,
        maxzoom=maxzoom,
        min_tile_cover=min_tile_cover,
        tile_cover_sort=tile_cover_sort,
        version=mosaic_version,
    )
    try:
        with MosaicBackend(_create_mosaic_path(mosaicid), client=s3_client) as mosaic:
            meta = mosaic.metadata
    except:  # noqa
        body = json.loads(body)
        with rasterio.Env(aws_session):
            mosaic_definition = MosaicJSON.from_urls(
                body,
                minzoom=minzoom,
                maxzoom=maxzoom,
                minimum_tile_cover=min_tile_cover,
                tile_cover_sort=tile_cover_sort,
            )

        with MosaicBackend(
            _create_mosaic_path(mosaicid),
            mosaic_def=mosaic_definition,
            client=s3_client,
        ) as mosaic:
            mosaic.write()
            meta = mosaic.metadata

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
        "bounds": meta["bounds"],
        "center": meta["center"],
        "maxzoom": meta["maxzoom"],
        "minzoom": meta["minzoom"],
        "name": mosaicid,
        "tilejson": "2.1.0",
        "tiles": [tile_url],
    }

    return ("OK", "application/json", json.dumps(meta, separators=(",", ":")))


@app.post("/add", tag=["mosaic"], **params)
def _add(body: str, mosaicid: str) -> Tuple:
    if _aws_head_object(_create_mosaic_path(mosaicid), client=s3_client):
        return ("NOK", "text/plain", f"Mosaic: {mosaicid} already exist.")

    mosaic_definition = MosaicJSON(**json.loads(body))
    with MosaicBackend(
        _create_mosaic_path(mosaicid), mosaic_def=mosaic_definition
    ) as mosaic:
        mosaic.write()

    return (
        "OK",
        "application/json",
        json.dumps({"id": mosaicid, "status": "READY"}, separators=(",", ":")),
    )


params["cache_control"] = os.environ.get("CACHE_CONTROL", None)


@app.get("/info", tag=["metadata"], **params)
@app.get("/<regex([0-9A-Fa-f]{56}):mosaicid>/info", tag=["metadata"], **params)
def _info(mosaicid: str = None, url: str = None) -> Tuple:
    """Handle /info requests."""
    if not mosaicid and not url:
        return ("NOK", "text/plain", "Missing 'MosaicID or URL' parameter")

    mosaic_path = _create_mosaic_path(mosaicid) if mosaicid else url
    with MosaicBackend(mosaic_path) as mosaic:
        meta = mosaic.metadata
        response = {
            "bounds": meta["bounds"],
            "center": meta["center"],
            "maxzoom": meta["maxzoom"],
            "minzoom": meta["minzoom"],
            "name": mosaicid or url,
        }

        if not mosaic_path.startswith("dynamodb://"):
            mosaic_quadkeys = set(mosaic._quadkeys)
            tile = mercantile.quadkey_to_tile(random.sample(mosaic_quadkeys, 1)[0])
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

        return ("OK", "application/json", json.dumps(response, separators=(",", ":")))


@app.get("/geojson", tag=["metadata"], **params)
@app.get("/<regex([0-9A-Fa-f]{56}):mosaicid>/geojson", tag=["metadata"], **params)
def _geojson(mosaicid: str = None, url: str = None) -> Tuple:
    """Handle /geojson requests."""
    if not mosaicid and not url:
        return ("NOK", "text/plain", "Missing 'MosaicID or URL' parameter")

    mosaic_path = _create_mosaic_path(mosaicid) if mosaicid else url
    with MosaicBackend(mosaic_path) as mosaic:
        geojson = {
            "type": "FeatureCollection",
            "features": [
                mercantile.feature(
                    mercantile.quadkey_to_tile(qk), props=dict(files=files)
                )
                for qk, files in mosaic.mosaic_def.tiles.items()
            ],
        }

    return ("OK", "application/json", json.dumps(geojson, separators=(",", ":")))


params["tag"] = ["tiles"]


@app.get("/tilejson.json", **params)
@app.get("/<regex([0-9A-Fa-f]{56}):mosaicid>/tilejson.json", **params)
def _tilejson(
    mosaicid: str = None,
    url: str = None,
    tile_scale: int = 1,
    tile_format: str = None,
    **kwargs: Any,
) -> Tuple:
    """Handle /tilejson.json requests."""
    if not mosaicid and not url:
        return ("NOK", "text/plain", "Missing 'MosaicID or URL' parameter")

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

    mosaic_path = _create_mosaic_path(mosaicid) if mosaicid else url
    with MosaicBackend(mosaic_path) as mosaic:
        meta = mosaic.metadata
        response = {
            "bounds": meta["bounds"],
            "center": meta["center"],
            "maxzoom": meta["maxzoom"],
            "minzoom": meta["minzoom"],
            "name": mosaicid or url,
            "tilejson": "2.1.0",
            "tiles": [tile_url],
        }
    return ("OK", "application/json", json.dumps(response, separators=(",", ":")))


@app.get("/wmts", **params)
@app.get("/<regex([0-9A-Fa-f]{56}):mosaicid>/wmts", **params)
def _wmts(
    mosaicid: str = None,
    url: str = None,
    tile_format: str = "png",
    tile_scale: int = 1,
    title: str = "Cloud Optimizied GeoTIFF Mosaic",
    **kwargs: Any,
) -> Tuple:
    """Handle /wmts requests."""
    if not mosaicid and not url:
        return ("NOK", "text/plain", "Missing 'MosaicID or URL' parameter")

    if tile_scale is not None and isinstance(tile_scale, str):
        tile_scale = int(tile_scale)

    if not mosaicid:
        kwargs.update(dict(url=url))
        host = app.host
    else:
        host = f"{app.host}/{mosaicid}"

    query_string = urllib.parse.urlencode(list(kwargs.items()))
    query_string = query_string.replace(
        "&", "&amp;"
    )  # & is an invalid character in XML
    kwargs.pop("SERVICE", None)
    kwargs.pop("REQUEST", None)

    mosaic_path = _create_mosaic_path(mosaicid) if mosaicid else url
    with MosaicBackend(mosaic_path) as mosaic:
        meta = mosaic.metadata

        return (
            "OK",
            "application/xml",
            wmts_template(
                host,
                query_string,
                minzoom=meta["minzoom"],
                maxzoom=meta["maxzoom"],
                bounds=meta["bounds"],
                tile_scale=tile_scale,
                tile_format=tile_format,
                title=title,
            ),
        )


@app.get("/<int:z>/<int:x>/<int:y>.pbf", **params)
@app.get("/<regex([0-9A-Fa-f]{56}):mosaicid>/<int:z>/<int:x>/<int:y>.pbf", **params)
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
) -> Tuple:
    """Handle MVT requests."""
    from rio_tiler_mvt.mvt import encoder as mvtEncoder  # noqa

    if not mosaicid and not url:
        return ("NOK", "text/plain", "Missing 'MosaicID or URL' parameter")

    mosaic_path = _create_mosaic_path(mosaicid) if mosaicid else url
    with MosaicBackend(mosaic_path) as mosaic:
        assets = mosaic.tile(x, y, z)
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
                mosaicid or os.path.basename(url),
                feature_type=feature_type,
            ),
        )


@app.get("/<int:z>/<int:x>/<int:y>.<ext>", **params)
@app.get("/<int:z>/<int:x>/<int:y>", **params)
@app.get("/<int:z>/<int:x>/<int:y>@<int:scale>x.<ext>", **params)
@app.get("/<int:z>/<int:x>/<int:y>@<int:scale>x", **params)
@app.get("/<regex([0-9A-Fa-f]{56}):mosaicid>/<int:z>/<int:x>/<int:y>.<ext>", **params)
@app.get("/<regex([0-9A-Fa-f]{56}):mosaicid>/<int:z>/<int:x>/<int:y>", **params)
@app.get(
    "/<regex([0-9A-Fa-f]{56}):mosaicid>/<int:z>/<int:x>/<int:y>@<int:scale>x.<ext>",
    **params,
)
@app.get(
    "/<regex([0-9A-Fa-f]{56}):mosaicid>/<int:z>/<int:x>/<int:y>@<int:scale>x", **params
)
def _img(
    mosaicid: str = None,
    z: int = None,
    x: int = None,
    y: int = None,
    scale: int = 1,
    ext: str = None,
    url: str = None,
    indexes: Optional[Sequence[int]] = None,
    rescale: str = None,
    color_ops: str = None,
    color_map: str = None,
    pixel_selection: str = "first",
    resampling_method: str = "nearest",
) -> Tuple:
    """Handle tile requests."""
    if not mosaicid and not url:
        return ("NOK", "text/plain", "Missing 'MosaicID or URL' parameter")

    mosaic_path = _create_mosaic_path(mosaicid) if mosaicid else url
    with MosaicBackend(mosaic_path) as mosaic:
        assets = mosaic.tile(x, y, z)
        if not assets:
            return ("EMPTY", "text/plain", f"No assets found for tile {z}-{x}-{y}")

    if indexes is not None and isinstance(indexes, str):
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

    if not ext:
        ext = "jpg" if mask.all() else "png"

    driver = "jpeg" if ext == "jpg" else ext
    options = img_profiles.get(driver, {})

    if color_map:
        options["colormap"] = cmap.get(color_map)

    if ext == "tif":
        ext = "tiff"
        driver = "GTiff"
        options = geotiff_options(x, y, z, tilesize)

    return (
        "OK",
        f"image/{ext}",
        render(rtile, mask, img_format=driver, **options),
    )


@app.get("/point", **params)
@app.get("/<regex([0-9A-Fa-f]{56}):mosaicid>/point", **params)
def _point(
    mosaicid: str = None, lng: float = None, lat: float = None, url: str = None
) -> Tuple[str, str, str]:
    """Handle point requests."""
    if not mosaicid and not url:
        return ("NOK", "text/plain", "Missing 'MosaicID or URL' parameter")

    if not lat or not lng:
        return ("NOK", "text/plain", "Missing 'Lon/Lat' parameter")

    if isinstance(lng, str):
        lng = float(lng)

    if isinstance(lat, str):
        lat = float(lat)

    mosaic_path = _create_mosaic_path(mosaicid) if mosaicid else url
    with MosaicBackend(mosaic_path) as mosaic:
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
            "values": [
                {"asset": assets[ix], "values": value}
                for ix, value in enumerate(multi_point(assets, coordinates=(lng, lat)))
            ],
        }
        return ("OK", "application/json", json.dumps(meta, separators=(",", ":")))


@app.get("/favicon.ico", tag=["other"])
def favicon() -> Tuple[str, str, str]:
    """Favicon."""
    return ("EMPTY", "text/plain", "")
