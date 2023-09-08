ARG CUDA_VERSION="11.8.0"
ARG CUDNN_VERSION="8"
ARG UBUNTU_VERSION="22.04"
ARG PYTHON_VERSION="3.11.4"
ARG DOCKER_FROM=nvidia/cuda:$CUDA_VERSION-cudnn$CUDNN_VERSION-devel-ubuntu$UBUNTU_VERSION



FROM $DOCKER_FROM AS base

RUN apt-get update && apt-get install -y \
    wget \
    bzip2 \
    git \
    ca-certificates \
    --no-install-recommends && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /tmp

RUN wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh && \
    bash Miniconda3-latest-Linux-x86_64.sh -b -p /opt/conda && \
    rm Miniconda3-latest-Linux-x86_64.sh

ENV PATH="/opt/conda/bin:${PATH}"

ENV MAX_LOCAL_CTX="4096"

RUN conda create -y --name interpreter-default python="$PYTHON_VERSION"
RUN echo "source activate interpreter-default" > ~/.bashrc
WORKDIR /app

COPY  . /app
RUN chmod +x /app/scripts/startup.sh
RUN chmod +x /app/scripts/build_llama-cpp-python.sh
RUN mkdir -p /app/logs
RUN mkdir -p  /root/.local/share/Open_Interpreter/models
RUN ln -s /root/.local/share/Open_Interpreter/models /app/models

RUN pip install -U pip setuptools
RUN pip install poetry

CMD [ "bash" ]