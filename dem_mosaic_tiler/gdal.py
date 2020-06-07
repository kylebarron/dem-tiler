import numpy as np
from osgeo import gdal, gdal_array, ogr, osr
from rasterio import Affine, MemoryFile, features
from rasterio.crs import CRS
from shapely.geometry import LineString, mapping, shape


def arr_to_gdal_image(
        arr, gdal_transform, dtype=None, projection=None,
        nodata=None):
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


def gdal_contour(input_image):
    # input_image = image

    band = input_image.GetRasterBand(1)
    dst_filename = asci + 'contour.shp'
    #Generate layer to save Contourlines in
    ogr_ds = ogr.GetDriverByName("GeoJSON").CreateDataSource(dst_filename)
    contour_shp = ogr_ds.CreateLayer('contour')

    field_defn = ogr.FieldDefn("ID", ogr.OFTInteger)
    contour_shp.CreateField(field_defn)
    field_defn = ogr.FieldDefn("elev", ogr.OFTReal)
    contour_shp.CreateField(field_defn)

    #Generate Contourlines
    gdal.ContourGenerate(in1, 0, 0, [-888], 0, 0, contour_shp, 0, 1)
    ogr_ds.Destroy()

    pass
