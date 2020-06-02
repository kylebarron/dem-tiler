import rasterio
from boto3.session import Session as boto3_session
from rasterio.session import AWSSession
from rio_tiler.io.cogeo import tile as cogeoTiler
from rio_tiler_mosaic.methods import defaults
from rio_tiler_mosaic.mosaic import mosaic_tiler

from cogeo_mosaic.backends import MosaicBackend
from dem_mosaic_tiler.utils import get_aws_terrain_url

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

def tile_assets(
        x,
        y,
        z,
        url,
        tile_size,
        pixel_selection: str = 'first',
        resampling_method: str = "nearest"):

    if url in ['terrarium', 'geotiff']:
        assets = get_aws_terrain_url(x, y, z, dataset='terrarium')
    else:
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
