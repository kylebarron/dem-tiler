
SHELL = /bin/bash

package:
	docker build --tag cogeo-mosaic:latest .
	docker run --name cogeo-mosaic --volume $(shell pwd)/:/local -itd cogeo-mosaic:latest bash
	docker exec -it cogeo-mosaic bash '/local/bin/package.sh'
	docker stop cogeo-mosaic
	docker rm cogeo-mosaic
