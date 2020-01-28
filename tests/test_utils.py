"""tests cogeo_mosaic.utils."""

import os
import re
import json

import pytest
from mock import patch

from cogeo_mosaic_tiler import utils
from cogeo_mosaic.utils import _decompress_gz

mosaic_json = os.path.join(os.path.dirname(__file__), "fixtures", "mosaic.json")


@pytest.fixture(autouse=True)
def testing_env_var(monkeypatch):
    """Set fake env to make sure we don't hit AWS services."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "jqt")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "rde")
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.setenv("AWS_CONFIG_FILE", "/tmp/noconfigheere")
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", "/tmp/noconfighereeither")
    monkeypatch.setenv("GDAL_DISABLE_READDIR_ON_OPEN", "TRUE")


def test_compress():
    """Test valid gz compression."""
    with open(mosaic_json, "r") as f:
        mosaic = json.loads(f.read())

    body = utils._compress_gz_json(mosaic)
    assert type(body) == bytes
    res = json.loads(_decompress_gz(body))
    assert res == mosaic


@patch("cogeo_mosaic_tiler.utils.boto3_session")
def test_aws_put_data_valid(session):
    """Create a file on S3."""
    session.return_value.client.return_value.put_object.return_value = True

    body = b"1111111"
    bucket = "my-bucket"
    key = "myfile.json.gz"

    res = utils._aws_put_data(key, bucket, body)
    session.assert_called_once()
    assert res == key


def test_hash():
    """Should return a 56 characters long string."""
    hash = utils.get_hash(a=1)
    assert re.match(r"[0-9A-Fa-f]{56}", hash)
