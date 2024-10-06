
# Open-Interpreter with Meta-Llama-3.2-90B-Vision-Instruct and SDAGENCY

## Overview
This version of Open-Interpreter is integrated with **Meta-Llama-3.2-90B-Vision-Instruct** as the default AI model for real-time project orchestration and code generation. The system includes an enhanced **SDAGENCY** module, which allows users to provide a software idea, break it down into tasks, and have different agents (backend, frontend, DevOps, security, etc.) execute each task autonomously.

## Features
- **Meta-Llama-3.2-90B-Vision-Instruct** as the default AI model.
- **SDAGENCY** for automatic project orchestration with agent-based task execution.
- Real-time code generation and deployment across different software components.

## Setup Instructions
1. Clone the repository:
    ```bash
    git clone https://github.com/ZanaNowshad/open-interpreter.git
    cd open-interpreter
    ```

2. Install the required dependencies:
    ```bash
    pip install -r requirements.txt
    ```

3. Set up the Meta-Llama model:
    - Ensure that you have access to the **Meta-Llama-3.2-90B-Vision-Instruct** model via the correct API.
    - Update your environment variables to include your **API key** for accessing the model.

4. Run the Interpreter:
    ```bash
    python main.py
    ```

## Usage
1. Start the interpreter.
2. Type `%sdagency%` to activate the **SDAGENCY** system.
3. Enter your software idea in detail, and watch as agents begin to work on the project autonomously.

## Dependencies
- **Python 3.8+**
- **Flask** (for backend code generation)
- **React** (for frontend code generation)
- **Terraform** (for cloud infrastructure)
- **Meta-Llama-3.2-90B-Vision-Instruct** (for real-time project orchestration)

## License
MIT License
