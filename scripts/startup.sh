
# Start build of llama-cpp-python in background
if [[ ! -f /.built.llama-cpp-python ]]; then
	./app/scripts/build-llama-cpp-python.sh
fi