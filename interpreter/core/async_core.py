import asyncio
import json
import os
import socket
import threading
import time
import traceback
from datetime import datetime
from typing import Any, Dict

from .core import OpenInterpreter

try:
    import janus
    import uvicorn
    from fastapi import APIRouter, FastAPI, WebSocket
    from fastapi.responses import PlainTextResponse
except:
    # Server dependencies are not required by the main package.
    pass


class AsyncInterpreter(OpenInterpreter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.respond_thread = None
        self.stop_event = threading.Event()
        self.output_queue = None
        self.id = os.getenv("INTERPRETER_ID", datetime.now().timestamp())
        self.print = True  # Will print output

        self.server = Server(self)

    async def input(self, chunk):
        """
        Accumulates LMC chunks onto interpreter.messages.
        When it hits an "end" flag, calls interpreter.respond().
        """

        if "start" in chunk:
            # If the user is starting something, the interpreter should stop.
            if self.respond_thread is not None and self.respond_thread.is_alive():
                self.stop_event.set()
                self.respond_thread.join()
            self.accumulate(chunk)
        elif "content" in chunk:
            self.accumulate(chunk)
        elif "end" in chunk:
            # If the user is done talking, the interpreter should respond.

            run_code = None  # Will later default to auto_run unless the user makes a command here

            # But first, process any commands.
            if self.messages[-1]["type"] == "command":
                command = self.messages[-1]["content"]
                self.messages = self.messages[:-1]

                if command == "stop":
                    # Any start flag would have stopped it a moment ago, but to be sure:
                    self.stop_event.set()
                    self.respond_thread.join()
                    return
                if command == "go":
                    # This is to approve code.
                    run_code = True
                    pass

            self.stop_event.clear()
            self.respond_thread = threading.Thread(
                target=self.respond, args=(run_code,)
            )
            self.respond_thread.start()

    async def output(self):
        if self.output_queue == None:
            self.output_queue = janus.Queue()
        return await self.output_queue.async_q.get()

    def respond(self, run_code=None):
        try:
            if run_code == None:
                run_code = self.auto_run

            for chunk_og in self._respond_and_store():
                chunk = (
                    chunk_og.copy()
                )  # This fixes weird double token chunks. Probably a deeper problem?

                if chunk["type"] == "confirmation":
                    if run_code:
                        run_code = False
                        continue
                    else:
                        break

                if self.stop_event.is_set():
                    return

                if self.print:
                    if "start" in chunk:
                        print("\n")
                    if chunk["type"] in ["code", "console"] and "format" in chunk:
                        if "start" in chunk:
                            print("\n------------\n\n```" + chunk["format"], flush=True)
                        if "end" in chunk:
                            print("\n```\n\n------------\n\n", flush=True)
                    if chunk.get("format") != "active_line":
                        print(chunk.get("content", ""), end="", flush=True)

                self.output_queue.sync_q.put(chunk)

            self.output_queue.sync_q.put(
                {"role": "server", "type": "status", "content": "complete"}
            )
        except Exception as e:
            error = traceback.format_exc() + "\n" + str(e)
            error_message = {
                "role": "server",
                "type": "error",
                "content": traceback.format_exc() + "\n" + str(e),
            }
            self.output_queue.sync_q.put(error_message)
            print("\n\n--- SENT ERROR: ---\n\n")
            print(error)
            print("\n\n--- (ERROR ABOVE WAS SENT) ---\n\n")

    def accumulate(self, chunk):
        """
        Accumulates LMC chunks onto interpreter.messages.
        """
        if type(chunk) == str:
            chunk = json.loads(chunk)

        if type(chunk) == dict:
            if chunk.get("format") == "active_line":
                # We don't do anything with these.
                pass

            elif (
                "start" in chunk
                or chunk["type"] != self.messages[-1]["type"]
                or chunk.get("format") != self.messages[-1].get("format")
            ):
                chunk_copy = (
                    chunk.copy()
                )  # So we don't modify the original chunk, which feels wrong.
                chunk_copy.pop("start")
                chunk_copy["content"] = ""
                self.messages.append(chunk_copy)

            elif "content" in chunk:
                self.messages[-1]["content"] += chunk["content"]

        elif type(chunk) == bytes:
            if self.messages[-1]["content"] == "":  # We initialize as an empty string ^
                self.messages[-1]["content"] = b""  # But it actually should be bytes
            self.messages[-1]["content"] += chunk


def create_router(async_interpreter):
    router = APIRouter()

    @router.get("/heartbeat")
    async def heartbeat():
        return {"status": "alive"}

    @router.get("/")
    async def home():
        return PlainTextResponse(
            """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Chat</title>
            </head>
            <body>
                <form action="" onsubmit="sendMessage(event)">
                    <textarea id="messageInput" rows="10" cols="50" autocomplete="off"></textarea>
                    <button>Send</button>
                </form>
                <button id="approveCodeButton">Approve Code</button>
                <div id="messages"></div>
                <script>
                    var ws = new WebSocket("ws://"""
            + async_interpreter.server.host
            + ":"
            + str(async_interpreter.server.port)
            + """/");
                    var lastMessageElement = null;
                    ws.onmessage = function(event) {
                        if (lastMessageElement == null) {
                            lastMessageElement = document.createElement('p');
                            document.getElementById('messages').appendChild(lastMessageElement);
                            lastMessageElement.innerHTML = "<br>"
                        }
                        var eventData = JSON.parse(event.data);

                        if ((eventData.role == "assistant" && eventData.type == "message" && eventData.content) ||
                            (eventData.role == "computer" && eventData.type == "console" && eventData.format == "output" && eventData.content) ||
                            (eventData.role == "assistant" && eventData.type == "code" && eventData.content)) {
                            lastMessageElement.innerHTML += eventData.content;
                        } else {
                            lastMessageElement.innerHTML += "<br><br>" + JSON.stringify(eventData) + "<br><br>";
                        }
                    };
                    function sendMessage(event) {
                        event.preventDefault();
                        var input = document.getElementById("messageInput");
                        var message = input.value;
                        if (message.startsWith('{') && message.endsWith('}')) {
                            message = JSON.stringify(JSON.parse(message));
                            ws.send(message);
                        } else {
                            var startMessageBlock = {
                                "role": "user",
                                "type": "message",
                                "start": true
                            };
                            ws.send(JSON.stringify(startMessageBlock));

                            var messageBlock = {
                                "role": "user",
                                "type": "message",
                                "content": message
                            };
                            ws.send(JSON.stringify(messageBlock));

                            var endMessageBlock = {
                                "role": "user",
                                "type": "message",
                                "end": true
                            };
                            ws.send(JSON.stringify(endMessageBlock));
                        }
                        var userMessageElement = document.createElement('p');
                        userMessageElement.innerHTML = '<b>' + input.value + '</b><br>';
                        document.getElementById('messages').appendChild(userMessageElement);
                        lastMessageElement = document.createElement('p');
                        document.getElementById('messages').appendChild(lastMessageElement);
                        input.value = '';
                    }
                function approveCode() {
                    var startCommandBlock = {
                        "role": "user",
                        "type": "command",
                        "start": true
                    };
                    ws.send(JSON.stringify(startCommandBlock));

                    var commandBlock = {
                        "role": "user",
                        "type": "command",
                        "content": "go"
                    };
                    ws.send(JSON.stringify(commandBlock));

                    var endCommandBlock = {
                        "role": "user",
                        "type": "command",
                        "end": true
                    };
                    ws.send(JSON.stringify(endCommandBlock));
                }

                document.getElementById("approveCodeButton").addEventListener("click", approveCode);
                </script>
            </body>
            </html>
            """,
            media_type="text/html",
        )

    @router.websocket("/")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        try:

            async def receive_input():
                while True:
                    try:
                        data = await websocket.receive()

                        if False:
                            print("Received:", data)

                        if data.get("type") == "websocket.receive":
                            if "text" in data:
                                data = json.loads(data["text"])
                            elif "bytes" in data:
                                data = data["bytes"]
                            await async_interpreter.input(data)
                        elif data.get("type") == "websocket.disconnect":
                            print("Disconnecting.")
                            return
                        else:
                            print("Invalid data:", data)
                            continue

                    except Exception as e:
                        error = traceback.format_exc() + "\n" + str(e)
                        error_message = {
                            "role": "server",
                            "type": "error",
                            "content": traceback.format_exc() + "\n" + str(e),
                        }
                        await websocket.send_text(json.dumps(error_message))
                        print("\n\n--- SENT ERROR: ---\n\n")
                        print(error)
                        print("\n\n--- (ERROR ABOVE WAS SENT) ---\n\n")

            async def send_output():
                while True:
                    try:
                        output = await async_interpreter.output()
                        # print("Attempting to send the following output:", output)

                        for attempt in range(100):
                            try:
                                if isinstance(output, bytes):
                                    await websocket.send_bytes(output)
                                else:
                                    await websocket.send_text(json.dumps(output))
                                # print("Output sent successfully. Output was:", output)
                                break
                            except Exception as e:
                                print(
                                    "Failed to send output on attempt number:",
                                    attempt + 1,
                                    ". Output was:",
                                    output,
                                )
                                print("Error:", str(e))
                                await asyncio.sleep(0.05)
                        else:
                            raise Exception(
                                "Failed to send after 100 attempts. Output was:",
                                str(output),
                            )
                    except Exception as e:
                        error = traceback.format_exc() + "\n" + str(e)
                        error_message = {
                            "role": "server",
                            "type": "error",
                            "content": traceback.format_exc() + "\n" + str(e),
                        }
                        await websocket.send_text(json.dumps(error_message))
                        print("\n\n--- SENT ERROR: ---\n\n")
                        print(error)
                        print("\n\n--- (ERROR ABOVE WAS SENT) ---\n\n")

            await asyncio.gather(receive_input(), send_output())
        except Exception as e:
            try:
                error = traceback.format_exc() + "\n" + str(e)
                error_message = {
                    "role": "server",
                    "type": "error",
                    "content": traceback.format_exc() + "\n" + str(e),
                }
                await websocket.send_text(json.dumps(error_message))
                print("\n\n--- SENT ERROR: ---\n\n")
                print(error)
                print("\n\n--- (ERROR ABOVE WAS SENT) ---\n\n")
            except:
                # If we can't send it, that's fine.
                pass
        finally:
            await websocket.close()

    # TODO
    @router.post("/")
    async def post_input(payload: Dict[str, Any]):
        try:
            async_interpreter.input(payload)
            return {"status": "success"}
        except Exception as e:
            return {"error": str(e)}, 500

    @router.post("/run")
    async def run_code(payload: Dict[str, Any]):
        language, code = payload.get("language"), payload.get("code")
        if not (language and code):
            return {"error": "Both 'language' and 'code' are required."}, 400
        try:
            print(f"Running {language}:", code)
            output = async_interpreter.computer.run(language, code)
            print("Output:", output)
            return {"output": output}
        except Exception as e:
            return {"error": str(e)}, 500

    @router.post("/settings")
    async def set_settings(payload: Dict[str, Any]):
        for key, value in payload.items():
            print(f"Updating settings: {key} = {value}")
            if key in ["llm", "computer"] and isinstance(value, dict):
                if hasattr(async_interpreter, key):
                    for sub_key, sub_value in value.items():
                        if hasattr(getattr(async_interpreter, key), sub_key):
                            setattr(getattr(async_interpreter, key), sub_key, sub_value)
                        else:
                            return {
                                "error": f"Sub-setting {sub_key} not found in {key}"
                            }, 404
                else:
                    return {"error": f"Setting {key} not found"}, 404
            elif hasattr(async_interpreter, key):
                setattr(async_interpreter, key, value)
            else:
                return {"error": f"Setting {key} not found"}, 404

        return {"status": "success"}

    @router.get("/settings/{setting}")
    async def get_setting(setting: str):
        if hasattr(async_interpreter, setting):
            setting_value = getattr(async_interpreter, setting)
            try:
                return json.dumps({setting: setting_value})
            except TypeError:
                return {"error": "Failed to serialize the setting value"}, 500
        else:
            return json.dumps({"error": "Setting not found"}), 404

    return router


host = os.getenv(
    "HOST", "127.0.0.1"
)  # IP address for localhost, used for local testing. To expose to local network, use 0.0.0.0
port = int(os.getenv("PORT", 8000))  # Default port is 8000

# FOR TESTING ONLY
# host = "0.0.0.0"


class Server:
    def __init__(self, async_interpreter, host=host, port=port):
        self.app = FastAPI()
        router = create_router(async_interpreter)
        self.app.include_router(router)
        self.host = host
        self.port = port

    def run(self, retries=5, *args, **kwargs):
        print("SERVER STARTING")

        if "host" in kwargs:
            self.host = kwargs.pop("host")
        if "port" in kwargs:
            self.port = kwargs.pop("port")
        if "app" in kwargs:
            self.app = kwargs.pop("app")

        if self.host == "0.0.0.0":
            print(
                "Warning: Using host `0.0.0.0` will expose Open Interpreter over your local network."
            )
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))  # Google's public DNS server
            print(f"Server is running at http://{s.getsockname()[0]}:{self.port}")
            s.close()

        for _ in range(retries):
            try:
                uvicorn.run(
                    app=self.app, host=self.host, port=self.port, *args, **kwargs
                )
                break
            except KeyboardInterrupt:
                break
            except ImportError as e:
                if _ == 4:  # If this is the last attempt
                    raise ImportError(
                        str(e)
                        + """\n\nPlease ensure you have run `pip install "open-interpreter[server]"` to install server dependencies."""
                    )
            except:
                print("An unexpected error occurred:", traceback.format_exc())
                print("SERVER RESTARTING")
        print("SERVER SHUTDOWN")
