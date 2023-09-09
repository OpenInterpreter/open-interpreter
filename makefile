MAJOR?=0
MINOR?=1
VERSION=$(MAJOR).$(MINOR)
APP_NAME="open_inperpreter"
HUB_NAMESPACE="killianlucas"
DOCKER_FILE_DIR = "."
DOCKERFILE = "${DOCKER_FILE_DIR}/Dockerfile"
IMAGE_NAME = "${HUB_NAMESPACE}/${APP_NAME}:${VERSION}"
CUR_DIR = $(shell echo "${PWD}")

build:
	@docker build -t $(IMAGE_NAME) -f $(DOCKERFILE) $(CUR_DIR)
run:
	@docker run -it --name $(APP_NAME) $(IMAGE_NAME)
run-gpu:
	@docker run -it --gpus=all --name $(APP_NAME) $(IMAGE_NAME)
rm:
	@docker rm $(APP_NAME)
