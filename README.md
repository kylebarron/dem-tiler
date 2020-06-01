# dem-mosaic-tiler

Work in progress

A fork of [`cogeo-mosaic-tiler`][cogeo-mosaic-tiler] to serve elevation products
on demand from a mosaic of Cloud-Optimized GeoTIFF elevation data.

[cogeo-mosaic-tiler]: https://github.com/developmentseed/cogeo-mosaic-tiler

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

This repo is set to use `pre-commit` to run _flake8_, _pydocstring_ and _black_ ("uncompromising Python code formatter") when committing new code.

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

Created by [Development Seed](http://developmentseed.org)
