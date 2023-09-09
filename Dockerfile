FROM nvidia/cuda:12.2.0-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV FORCE_CMAKE=1
ENV GPU_FLAGS=all

ENV CMAKE_ARGS=${CMAKE_ARGS:-"-DLLAMA_OPENBLAS=on -DLLAMA_BLAS=ON -DLLAMA_CUBLAS=on -DLLAMA_CLBLAST=on -DLLAMA_HIPBLAS=on -DLLAMA_F16C=on -DLLAMA_AVX512=on -DLLAMA_AVX2=on -DLLAMA_FMA=on"}

RUN apt-get update && \
  apt-get install -y --no-install-recommends python3 python3-dev python3-pip python3-venv && \
  rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/pip \
  pip install --upgrade pip && \
  python3 -m venv venv && \
  . venv/bin/activate && \
  pip install --upgrade llama-cpp-python open-interpreter

COPY entrypoint.sh /app/entrypoint.sh

# Start an interactive shell
CMD ["/app/entrypoint.sh"]
