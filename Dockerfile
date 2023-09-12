FROM python:3.10

WORKDIR /app

ADD . /app

RUN pip install poetry

RUN poetry install

EXPOSE 80

# Define environment variable for Open Interpreter
# You can replace these with your actual values
ENV INTERPRETER_CLI_AUTO_RUN=False
ENV INTERPRETER_CLI_FAST_MODE=False
ENV INTERPRETER_CLI_LOCAL_RUN=False
ENV INTERPRETER_CLI_DEBUG=False
ENV INTERPRETER_CLI_USE_AZURE=False

CMD ["poetry", "run", "interpreter"]
