from interpreter import interpreter
#     ____                      ____      __                            __
#    / __ \____  ___  ____     /  _/___  / /____  _________  ________  / /____  _____
#   / / / / __ \/ _ \/ __ \    / // __ \/ __/ _ \/ ___/ __ \/ ___/ _ \/ __/ _ \/ ___/
#  / /_/ / /_/ /  __/ / / /  _/ // / / / /_/  __/ /  / /_/ / /  /  __/ /_/  __/ /
#  \____/ .___/\___/_/ /_/  /___/_/ /_/\__/\___/_/  / .___/_/   \___/\__/\___/_/
#      /_/                                         /_/
# from interpreter import interpreter
interpreter.llm.model = 'mixtral-8x7b-32768'
interpreter.llm.api_key = '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'
interpreter.llm.api_base = "https://api.groq.com/openai/v1"
interpreter.llm.context_window = 32000

blocks = []
def out(partial, *a, **kw):
    print("STREAMING OUT! ",partial)
interpreter.chat(stream_out = out)
