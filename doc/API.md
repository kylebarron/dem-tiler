# API

Online API documentation can be found at `{endpoint}/docs`.

## mosaicJSON path

Every method to `cogeo-mosaic-tiler` accepts a `url` parameter, which allows for
describing the path to the MosaicJSON, and further allows using different
backends, such as an internet URL over HTTP, a file on S3, or a DynamoDB table.

```
https://{endpoint-url}/{method}?url={mosaicURL}
```

For example:

- S3:
    - `https://{endpoint-url}/{method}?url=s3://{bucket}/{key}`
- HTTP:
    - `https://{endpoint-url}/{method}?url=http(s)://example.com/path/to/mosaic`
- DynamoDB. If you don't pass a region, the local region is assumed. Note that if you don't pass a region you need _three_ `///`.
    - `https://{endpoint-url}/{method}?url=dynamodb://{AWS region}/{mosaicid}`
    - `https://{endpoint-url}/{method}?url=dynamodb:///{mosaicid}`
-  Local file. Note if you pass `file:///` you need _three_ `///`.
    - `https://{endpoint-url}/{method}?url=file:///path/to/local/file`
    - `https://{endpoint-url}/{method}?url=/path/to/local/file`
    - `https://{endpoint-url}/{method}?url=./relative/path/to/local/file`
    - `https://{endpoint-url}/{method}?url=relative/path/to/local/file`

Historically, a  **`mosaicid`** is a 56-character hexadecimal string (matching `[0-9A-Fa-f]{56}` regex), usually created using `sha224sum mymosaic.json.gz`.

```
$ cogeo-mosaic create mylist.txt -o mosaic.json.gz

$ sha224sum mosaic.json.gz
92979ccd7d443ff826e493e4af707220ba77f16def6f15db86141ba8  mosaic.json.gz
```

## Using mosaicid

Most of the `GET` requests support using **mosaicid** in the path (prefix) instead of passing an url. When using mosaicid, the tiler will reconscruct a file s3 url and then result to `s3://{bucket}/mosaics/mosaicid.json.gz`, with `{bucket}` set in the environment variable. 

```python
# https://github.com/developmentseed/cogeo-mosaic-tiler/blob/1bebcae6c3d8e5d726fc1ba55c40c79d23bdab15/cogeo_mosaic_tiler/handlers/app.py#L59-L66
def _create_mosaic_path(
    mosaicid: str,
    bucket: str = os.environ["MOSAIC_DEF_BUCKET"],
    prefix: str = os.environ.get("MOSAIC_PREFIX", "mosaics"),
) -> str:
    """Translate mosaicid to s3 path."""
    key = f"{prefix}/{mosaicid}.json.gz" if prefix else f"{mosaicid}.json.gz"
    return f"s3://{bucket}/{key}"
```

#### Example

```
$ curl https://{endpoint-url}/92979ccd7d443ff826e493e4af707220ba77f16def6f15db86141ba8/info
```
will give the same result as

```
$ curl https://{endpoint-url}/info?url=s3://{bucket}/mosaics/92979ccd7d443ff826e493e4af707220ba77f16def6f15db86141ba8.json.gz
```


## - Create MosaicJSON (Experimental)
`/create`

- methods:POST
- **body**
  - content: List of files
  - format: **json**
- returns: mosaic definition (application/json, compression: **gzip**)

Note: equivalent of running `cogeo-mosaic create` locally

```bash
$ curl -X POST -d @list.json https://{endpoint-url}/create`
```

## - Add MosaicJSON
`/add`

- methods:POST
- **body**
  - content: mosaicJSON (created by `cogeo-mosaic create`)
  - mosaicid: string matching `[0-9A-Fa-f]{56}` regex
  - format: **json**
- returns: mosaic info (application/json, compression: **gzip**)

```bash
$ curl -X POST -d @list.json https://{endpoint-url}/add`

