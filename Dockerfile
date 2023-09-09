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

COPY --from=continuumio/miniconda3:23.5.2-0 /opt/conda /opt/conda

ENV PATH="/opt/conda/bin:${PATH}"


RUN conda create -y --name interpreter-default python="$PYTHON_VERSION"
RUN echo "source activate interpreter-default" > ~/.bashrc
WORKDIR /app

COPY  . /app
RUN chmod +x /app/scripts/startup.sh
RUN chmod +x /app/scripts/build_llama-cpp-python.sh
RUN mkdir -p /app/logs
RUN mkdir -p /root/.local/share/Open_Interpreter
RUN mkdir -p /app/models

#RUN ln -s /root/.local/share/Open_Interpreter/models /app/models
#RUN ln -s /app/models /root/.local/share/Open_Interpreter/models
RUN pip install -U pip setuptools
RUN pip install poetry

CMD [ "bash" ]
