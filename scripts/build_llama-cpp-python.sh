#!/bin/bash

# Install llama-cpp-python with GPU acceleration, overwriting the version installed by text-generation-webui
# We do this on boot, so as to ensure the binaries are built with the right CPU instructions for the machine being used

pip uninstall -qy llama-cpp-python

# Check to see if this machine supports AVX2 instructions
if python3 /app/scripts/check_avx2.py; then
	export CMAKE_ARGS="-DLLAMA_CUBLAS=on -DCMAKE_CUDA_COMPILER=/usr/local/cuda/bin/nvcc"
else
	# If it does not, we need to specifically tell llama-cpp-python not to use them
	# as unfortunately it's otherwise hardcoded to use them
	export CMAKE_ARGS="-DLLAMA_AVX2=OFF -DLLAMA_CUBLAS=on -DCMAKE_CUDA_COMPILER=/usr/local/cuda/bin/nvcc"
fi

export PATH=/usr/local/cuda/bin:"$PATH"
export FORCE_CMAKE=1