{
  "id": "d4c05a130c8a336c6..........2cbc5c34aed85feffdaafd01ef", "status": "READY"
}
```

## - Mosaic Metadata

`/info`

- methods: GET
- **url** (in querytring): mosaic definition url
- returns: mosaic defintion info (application/json, compression: **gzip**)

```bash
$ curl https://{endpoint-url}/info?url=s3://my_bucket/my_mosaic.json.gz
```

```js
{
    "bounds": [],                // mosaic bounds
    "center": [lon, lat, zoom],     // mosaic center
    "maxzoom": 22,                  // mosaic max zoom
    "minzoom": 18,                  // mosaic min zoom
    "name": "0505ad234b5fb97df134001709b8a42eddce5d03b200eb8f7f4540d6", // mosaic basename
    "quadkeys": [],              // list of quakeys (not returned for dynamoDB backend)
    "layers": [] ,               // dataset band names (not returned for dynamoDB backend)
}
```

## - Mosaic GeoJSON

`/geojson`

- methods: GET
- **url** (in querytring): mosaic definition url
- returns: mosaic-json as geojson (application/json, compression: **gzip**)

```bash
$ curl https://{endpoint-url}/geojson?url=s3://my_bucket/my_mosaic.json.gz
```

```js
{
    "type":"FeatureCollection",
    "features":[
        {
            "type":"Feature",
            "bbox":[...],
            "id":"Tile(x=21, y=20, z=7)",
            "geometry":{
                "type":"Polygon",
                "coordinates":[[
                    ...
                ]]
            },
            "properties":{
                "title":"XYZ tile Tile(x=21, y=20, z=7)",
                "files":[]
            }
        }
        ...
    ]
}
```

## - TileJSON (2.1.0)

`/tilejson.json`

- methods: GET
- **url** (required): mosaic definition url
- **tile_format** (optional, str): output tile format (default: "png")
- **tile_scale** (optional, int): output tile scale (default: 1 = 256px)
- **kwargs** (in querytring): tiler options
- returns: tileJSON defintion (application/json, compression: **gzip**)

```bash
$ curl https://{endpoint-url}/tilejson.json?url=s3://my_bucket/my_mosaic.json.gz
```

```json
{
    "bounds": [],
    "center": [lon, lat, minzoom],
    "maxzoom": 22,
    "minzoom": 18,
    "name": "s3://my_bucket/my_mosaic.json.gz",
    "tilejson": "2.1.0",
    "tiles": [
        "https://{endpoint-url}/{{z}}/{{x}}/{{y}}@2x.<ext>"
    ],
}
```

## - OGC WMTS

`/wmts`

- methods: GET
- **url** (in querytring): mosaic definition url
- **tile_format** (optional, str): output tile format (default: "png")
- **tile_scale** (optional, int): output tile scale (default: 1 = 256px)
- **title** (optional, str): layer name (default: "Cloud Optimizied GeoTIFF Mosaic")
- **kwargs** (in querytring): tiler options
- returns: WMTS xml (application/xml, compression: **gzip**)

```bash
$ curl https://{endpoint-url}/wmts?url=s3://my_bucket/my_mosaic.json.gz
```

<details>

```xml
<Capabilities
        xmlns="http://www.opengis.net/wmts/1.0"
        xmlns:ows="http://www.opengis.net/ows/1.1"
        xmlns:xlink="http://www.w3.org/1999/xlink"
        xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
        xmlns:gml="http://www.opengis.net/gml"
        xsi:schemaLocation="http://www.opengis.net/wmts/1.0 http://schemas.opengis.net/wmts/1.0/wmtsGetCapabilities_response.xsd"
        version="1.0.0">
       <ows:ServiceIdentification>
            <ows:Title>Cloud Optimizied GeoTIFF Mosaic</ows:Title>
            <ows:ServiceType>OGC WMTS</ows:ServiceType>
            <ows:ServiceTypeVersion>1.0.0</ows:ServiceTypeVersion>
        </ows:ServiceIdentification>
        <ows:OperationsMetadata>
            <ows:Operation name="GetCapabilities">
                <ows:DCP>
                    <ows:HTTP>
                        <ows:Get xlink:href="https://{endpoint-url}/wmts?url=http%3A%2F%2Fmymosaic.json">
                            <ows:Constraint name="GetEncoding">
                                <ows:AllowedValues>
                                    <ows:Value>RESTful</ows:Value>
                                </ows:AllowedValues>
                            </ows:Constraint>
                        </ows:Get>
                    </ows:HTTP>
                </ows:DCP>
            </ows:Operation>
            <ows:Operation name="GetTile">
                <ows:DCP>
                    <ows:HTTP>
                        <ows:Get xlink:href="https://{endpoint-url}/wmts?url=http%3A%2F%2Fmymosaic.json">
                            <ows:Constraint name="GetEncoding">
                                <ows:AllowedValues>
                                    <ows:Value>RESTful</ows:Value>
                                </ows:AllowedValues>
                            </ows:Constraint>
                        </ows:Get>
                    </ows:HTTP>
                </ows:DCP>
            </ows:Operation>
        </ows:OperationsMetadata>
        <Contents>
            <Layer>
                <ows:Title>Cloud Optimizied GeoTIFF Mosaic</ows:Title>
                <ows:Identifier>CogeoMosaic</ows:Identifier>
                <ows:Abstract>cogeo-mosaic</ows:Abstract>
                <ows:WGS84BoundingBox crs="urn:ogc:def:crs:OGC:2:84">
                    <ows:LowerCorner>-75.98703377403767 44.93504283303786</ows:LowerCorner>
                    <ows:UpperCorner>-71.337604724099 47.096855991923235</ows:UpperCorner>
                </ows:WGS84BoundingBox>
                <Style isDefault="true">
                    <ows:Identifier>default</ows:Identifier>
                </Style>
                <Format>image/png</Format>
                <TileMatrixSetLink>
                    <TileMatrixSet>GoogleMapsCompatible</TileMatrixSet>
                </TileMatrixSetLink>
                <ResourceURL
                    format="image/png"
                    resourceType="tile"
                    template="https://{endpoint-url}/{TileMatrix}/{TileCol}/{TileRow}@1x.png?url=http%3A%2F%2Fmymosaic.json"/>
            </Layer>
            <TileMatrixSet>
                <ows:Title>GoogleMapsCompatible</ows:Title>
                <ows:Abstract>GoogleMapsCompatible EPSG:3857</ows:Abstract>
                <ows:Identifier>GoogleMapsCompatible</ows:Identifier>
                <ows:SupportedCRS>urn:ogc:def:crs:EPSG::3857</ows:SupportedCRS>
                <TileMatrix>
            <ows:Identifier>7</ows:Identifier>
            <ScaleDenominator>4367830.187724375</ScaleDenominator>
            <TopLeftCorner>-20037508.34278925 20037508.34278925</TopLeftCorner>
            <TileWidth>256</TileWidth>
            <TileHeight>256</TileHeight>
            <MatrixWidth>128</MatrixWidth>
            <MatrixHeight>128</MatrixHeight>
        </TileMatrix>
