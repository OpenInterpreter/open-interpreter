import interpreter
interpreter.no_confirm = True
interpreter.temperature = 0

def test_delayed_exec():
    interpreter.reset()
    interpreter.chat("""Can you write a single block of code and run_code it that prints something, then delays 5 seconds, then prints something else? No talk just code. Thanks!""", return_messages=True)

def test_math():
    interpreter.reset()
    messages = interpreter.chat("""Please perform the calculation 27073*7397 then reply with just the integer answer, nothing else.""", return_messages=True)
    assert messages[-1] == {'role': 'assistant', 'content': '200258981'}

def test_hello_world():
    interpreter.reset()
    messages = interpreter.chat("""Please reply with just the words "Hello, World!" and nothing else.""", return_messages=True)
    assert messages == [{'role': 'user', 'content': 'Please reply with just the words "Hello, World!" and nothing else.'}, {'role': 'assistant', 'content': 'Hello, World!'}]
  
def test_markdown():
    interpreter.reset()
    interpreter.chat("Hi, can you test out a bunch of markdown features? Try writing a fenced code block, a table, headers, everything. DO NOT write the markdown inside a markdown code block, just write it raw.")