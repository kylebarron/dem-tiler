"""cogeo-mosaic-tiler: utility functions."""

from urllib.parse import urlparse

import numpy
from boto3.session import Session as boto3_session
from botocore.exceptions import ClientError
from rio_color.operations import parse_operations
from rio_color.utils import scale_dtype, to_math_type
from rio_tiler.utils import linear_rescale


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
