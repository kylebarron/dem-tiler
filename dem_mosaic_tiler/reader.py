import numpy as np
import rasterio
from boto3.session import Session as boto3_session
from pymartini import decode_ele
from rasterio.session import AWSSession
from rio_tiler.io.cogeo import tile as cogeoTiler
from rio_tiler_mosaic.methods import defaults
from rio_tiler_mosaic.mosaic import mosaic_tiler

from cogeo_mosaic.backends import MosaicBackend
from dem_mosaic_tiler.utils import _find_geotiff_assets, _find_terrarium_assets

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
        - tile_size, one of 256, 260, 512, 516
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


def backfill_arrays(center, left, bottom, right, top):
    new_shape = center.shape[0], center.shape[1] + 2, center.shape[2] + 2
    new_arr = np.zeros(new_shape, center.dtype)

    # Copy center into center of new array
    np.copyto(new_arr[:, 1:-1, 1:-1], center)

    # fill left
    new_arr[:, 1:-1, :1] = left[:, :, -1:]

    # fill right
    new_arr[:, 1:-1, -1:] = right[:, :, :1]

    # TODO: make sure these two are correct. Looks a little discontinuous
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


def tile_assets(
        x,
        y,
        z,
        url,
        tile_size,
        pixel_selection: str = 'first',
        resampling_method: str = "nearest"):

    if url in ['terrarium', 'geotiff']:
        return load_aws_terrain(x, y, z, dataset=url)

    with MosaicBackend(url) as mosaic:
        assets = mosaic.tile(x, y, z)

    if not assets:
        return None, None

    with rasterio.Env(aws_session):
        pixsel_method = PIXSEL_METHODS[pixel_selection]
        return mosaic_tiler(
            assets,
            x,
            y,
            z,
            cogeoTiler,
            tilesize=tile_size,
            pixel_selection=pixsel_method(),
            resampling_method=resampling_method,
        )


def load_aws_terrain(x, y, z, dataset):
    assets = get_aws_terrain_url(x, y, z, dataset)
    r = rasterio.open(assets)
    data = r.read()

    if dataset == 'terrarium':
        data = decode_ele(data, 'terrarium')
        decode_ele(data, 'terrarium', backfill=False).shape

    return data, None
