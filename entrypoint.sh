#!/usr/bin/env bash

LOCAL_LLM=${LOCAL_LLM:-true}      # local llama (local) or "open" ai (empty string/null)
MODELS_DIR=${MODELS_DIR:-"/root/.local/share/Open Interpreter/models"} # model download directory (optional)
DATA_DIR=${DATA_DIR:-/data}       # data directory (optional)
PARAMS=${PARAMS:-}                # optional additional params to pass to the python script

if [ "${LOCAL_LLM}" = "true" ]; then
  LLM="--local"
else
  LLM=""
fi

# split any params if they are provided in to an array
if [ -n "$PARAMS" ]; then
  IFS=' ' read -r -a PARAMS <<<"$PARAMS"
else
  PARAMS=()
fi

# load python virtualenv
. venv/bin/activate

echo "Models directory: ${MODELS_DIR}"
echo "Data directory: ${DATA_DIR}"

# run the python script
interpreter "$LLM" "${PARAMS[@]}"
