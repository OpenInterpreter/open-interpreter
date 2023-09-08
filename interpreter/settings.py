"""
File for constants and settings
"""

# Message for when users don't have an OpenAI API key.
MISSING_API_KEY_MESSAGE = """> OpenAI API key not found

To use `GPT-4` (recommended) please provide an OpenAI API key.

To use `Code-Llama` (free but less capable) press `enter`.
"""

# Message for when users don't have an OpenAI API key.
MISSING_AZURE_INFO_MESSAGE = """> Azure OpenAI Service API info not found

To use `GPT-4` (recommended) please provide an Azure OpenAI API key, a API base, a deployment name and a API version.

To use `Code-Llama` (free but less capable) press `enter`.
"""

CONFIRM_MODE_MESSAGE = """
**Open Interpreter** will require approval before running code. Use `interpreter -y` to bypass this.

Press `CTRL-C` to exit.
"""

APPLE_WARNING_MESSAGE = """
Warning: You are using Apple Silicon (M1) Mac but your Python is not of 'arm64' architecture.
The llama.ccp x86 version will be 10x slower on Apple Silicon (M1) Mac.
\nTo install the correct version of Python that supports 'arm64' architecture:
1. Download Miniforge for M1:
wget https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-MacOSX-arm64.sh
2. Install it:
bash Miniforge3-MacOSX-arm64.sh\n
"""
