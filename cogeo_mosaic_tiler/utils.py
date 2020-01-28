"""cogeo_mosaic.utils: utility functions."""

from typing import Any, Dict, BinaryIO

import os
import zlib
import json
import logging
import hashlib

from boto3.session import Session as boto3_session


logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _compress_gz_json(data):
    gzip_compress = zlib.compressobj(9, zlib.DEFLATED, zlib.MAX_WBITS | 16)

    return (
        gzip_compress.compress(json.dumps(data).encode("utf-8")) + gzip_compress.flush()
    )


def _aws_put_data(
    key: str,
    bucket: str,
    body: BinaryIO,
    options: Dict = {},
    client: boto3_session.client = None,
) -> str:
    if not client:
        session = boto3_session()
        client = session.client("s3")
    client.put_object(Bucket=bucket, Key=key, Body=body, **options)
    return key


def get_hash(**kwargs: Any) -> str:
    """Create hash from a dict."""
    return hashlib.sha224(
        json.dumps(kwargs, sort_keys=True, default=str).encode()
    ).hexdigest()


def _create_path(mosaicid: str) -> str:
    """Get Mosaic definition info."""
    key = f"mosaics/{mosaicid}.json.gz"
    bucket = os.environ["MOSAIC_DEF_BUCKET"]
    return f"s3://{bucket}/{key}"
