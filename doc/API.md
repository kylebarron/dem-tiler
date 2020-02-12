# API

Online API documentation can be found over `{endpoint}/docs`.

## mosaicJSON path

The cogeo-mosaic-tiler support two ways of passing the mosaicJSON path.
- `https://{endpoint-url}/{method}?url={mosaicURL}` 

The **mosaicURL** can be any web hosted files.

- `https://{endpoint-url}/{mosaicid}/{method}` (advanced method)

The **mosaicid** should be a string matching `[0-9A-Fa-f]{56}` regex (usually created using `sha224sum mymosaic.json.gz`). When using mosaicid, the tiler will reconscruct a file s3 url and then result to `s3://{my-bucket}/mosaic/mosaicid.json.gz`

```
$ cogeo-mosaic create mylist.txt -o mosaic.json
$ cat mosaic.json | gzip > mosaic.json.gz 

$ sha224sum mosaic.json.gz
92979ccd7d443ff826e493e4af707220ba77f16def6f15db86141ba8  mosaic.json.gz

$ aws s3 cp mosaic.json.gz s3://my-bucket/mosaics/92979ccd7d443ff826e493e4af707220ba77f16def6f15db86141ba8.json.gz

$ curl https://{endpoint-url}/92979ccd7d443ff826e493e4af707220ba77f16def6f15db86141ba8/info
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
  - format: **json**
- returns: mosaic info (application/json, compression: **gzip**)

```bash
$ curl -X POST -d @list.json https://{endpoint-url}/add`

