"""Setup cogeo-mosaic."""

from setuptools import find_packages, setup

# Runtime requirements.
# NOTE: there were breaking changes in cogeo-mosaic and rio-tiler between these
# alpha releases and 3.0 and 2.0
inst_reqs = [
    "cogeo-mosaic==3.0a1",
    # the GDAL C library is installed separately;
    # This is specifically for the Python GDAL bindings, used to create contours
    "gdal<3.0",
    "lambda-proxy~=5.2",
    "pymartini>=0.3.0",
    "pydelatin>=0.2.0",
    "quantized-mesh-encoder>=0.1.2",
    "rio-color",
    "rio-tiler==2.0a9",
]

extra_reqs = {
    "dev": ["pytest", "pytest-cov", "pre-commit", "mock"],
    "mvt": ["rio-tiler-mvt"],
    "test": ["pytest", "pytest-cov", "mock"],
}

setup(
    name="dem-tiler",
    version="0.0.2",
    description=u"Serve Map tile from Cloud Optimized GeoTIFF mosaics.",
    long_description=u"Serve Map tile from Cloud Optimized GeoTIFF mosaics.",
    python_requires=">=3",
    classifiers=[
        "Intended Audience :: Information Technology",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: BSD License",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
    ],
    keywords="COG COGEO Mosaic GIS",
    author=u"Vincent Sarago",
    author_email="vincent@developmentseed.org",
    url="https://github.com/developmentseed/dem-tiler",
    license="MIT",
    packages=find_packages(exclude=["ez_setup", "examples", "tests"]),
    include_package_data=True,
    zip_safe=False,
    install_requires=inst_reqs,
    extras_require=extra_reqs,
)
