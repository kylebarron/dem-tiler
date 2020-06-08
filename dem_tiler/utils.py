"""dem-tiler: utility functions."""

from urllib.parse import urlparse

from boto3.session import Session as boto3_session
from botocore.exceptions import ClientError


def _find_terrarium_assets(x, y, z, tile_size):
    # Terrarium has a max zoom level of 15, each tile is 256px
    if z >= 16:
        return None

    base_url = 's3://elevation-tiles-prod/terrarium'

    if tile_size == 256:
        return [f'{base_url}/{z}/{x}/{y}.png']

    if tile_size == 258:
        # center, left, bottom, right, top
        return [
            f'{base_url}/{z}/{x}/{y}.png',
            f'{base_url}/{z}/{x - 1}/{y}.png',
            f'{base_url}/{z}/{x}/{y + 1}.png',
            f'{base_url}/{z}/{x + 1}/{y}.png',
            f'{base_url}/{z}/{x}/{y - 1}.png']

    raise NotImplementedError(f'tile_size {tile_size} not implemented')


def _find_geotiff_assets(x, y, z, tile_size):
    # AWS GeoTIFF tiles have a max zoom level of 14, each tile is 512px
    if z >= 15:
        return None

    base_url = 's3://elevation-tiles-prod/geotiff'

    if tile_size == 512:
        return [f'{base_url}/{z}/{x}/{y}.png']

    raise NotImplementedError(f'tile_size {tile_size} not implemented')


def _get_layer_names(src_dst):
    def _get_name(ix):
        name = src_dst.descriptions[ix - 1]
        if not name:
            name = f"band{ix}"
        return name

    return [_get_name(ix) for ix in src_dst.indexes]


def _aws_head_object(url: str, client: boto3_session.client = None) -> bool:
    if not client:
        session = boto3_session()
        client = session.client("s3")

    parsed = urlparse(url)
    bucket = parsed.netloc
    key = parsed.path.strip("/")

    try:
        return client.head_object(Bucket=bucket, Key=key)
    except ClientError:
        return False
