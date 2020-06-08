# dem-tiler

Work in progress

A fork of [`cogeo-mosaic-tiler`][cogeo-mosaic-tiler] to serve elevation products
on demand from a mosaic of Cloud-Optimized GeoTIFF elevation data.

[cogeo-mosaic-tiler]: https://github.com/developmentseed/cogeo-mosaic-tiler

## Overview

### Input Formats

#### AWS Terrain Tiles

[AWS Terrain Tiles][aws-terrain-tiles] is an open dataset on S3 with global
elevation data in the Web Mercator projection. This makes it easy to use as an
input format, and is the fastest input format available.

[aws-terrain-tiles]: https://registry.opendata.aws/terrain-tiles/

#### COG MosaicJSON

[MosaicJSON][mosaicjson] of [Cloud-Optimized GeoTIFF][cogeo] (COG) files.

The USGS has recently put almost [all their elevation files][usgs-dem-cog] in
COG format. Additionally, the USGS plans to complete 1-meter DEMs of the entire
continental U.S. by the end of 2023, and all these files are created in COG
format. See [`usgs-dem-mosaic`][usgs-dem-mosaic] (WIP) for instructions on
creating a MosaicJSON of USGS COGs.

[usgs-dem-mosaic]: https://github.com/kylebarron/usgs-dem-mosaic
[usgs-dem-cog]: https://www.usgs.gov/news/usgs-digital-elevation-models-dem-switching-new-distribution-format
[mosaicjson]: https://github.com/developmentseed/mosaicjson-spec
[cogeo]: https://cogeo.org

### Output Formats

#### Terrain RGB

Encodes raw elevation values into a PNG, using the red, green, and blue channels
for a high bit depth. The [`terrarium` encoding][terrarium-encoding] has
3-millimeter precision and the [`mapbox` encoding][terrain-rgb-encoding] (not
yet implemented) has 10-centimeter precision.

If you plan to use AWS terrain tiles as the input format, and don't plan to add
a buffer to the tile, there's no reason to use this package, and you should
access the public tiles directly.

[terrarium-encoding]: https://github.com/tilezen/joerd/blob/master/docs/formats.md#terrarium
[terrain-rgb-encoding]: https://docs.mapbox.com/help/troubleshooting/access-elevation-data/#mapbox-terrain-rgb

##### Extra buffer

Can export PNG images of size 258x258 pixels or 518x518px, i.e. an extra 1-pixel
border around the normal 256 or 512-pixel tile. This is helpful for client-side
slope computations, where you need a 1 pixel border around the tile.

#### Contours

Uses [`gdal_contour`][gdal-contour] and [`tippecanoe`][tippecanoe] to provide
Mapbox Vector Tiles of elevation contours on demand. Contours can be generated
at an arbitrary interval, and can be shown in either meters or feet.

[gdal-contour]: https://gdal.org/programs/gdal_contour.html
[tippecanoe]: https://github.com/mapbox/tippecanoe

#### Quantized Mesh

[Quantized Mesh][quantized-mesh-spec] is a file format for terrain meshes, ideal
for transport to the browser for 3D terrain rendering. This output format uses
[`pymartini`][pymartini] for fast mesh generation from a raster heightmap, and
then [`quantized-mesh-encoder`][quantized-mesh-encoder] to encode the mesh.

[quantized-mesh-spec]: https://github.com/CesiumGS/quantized-mesh
[pymartini]: https://github.com/kylebarron/pymartini
[quantized-mesh-encoder]: https://github.com/kylebarron/quantized-mesh-encoder

## Deploy

#### Package Lambda

Create the AWS Lambda deployment package

```bash
make package
```

#### Deploy to AWS

This project uses [Serverless](https://serverless.com) to manage deploy on AWS.

If you plan to use AWS Terrain Tiles as input data, you should deploy to
`us-east-1` for minimal latency. If you plan to use USGS COGs as input data, you
should deploy to `us-west-2` for minimal latency. If you plan to use both, it
may be wise to deploy to both regions and switch between them depending on the
data source for the request.

```bash
# Install and Configure serverless (https://serverless.com/framework/docs/providers/aws/guide/credentials/)
$ npm install serverless -g

$ sls deploy --region us-east-1 --bucket a-bucket-where-you-store-data
```