<TileMatrix>
            <ows:Identifier>8</ows:Identifier>
            <ScaleDenominator>2183915.0938621876</ScaleDenominator>
            <TopLeftCorner>-20037508.34278925 20037508.34278925</TopLeftCorner>
            <TileWidth>256</TileWidth>
            <TileHeight>256</TileHeight>
            <MatrixWidth>256</MatrixWidth>
            <MatrixHeight>256</MatrixHeight>
        </TileMatrix>
<TileMatrix>
            <ows:Identifier>9</ows:Identifier>
            <ScaleDenominator>1091957.5469310938</ScaleDenominator>
            <TopLeftCorner>-20037508.34278925 20037508.34278925</TopLeftCorner>
            <TileWidth>256</TileWidth>
            <TileHeight>256</TileHeight>
            <MatrixWidth>512</MatrixWidth>
            <MatrixHeight>512</MatrixHeight>
        </TileMatrix>
            </TileMatrixSet>
        </Contents>
        <ServiceMetadataURL xlink:href='https://{endpoint-url}/tiles/wmts?url=http%3A%2F%2Fmymosaic.json'/>
    </Capabilities>
```
</details>

## - Image tiles

- `/<int:z>/<int:x>/<int:y>.<ext>`
- `/<int:z>/<int:x>/<int:y>@2x.<ext>`

- methods: GET
- **z**: Mercator tile zoom value
- **x**: Mercator tile x value
- **y**: Mercator tile y value
- **scale**: Tile scale (default: 1)
- **ext**: Output tile format (e.g `jpg`)
- **url** (required): mosaic definition url
- **indexes** (optional, str): dataset band indexes (default: None)
- **rescale** (optional, str): min/max for data rescaling (default: None)
- **color_ops** (optional, str): rio-color formula (default: None)
- **color_map** (optional, str): rio-tiler colormap (default: None)
- **pixel_selection** (optional, str): mosaic pixel selection (default: `first`)
- **resampling_method** (optional, str): tiler resampling method (default: `nearest`)
- compression: **gzip**
- returns: image body (image/jpeg)

```bash
$ curl https://{endpoint-url}/8/32/22.png?url=s3://my_bucket/my_mosaic.json.gz&indexes=1,2,3&rescale=100,3000&color_ops=Gamma RGB 3&pixel_selection=first
```

## - Vector tiles

Note that generating vector tiles depends on the optional dependency
`rio-tiler-mvt`. If the vector tile endpoint is requested and the dependency is
not installed, an error will be raised.

`/<int:z>/<int:x>/<int:y>.<pbf>`

- methods: GET
- **z**: Mercator tile zoom value
- **x**: Mercator tile x value
- **y**: Mercator tile y value
- **ext**: Output tile format (e.g `jpg`)
- **url** (required): mosaic definition url
- **tile_size**: (optional, int) Tile size (default: 256)
- **pixel_selection** (optional, str): mosaic pixel selection (default: `first`)
- **feature_type** (optional, str): feature type (default: `point`)
- **resampling_method** (optional, str): tiler resampling method (default: `nearest`)
- compression: **gzip**
- returns: tile body (application/x-protobuf)

```bash
$ curl https://{endpoint-url}/8/32/22.pbf?url=s3://my_bucket/my_mosaic.json.gz&pixel_selection=first
```

### - Point Value

`/point`

- methods: GET
- **lng** (required, float): longitude
- **lat** (required, float): lattitude
- **url** (required): mosaic definition url
- compression: **gzip**
- returns: json(application/json, compression: **gzip**)

```bash
$ curl https://{endpoint-url}/point?url=s3://my_bucket/my_mosaic.json.gz&lng=10&lat=-10
```