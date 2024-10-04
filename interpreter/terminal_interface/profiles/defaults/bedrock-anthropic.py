"""
This is an Open Interpreter profile. It configures Open Interpreter to run Anthropic's `Claude 3 Sonnet` using Bedrock.
"""

"""
Recommended pip package:
pip install boto3

Recommended environment variables:
os.environ["AWS_ACCESS_KEY_ID"] = ""  # Access key
os.environ["AWS_SECRET_ACCESS_KEY"] = "" # Secret access key
os.environ["AWS_REGION_NAME"] = "" # us-east-1, us-east-2, us-west-1, us-west-2

More information can be found here: https://docs.litellm.ai/docs/providers/bedrock
"""

from interpreter import interpreter

interpreter.llm.model = "bedrock/anthropic.claude-3-sonnet-20240229-v1:0"

interpreter.computer.import_computer_api = True

interpreter.llm.supports_functions = False
interpreter.llm.supports_vision = False
interpreter.llm.context_window = 10000
interpreter.llm.max_tokens = 4096
