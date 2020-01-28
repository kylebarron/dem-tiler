FROM remotepixel/amazonlinux:gdal3.0-py3.7-cogeo

WORKDIR /tmp

ENV PYTHONUSERBASE=/var/task

COPY cogeo_mosaic_tiler/ cogeo_mosaic_tiler/
COPY setup.py setup.py

# Install dependencies
RUN pip install . --user
RUN rm -rf cogeo_mosaic_tiler setup.py