{
  "id": "d4c05a130c8a336c6..........2cbc5c34aed85feffdaafd01ef",
  "url": "s3://{my-bucket}/mosaics/d4c05a130c8a336c647ef83fe...........ffdaafd01ef.json.gz"
}
```

## - Mosaic Metadata
`/info`
- methods: GET
- **url** (in querytring): mosaic definition url
- returns: mosaic defintion info (application/json, compression: **gzip**)

```bash
$ curl https://{endpoint-url}/info?url=https://my-mosaic.json.gz
```

`/<mosaicid>/info`
- methods: GET
- **mosaicid** (in path): mosaic definition id
- returns: mosaic defintion info (application/json, compression: **gzip**)


```bash
$ curl https://{endpoint-url}/0505ad234b5fb97df134001709b8a42eddce5d
03b200eb8f7f4540d6/info
```

```json
{
    "bounds": [],                // mosaic bounds
    "center": [lon, lat, zoom],     // mosaic center
    "maxzoom": 22,                  // mosaic max zoom
    "minzoom": 18,                  // mosaic min zoom
    "name": "0505ad234b5fb97df134001709b8a42eddce5d03b200eb8f7f4540d6", // mosaic basename
    "quadkeys": [],              // list of quakeys
    "layers": [] ,               // dataset band names
}
```

## - Mosaic GeoJSON

`/geojson`
- methods: GET
- **url** (in querytring): mosaic definition url
- returns: mosaic-json as geojson (application/json, compression: **gzip**)

```bash
$ curl https://{endpoint-url}/geojson?url=s3://my_file.json.gz
```

`/<mosaicid>/geojson`
- methods: GET
- **mosaicid** (in path): mosaic definition id
- returns: mosaic-json as geojson (application/json, compression: **gzip**)

```bash
$ curl https://{endpoint-url}/0505ad234b5fb97df134001709b8a42eddce5d
03b200eb8f7f4540d6/geojson
```

```json
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
$ curl https://{endpoint-url}/tilejson.json?url=s3://my_file.json.gz
```

`/<mosaicid>/tilejson.json`

- methods: GET
- **mosaicid** (in path): mosaic definition id
- **tile_format** (optional, str): output tile format (default: "png")
- **tile_scale** (optional, int): output tile scale (default: 1 = 256px)
- **kwargs** (in querytring): tiler options
- returns: tileJSON defintion (application/json, compression: **gzip**)

```bash
$ curl https://{endpoint-url}/0505ad234b5fb97df134001709b8a42eddce5d
03b200eb8f7f4540d6/tilejson.json
```

```json
{
    "bounds": [],
    "center": [lon, lat, minzoom],
    "maxzoom": 22,
    "minzoom": 18,
    "name": "s3://my_file.json.gz",
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
$ curl https://{endpoint-url}/wmts?url=s3://my_file.json.gz)
```

`/<mosaicid>/wmts`

- methods: GET
- **mosaicid** (in path): mosaic definition id
- **tile_format** (optional, str): output tile format (default: "png")
- **tile_scale** (optional, int): output tile scale (default: 1 = 256px)
- **title** (optional, str): layer name (default: "Cloud Optimizied GeoTIFF Mosaic")
- **kwargs** (in querytring): tiler options
- returns: WMTS xml (application/xml, compression: **gzip**)

```bash
$ curl https://{endpoint-url}/0505ad234b5fb97df134001709b8a42eddce5d
03b200eb8f7f4540d6/wmts
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

## - image tiles
`/<int:z>/<int:x>/<int:y>.<ext>`

`/<int:z>/<int:x>/<int:y>@2x.<ext>`

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
$ curl https://{endpoint-url}/8/32/22.png?url=s3://my_file.json.gz&indexes=1,2,3&rescale=100,3000&color_ops=Gamma RGB 3&pixel_selection=first
```

`/<mosaicid>/<int:z>/<int:x>/<int:y>.<ext>`

`/<mosaicid>/<int:z>/<int:x>/<int:y>@2x.<ext>`

- methods: GET
- **mosaicid** (in path): mosaic definition id
- **z**: Mercator tile zoom value
- **x**: Mercator tile x value
- **y**: Mercator tile y value
- **scale**: Tile scale (default: 1)
- **ext**: Output tile format (e.g `jpg`)
- **indexes** (optional, str): dataset band indexes (default: None)
- **rescale** (optional, str): min/max for data rescaling (default: None)
- **color_ops** (optional, str): rio-color formula (default: None)
- **color_map** (optional, str): rio-tiler colormap (default: None)
- **pixel_selection** (optional, str): mosaic pixel selection (default: `first`)
- **resampling_method** (optional, str): tiler resampling method (default: `nearest`)
- compression: **gzip**
- returns: image body (image/jpeg)

```bash
$ curl https://{endpoint-url}/0505ad234b5fb97df134001709b8a42eddce5d
03b200eb8f7f4540d6/8/32/22.png?indexes=1,2,3&rescale=100,3000&color_ops=Gamma RGB 3&pixel_selection=first
```

## - Vector tiles

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
$ curl https://{endpoint-url}/8/32/22.pbf?url=s3://my_file.json.gz&pixel_selection=first
```

`/<mosaicid>/<int:z>/<int:x>/<int:y>.<pbf>`

- methods: GET
- **mosaicid** (in path): mosaic definition id
- **z**: Mercator tile zoom value
- **x**: Mercator tile x value
- **y**: Mercator tile y value
- **tile_size**: (optional, int) Tile size (default: 256)
- **pixel_selection** (optional, str): mosaic pixel selection (default: `first`)
- **feature_type** (optional, str): feature type (default: `point`)
- **resampling_method** (optional, str): tiler resampling method (default: `nearest`)
- compression: **gzip**
- returns: tile body (application/x-protobuf)

```bash
$ curl https://{endpoint-url}/0505ad234b5fb97df134001709b8a42eddce5d
03b200eb8f7f4540d6/8/32/22.pbf?pixel_selection=first
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
$ curl https://{endpoint-url}/point?url=s3://my_file.json.gz&lng=10&lat=-10
```

`/<mosaicid>/point`

- methods: GET
- **mosaicid** (in path): mosaic definition id
- **lng** (required, float): longitude
- **lat** (required, float): lattitude
- compression: **gzip**
- returns: tile body (application/x-protobuf)

```bash
$ curl https://{endpoint-url}/0505ad234b5fb97df134001709b8a42eddce5d
03b200eb8f7f4540d6/point?lng=10&lat=-10
```

