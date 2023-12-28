import requests

from ..llm.utils.convert_to_openai_messages import convert_to_openai_messages


def get_relevant_procedures_string(interpreter):
    # Open Procedures is an open-source database of tiny, up-to-date coding tutorials.
    # We can query it semantically with the last two messages and append relevant tutorials/procedures to our system message:

    # Convert last two messages to required OpenAI-compatible `messages` list
    messages = convert_to_openai_messages(
        interpreter.messages[-2:], function_calling=False, vision=False
    )
    messages = [{"role": "system", "content": interpreter.system_message}] + messages
    query = {"query": messages}
    url = "https://open-procedures.replit.app/search/"

    response = requests.post(url, json=query).json()

    if interpreter.verbose:
        print(response)

    relevant_procedures = response["procedures"]
    relevant_procedures = "[Recommended Procedures]\n" + "\n---\n".join(
        relevant_procedures
    )
    if not interpreter.os:
        relevant_procedures += "\nIn your plan, include steps and, for relevant deprecation notices, **EXACT CODE SNIPPETS** -- these notices will VANISH once you execute your first line of code, so WRITE THEM DOWN NOW if you need them."

    return relevant_procedures
