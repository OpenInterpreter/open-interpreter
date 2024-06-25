###########################################################################################
# This Dockerfile runs an LMC-compatible websocket server at / on port 8000.              #
# To learn more about LMC, visit https://docs.openinterpreter.com/protocols/lmc-messages. #
###########################################################################################

FROM python:3.11.8

# Set environment variables
# ENV OPENAI_API_KEY ...

# Copy required files into container
RUN mkdir -p interpreter
COPY interpreter/ interpreter/
COPY poetry.lock pyproject.toml README.md ./

# Expose port 8000
EXPOSE 8000

# Install server dependencies
RUN pip install -e ".[server]"

# Start the server
ENTRYPOINT ["interpreter", "--server"]