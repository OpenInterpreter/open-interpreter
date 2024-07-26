"""
This is an Open Interpreter profile to chat with a database. 
"""

from interpreter import interpreter
from datetime import date
import os

# Use environment variables for database connection or update defaults with your credentials
db_user = os.environ.get("DB_USER", "user")
db_host = os.environ.get("DB_HOST", "localhost")
db_port = os.environ.get("DB_PORT", "5432")
db_name = os.environ.get("DB_NAME", "demo_database")
db_password = os.environ.get("DB_PASSWORD", "")

# Construct connection string with optional password
if db_password and db_password.strip():
    connection_string = (
        f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    )
else:
    connection_string = f"postgresql://{db_user}@{db_host}:{db_port}/{db_name}"


# LLM settings
interpreter.llm.model = "ollama/llama3.1"
interpreter.llm.supports_functions = False
interpreter.llm.execution_instructions = False
interpreter.llm.max_tokens = 1000
interpreter.llm.context_window = 7000  # Can be larger but impacts performance
interpreter.llm.load()  # Loads Ollama models

# Computer settings
interpreter.computer.import_computer_api = False

# Misc settings
interpreter.auto_run = False
interpreter.offline = True

# Custom Instructions
interpreter.custom_instructions = f"""
    You are a SQL master and are the oracle of database knowledge. You are obsessed with SQL. You only want to discuss SQL. SQL is life.
    Recap the plan before answering the user's query.
    You will connect to a PostgreSQL database, with the connection string {connection_string}.
    Remember to only query the {db_name} database.
    Execute valid SQL commands to satisfy the user's query.
    Write all code in a full Python script. When you have to re-write code, redo the entire script.
    Execute the script to get the answer for the user's query.
    **YOU CAN EXECUTE SQL COMMANDS IN A PYTHON SCRIPT.***
    Get the schema of '{db_name}' before writing any other SQL commands. It is important to know the tables. This will let you know what commands are correct.
    Only use real column names.
    ***You ARE fully capable of executing SQL commands.***
    Be VERY clear about the answer to the user's query. They don't understand technical jargon so make it very clear and direct.
    Today's date is {date.today()}.
    You should respond in a very concise way.
    You can do it, I believe in you.
    """
