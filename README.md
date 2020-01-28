# cogeo-mosaic

Serve Map tile from Cloud Optimized GeoTIFF mosaics based on [mosaicJSON](https://github.com/developmentseed/mosaicjson-spec).

[![CircleCI](https://circleci.com/gh/developmentseed/cogeo-mosaic-tiler.svg?style=svg)](https://circleci.com/gh/developmentseed/cogeo-mosaic-tiler)
[![codecov](https://codecov.io/gh/developmentseed/cogeo-mosaic-tiler/branch/master/graph/badge.svg)](https://codecov.io/gh/developmentseed/cogeo-mosaic-tiler)

**Read the official announcement https://medium.com/devseed/cog-talk-part-2-mosaics-bbbf474e66df**

![](https://user-images.githubusercontent.com/10407788/57888417-1fc75100-7800-11e9-93a3-b54d06fb4cd2.png)

# Deploy

#### Package Lambda

Create `package.zip`

```bash
$ make package
```

#### Deploy to AWS

This project uses [Serverless](https://serverless.com) to manage deploy on AWS.

```bash
# Install and Configure serverless (https://serverless.com/framework/docs/providers/aws/guide/credentials/)
$ npm install serverless -g 

$ sls deploy --region us-east-1 --bucket a-bucket-where-you-store-data
```

#### Docs

See [/doc/API.md](/doc/API.md) for the documentation. 

#### Live

A version of this stack is deployed on AWS us-east-1 and available on [mosaic.cogeo.xyz](https://mosaic.cogeo.xyz)

### Contribution & Development

Issues and pull requests are more than welcome.

**Dev install & Pull-Request**

```
$ git clone http://github.com/developmentseed/cogeo-mosaic-tiler.git
$ cd cogeo-mosaic
$ pip install -e .[dev]
```


**Python >=3.6 only**

This repo is set to use `pre-commit` to run *flake8*, *pydocstring* and *black* ("uncompromising Python code formatter") when committing new code.

```
$ pre-commit install
$ git add .
$ git commit -m'my change'
black....................................................................Passed
Flake8...................................................................Passed
Verifying PEP257 Compliance..............................................Passed
$ git push origin
```


## About
Created by [Development Seed](<http://developmentseed.org>)
