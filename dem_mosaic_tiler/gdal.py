import json
from pathlib import Path
from subprocess import run

from geojson import FeatureCollection
from osgeo import gdal, gdal_array, ogr, osr


def arr_to_gdal_image(
        arr, gdal_transform, dtype=None, projection=None, nodata=None):
    """

    Args:
        - arr: single-band numpy array, of shape (x, y), e.g. (256, 256)
        - dtype: numpy dtype. If None, inferred from arr
        - gdal_transform: GDAL geogdal_transform. Default `(0, 1, 0, 0, 0, 1)` (Identity matrix I think)
        - projection: Defaults to EPSG 3857 (Web Mercator)
        - nodata: nodata value
    """
    if len(arr.shape) != 2:
        raise ValueError('arr.shape must be 2')

    y_res, x_res = arr.shape
    driver = gdal.GetDriverByName('MEM')

    if not dtype:
        dtype = arr.dtype

    gdal_dtype = gdal_array.NumericTypeCodeToGDALTypeCode(dtype)
    image = driver.Create('memory_filename', x_res, y_res, 1, gdal_dtype)

    image.SetGeoTransform(gdal_transform)

    if projection is None:
        gdal_projection = osr.SpatialReference()
        gdal_projection.ImportFromEPSG(3857)
        projection = gdal_projection.ExportToWkt()

    image.SetProjection(projection)

    # Write band
    band = image.GetRasterBand(1)
    if nodata is not None:
        band.SetNoDataValue(nodata)

    band.WriteArray(arr)
    band.FlushCache()
    return image


def create_contour(gdal_image):
    """
    Ref:
    https://github.com/OSGeo/gdal/blob/3554675bbce8dc00030bac33c99d92764d0f3844/autotest/alg/contour.py#L88-L97
    """
    ogr_ds = ogr.GetDriverByName('Memory').CreateDataSource('memory_filename')
    ogr_lyr = ogr_ds.CreateLayer('contour')
    field_defn = ogr.FieldDefn('ID', ogr.OFTInteger)
    ogr_lyr.CreateField(field_defn)
    field_defn = ogr.FieldDefn('elev', ogr.OFTReal)
    ogr_lyr.CreateField(field_defn)

    gdal.ContourGenerate(
        gdal_image.GetRasterBand(1), 10, 0, [], 0, 0, ogr_lyr, 0, 1)

    features = []
    for i in range(ogr_lyr.GetFeatureCount()):
        features.append(json.loads(ogr_lyr.GetFeature(i).ExportToJson()))

    # Not sure if these are needed
    # del gdal_image
    # del ogr_ds

    return features


def run_tippecanoe(features, x, y, z, path='.'):
    path = Path('.').resolve()
    fc = FeatureCollection(features)

    cmd = f'tippecanoe -R "{z}/{x}/{y}" -f -e {str(path)}'
    run(cmd, input=json.dumps(fc).encode('utf-8'), check=True, shell=True)

    # Load and return mvt
    mvt_path = path / str(z) / str(x) / f'{y}.pbf'
    with open(mvt_path, 'rb') as f:
        return f.read()
