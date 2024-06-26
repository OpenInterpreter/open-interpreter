"""
This is a sketch of a simple benchmark runner.
"""

tasks = [
    {
        "question": "",
        "answer": "",
    },
    {"setup_script": "", "question": "", "answer": "", "evaluation_script": ""},
]

# For each task,
# Start a thread that does the following:
# Spin up a docker container
# Run the setup script
# Ask the question
# Run the evaluation script or use an LLM to check the answer
