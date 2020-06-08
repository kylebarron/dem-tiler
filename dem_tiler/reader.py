import numpy as np
import rasterio
from boto3.session import Session as boto3_session
from pymartini import decode_ele
from rasterio.session import AWSSession
from rio_tiler.io.cogeo import tile as cogeoTiler
from rio_tiler.utils import mapzen_elevation_rgb
from rio_tiler_mosaic.methods import defaults
from rio_tiler_mosaic.mosaic import mosaic_tiler

from cogeo_mosaic.backends import MosaicBackend
from dem_tiler.utils import _find_geotiff_assets, _find_terrarium_assets

session = boto3_session()
s3_client = session.client("s3")
aws_session = AWSSession(session=session)

PIXSEL_METHODS = {
    "first": defaults.FirstMethod,
    "highest": defaults.HighestMethod,
    "lowest": defaults.LowestMethod,
    "mean": defaults.MeanMethod,
    "median": defaults.MedianMethod,
    "stdev": defaults.StdevMethod}


def find_assets(x, y, z, mosaic_url, tile_size):
    """Find assets for input

    Args:
        - x: OSM tile index
        - y: OSM tile index
        - z: OSM tile index
        - mosaic_url: either url to MosaicJSON file, or the strings "terrarium" or "geotiff" to load terrarium or geotiff tiles from AWS Terrain Tiles
        - tile_size, one of 256, 258, 512, 514
    """
    if mosaic_url == 'terrarium':
        return _find_terrarium_assets(x, y, z, tile_size)

    if mosaic_url == 'geotiff':
        return _find_geotiff_assets(x, y, z, tile_size)

    with MosaicBackend(mosaic_url) as mosaic:
        return mosaic.tile(x, y, z)


# tile_size = 258
# assets = _find_terrarium_assets(x, y, z, tile_size)
# asset = assets[0]
# data = rasterio.open(asset).read()
# data = r.read()
# data.shape
# arrays = [rasterio.open(asset).read() for asset in assets]
# arrays[0]
# len(arrays)
# for asset in
# r = rasterio.open(assets)
# data = r.read()
# center, left, bottom, right, top = arrays


def backfill_arrays(center, left=None, bottom=None, right=None, top=None):
    if left is None or bottom is None or right is None or top is None:
        return center

    new_shape = center.shape[0], center.shape[1] + 2, center.shape[2] + 2
    new_arr = np.zeros(new_shape, center.dtype)

    # Copy center into center of new array
    np.copyto(new_arr[:, 1:-1, 1:-1], center)

    # fill left
    new_arr[:, 1:-1, :1] = left[:, :, -1:]

    # fill right
    new_arr[:, 1:-1, -1:] = right[:, :, :1]

    # fill bottom
    new_arr[:, -1:, 1:-1] = bottom[:, :1, :]

    # fill top
    new_arr[:, :1, 1:-1] = top[:, -1:, :]

    # fill corners. For now just backfill diagonally
    new_arr[:, 0, 0] = new_arr[:, 1, 1]
    new_arr[:, -1, 0] = new_arr[:, -2, 1]
    new_arr[:, 0, -1] = new_arr[:, 1, -2]
    new_arr[:, -1, -1] = new_arr[:, -2, -2]

    return new_arr


def load_assets(
        x,
        y,
        z,
        assets,
        tile_size,
        input_format: str = None,
        output_format: str = None,
        backfill: bool = False,
        pixel_selection: str = 'first',
        resampling_method: str = "nearest"):

    if input_format == 'terrarium':
        arrays = [rasterio.open(asset).read() for asset in assets]
        backfilled = backfill_arrays(*arrays)

        if output_format == 'terrarium':
            return backfilled

        data = decode_ele(backfilled, 'terrarium', backfill=backfill)

    elif input_format == 'geotiff':
        arrays = [rasterio.open(asset).read() for asset in assets]
        data = backfill_arrays(*arrays)

    else:
        with rasterio.Env(aws_session):
            pixsel_method = PIXSEL_METHODS[pixel_selection]
            data, _ = mosaic_tiler(
                assets,
                x,
                y,
                z,
                cogeoTiler,
                tilesize=tile_size,
                pixel_selection=pixsel_method(),
                resampling_method=resampling_method,
            )

    if output_format == 'terrarium':
        return mapzen_elevation_rgb(data)

    return data
