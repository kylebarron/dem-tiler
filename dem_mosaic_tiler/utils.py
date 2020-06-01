"""cogeo-mosaic-tiler: utility functions."""

from urllib.parse import urlparse

import numpy
from boto3.session import Session as boto3_session
from botocore.exceptions import ClientError
from rio_color.operations import parse_operations
from rio_color.utils import scale_dtype, to_math_type
from rio_tiler.utils import linear_rescale


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
