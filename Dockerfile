FROM python:3.11.8

# Set environment variables
# ENV OPENAI_API_KEY ...

ENV INTERPRETER_HOST 0.0.0.0
# ^ Sets the server host to 0.0.0.0, Required for the server to be accessible outside the container

# Copy required files into container
RUN mkdir -p interpreter scripts
COPY interpreter/ interpreter/
COPY scripts/ scripts/
COPY poetry.lock pyproject.toml README.md ./

# Expose port 8000
EXPOSE 8000

RUN pip install "."

# Start the server
ENTRYPOINT ["interpreter", "--serve"]