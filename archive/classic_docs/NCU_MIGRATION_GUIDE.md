# `0.2.0` Migration Guide

Open Interpreter is [changing](https://changes.openinterpreter.com/log/the-new-computer-update). This guide will help you migrate your application to `0.2.0`, also called the _New Computer Update_ (NCU), the latest major version of Open Interpreter.

## A New Start

To start using Open Interpreter in Python, we now use a standard **class instantiation** format:

```python
# From the module `interpreter`, import the class `OpenInterpreter`
from interpreter import OpenInterpreter

# Create an instance of `OpenInterpreter` to use it
agent = OpenInterpreter()
agent.chat()
```

For convenience, we also provide an instance of `interpreter`, which you can import from the module (also called `interpreter`):

```python
 # From the module `interpreter`, import the included instance of `OpenInterpreter`
from interpreter import interpreter

interpreter.chat()
```

## New Parameters

All stateless LLM attributes have been moved to `interpreter.llm`:

- `interpreter.model` → `interpreter.llm.model`
- `interpreter.api_key` → `interpreter.llm.api_key`
- `interpreter.llm_supports_vision` → `interpreter.llm.supports_vision`
- `interpreter.supports_function_calling` → `interpreter.llm.supports_functions`
- `interpreter.max_tokens` → `interpreter.llm.max_tokens`
- `interpreter.context_window` → `interpreter.llm.context_window`
- `interpreter.temperature` → `interpreter.llm.temperature`
- `interpreter.api_version` → `interpreter.llm.api_version`
- `interpreter.api_base` → `interpreter.llm.api_base`

This is reflected **1)** in Python applications using Open Interpreter and **2)** in your profile for OI's terminal interface, which can be edited via `interpreter --profiles`.

## New Static Messages Structure

- The array of messages is now flat, making the architecture more modular, and easier to adapt to new kinds of media in the future.
- Each message holds only one kind of data. This yields more messages, but prevents large nested messages that can be difficult to parse.
- This allows you to pass the full `messages` list into Open Interpreter as `interpreter.messages = message_list`.
- Every message has a "role", which can be "assistant", "computer", or "user".
- Every message has a "type", specifying the type of data it contains.
- Every message has "content", which contains the data for the message.
- Some messages have a "format" key, to specify the format of the content, like "path" or "base64.png".
- The recipient of the message is specified by the "recipient" key, which can be "user" or "assistant". This is used to inform the LLM of who the message is intended for.

```python
[
  {"role": "user", "type": "message", "content": "Please create a plot from this data and display it as an image and then as HTML."}, # implied format: text (only one format for type message)
  {"role": "user", "type": "image", "format": "path", "content": "path/to/image.png"}
  {"role": "user", "type": "file", "content": "/path/to/file.pdf"} # implied format: path (only one format for type file)
  {"role": "assistant", "type": "message", "content": "Processing your request to generate a plot."} # implied format: text
  {"role": "assistant", "type": "code", "format": "python", "content": "plot = create_plot_from_data('data')\ndisplay_as_image(plot)\ndisplay_as_html(plot)"}
  {"role": "computer", "type": "image", "format": "base64.png", "content": "base64"}
  {"role": "computer", "type": "code", "format": "html", "content": "<html>Plot in HTML format</html>"}
  {"role": "computer", "type": "console", "format": "output", "content": "{HTML errors}"}
  {"role": "assistant", "type": "message", "content": "Plot generated successfully."} # implied format: text
]
```

## New Streaming Structure

- The streaming data structure closely matches the static messages structure, with only a few differences.
- Every streaming chunk has a "start" and "end" key, which are booleans that specify whether the chunk is the first or last chunk in the stream. This is what you should use to build messages from the streaming chunks.
- There is a "confirmation" chunk type, which is used to confirm with the user that the code should be run. The "content" key of this chunk is a dictionary with a `code` and a `language` key.
- Introducing more information per chunk is helpful in processing the streaming responses. Please take a look below for example code for processing streaming responses, in JavaScript.

```python
{"role": "assistant", "type": "message", "start": True}
{"role": "assistant", "type": "message", "content": "Pro"}
{"role": "assistant", "type": "message", "content": "cessing"}
{"role": "assistant", "type": "message", "content": "your request"}
{"role": "assistant", "type": "message", "content": "to generate a plot."}
{"role": "assistant", "type": "message", "end": True}

{"role": "assistant", "type": "code", "format": "python", "start": True}
{"role": "assistant", "type": "code", "format": "python", "content": "plot = create_plot_from_data"}
{"role": "assistant", "type": "code", "format": "python", "content": "('data')\ndisplay_as_image(plot)"}
{"role": "assistant", "type": "code", "format": "python", "content": "\ndisplay_as_html(plot)"}
{"role": "assistant", "type": "code", "format": "python", "end": True}

# The computer will emit a confirmation chunk *before* running the code. You can break here to cancel the execution.

{"role": "computer", "type": "confirmation", "format": "execution", "content": {
    "type": "code",
    "format": "python",
    "content": "plot = create_plot_from_data('data')\ndisplay_as_image(plot)\ndisplay_as_html(plot)",
}}

{"role": "computer", "type": "console", "start": True}
{"role": "computer", "type": "console", "format": "output", "content": "a printed statement"}
{"role": "computer", "type": "console", "format": "active_line", "content": "1"}
{"role": "computer", "type": "console", "format": "active_line", "content": "2"}
{"role": "computer", "type": "console", "format": "active_line", "content": "3"}
{"role": "computer", "type": "console", "format": "output", "content": "another printed statement"}
{"role": "computer", "type": "console", "end": True}
```

## Tips and Best Practices

- Adding an `id` and a `created_at` field to messages can be helpful to manipulate the messages later on.
- If you want your application to run the code instead of OI, then your app will act as the `computer`. This means breaking from the stream once OI emits a confirmation chunk (`{'role': 'computer', 'type': 'confirmation' ...}`) to prevent OI from running the code. When you run code, grab the message history via `messages = interpreter.messages`, then simply mimic the `computer` format above by appending new `{'role': 'computer' ...}` messages, then run `interpreter.chat(messages)`.
- Open Interpreter is designed to stop code execution when the stream is disconnected. Use this to your advantage to add a "Stop" button to the UI.
- Setting up your Python server to send errors and exceptions to the client can be helpful for debugging and generating error messages.

## Example Code

### Types

Python:

```python
class Message:
    role: Union["user", "assistant", "computer"]
    type: Union["message", "code", "image", "console", "file", "confirmation"]
    format: Union["output", "path", "base64.png", "base64.jpeg", "python", "javascript", "shell", "html", "active_line", "execution"]
    recipient: Union["user", "assistant"]
    content: Union[str, dict]  # dict should have 'code' and 'language' keys, this is only for confirmation messages

class StreamingChunk(Message):
    start: bool
    end: bool
```

TypeScript:

```typescript
interface Message {
  role: "user" | "assistant" | "computer";
  type: "message" | "code" | "image" | "console" | "file", | "confirmation";
  format: "output" | "path" | "base64.png" | "base64.jpeg" | "python" | "javascript" | "shell" | "html" | "active_line", | "execution";
  recipient: "user" | "assistant";
  content: string | { code: string; language: string };
}
```

```typescript
interface StreamingChunk extends Message {
  start: boolean;
  end: boolean;
}
```

### Handling streaming chunks

Here is a minimal example of how to handle streaming chunks in JavaScript. This example assumes that you are using a Python server to handle the streaming requests, and that you are using a JavaScript client to send the requests and handle the responses. See the main repository README for an example FastAPI server.

```javascript
//Javascript

let messages = []; //variable to hold all messages
let currentMessageIndex = 0; //variable to keep track of the current message index
let isGenerating = false; //variable to stop the stream

// Function to send a POST request to the OI
async function sendRequest() {
  // Temporary message to hold the message that is being processed
  try {
    // Define parameters for the POST request, add at least the full messages array, but you may also consider adding any other OI parameters here, like auto_run, local, etc.
    const params = {
      messages,
    };

    //Define a controller to allow for aborting the request
    const controller = new AbortController();
    const { signal } = controller;

    // Send the POST request to your Python server endpoint
    const interpreterCall = await fetch("https://YOUR_ENDPOINT/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(params),
      signal,
    });

    // Throw an error if the request was not successful
    if (!interpreterCall.ok) {
      console.error("Interpreter didn't respond with 200 OK");
      return;
    }

    // Initialize a reader for the response body
    const reader = interpreterCall.body.getReader();

    isGenerating = true;
    while (true) {
      const { value, done } = await reader.read();

      // Break the loop if the stream is done
      if (done) {
        break;
      }
      // If isGenerating is set to false, cancel the reader and break the loop. This will halt the execution of the code run by OI as well
      if (!isGenerating) {
        await reader.cancel();
        controller.abort();
        break;
      }
      // Decode the stream and split it into lines
      const text = new TextDecoder().decode(value);
      const lines = text.split("\n");
      lines.pop(); // Remove last empty line

      // Process each line of the response
      for (const line of lines) {
        const chunk = JSON.parse(line);
        await processChunk(chunk);
      }
    }
    //Stream has completed here, so run any code that needs to be run after the stream has finished
    if (isGenerating) isGenerating = false;
  } catch (error) {
    console.error("An error occurred:", error);
  }
}

//Function to process each chunk of the stream, and create messages
function processChunk(chunk) {
  if (chunk.start) {
    const tempMessage = {};
    //add the new message's data to the tempMessage
    tempMessage.role = chunk.role;
    tempMessage.type = chunk.type;
    tempMessage.content = "";
    if (chunk.format) tempMessage.format = chunk.format;
    if (chunk.recipient) tempMessage.recipient = chunk.recipient;

    //add the new message to the messages array, and set the currentMessageIndex to the index of the new message
    messages.push(tempMessage);
    currentMessageIndex = messages.length - 1;
  }

  //Handle active lines for code blocks
  if (chunk.format === "active_line") {
    messages[currentMessageIndex].activeLine = chunk.content;
  } else if (chunk.end && chunk.type === "console") {
    messages[currentMessageIndex].activeLine = null;
  }

  //Add the content of the chunk to current message, avoiding adding the content of the active line
  if (chunk.content && chunk.format !== "active_line") {
    messages[currentMessageIndex].content += chunk.content;
  }
}
```
