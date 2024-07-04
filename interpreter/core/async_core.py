import asyncio
import json
import os
import threading
import traceback
from datetime import datetime
from typing import Any, Dict

from .core import OpenInterpreter

try:
    import janus
    import uvicorn
    from fastapi import APIRouter, FastAPI, WebSocket
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
        if run_code == None:
            run_code = self.auto_run

        for chunk in self._respond_and_store():
            if chunk["type"] == "confirmation":
                if run_code:
                    continue  # We don't need to send out confirmation chunks on the server. I don't even like them.
                else:
                    break

            if self.stop_event.is_set():
                return

            if self.print:
                if chunk["type"] in ["code", "output"]:
                    if "start" in chunk:
                        print("\n\n```" + chunk["format"], flush=True)
                    if "end" in chunk:
                        print("\n```", flush=True)
                print(chunk.get("content", ""), end="", flush=True)

            self.output_queue.sync_q.put(chunk)

        self.output_queue.sync_q.put(
            {"role": "assistant", "type": "status", "content": "complete"}
        )

    def accumulate(self, chunk):
        """
        Accumulates LMC chunks onto interpreter.messages.
        """
        if type(chunk) == dict:
            if chunk.get("format") == "active_line":
                # We don't do anything with these.
                pass

            elif "start" in chunk:
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

    @router.websocket("/")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        try:

            async def receive_input():
                while True:
                    try:
                        data = await websocket.receive()

                        if data.get("type") == "websocket.receive" and "text" in data:
                            data = json.loads(data["text"])
                            await async_interpreter.input(data)
                        elif (
                            data.get("type") == "websocket.disconnect"
                            and data.get("code") == 1000
                        ):
                            print("Disconnecting.")
                            return
                        else:
                            print("Invalid data:", data)
                            continue

                    except Exception as e:
                        error_message = {
                            "role": "server",
                            "type": "error",
                            "content": traceback.format_exc() + "\n" + str(e),
                        }
                        await websocket.send_text(json.dumps(error_message))

            async def send_output():
                while True:
                    try:
                        output = await async_interpreter.output()

                        if isinstance(output, bytes):
                            await websocket.send_bytes(output)
                        else:
                            await websocket.send_text(json.dumps(output))
                    except Exception as e:
                        traceback.print_exc()
                        error_message = {
                            "role": "server",
                            "type": "error",
                            "content": traceback.format_exc() + "\n" + str(e),
                        }
                        await websocket.send_text(json.dumps(error_message))

            await asyncio.gather(receive_input(), send_output())
        except Exception as e:
            traceback.print_exc()
            try:
                error_message = {
                    "role": "server",
                    "type": "error",
                    "content": traceback.format_exc() + "\n" + str(e),
                }
                await websocket.send_text(json.dumps(error_message))
            except:
                # If we can't send it, that's fine.
                pass
        finally:
            await websocket.close()

    @router.post("/run")
    async def run_code(payload: Dict[str, Any]):
        language, code = payload.get("language"), payload.get("code")
        if not (language and code):
            return {"error": "Both 'language' and 'code' are required."}, 400
        try:
            return {"output": async_interpreter.computer.run(language, code)}
        except Exception as e:
            return {"error": str(e)}, 500

    @router.post("/settings")
    async def set_settings(payload: Dict[str, Any]):
        for key, value in payload.items():
            print(f"Updating settings: {key} = {value}")
            if key in ["llm", "computer"] and isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    setattr(getattr(async_interpreter, key), sub_key, sub_value)
            else:
                setattr(async_interpreter, key, value)

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


class Server:
    def __init__(self, async_interpreter, host="0.0.0.0", port=8000):
        self.app = FastAPI()
        router = create_router(async_interpreter)
        self.app.include_router(router)
        self.host = host
        self.port = port
        self.uvicorn_server = uvicorn.Server(
            config=uvicorn.Config(app=self.app, host=self.host, port=self.port)
        )

    def run(self):
        try:
            self.uvicorn_server.run()
        except ImportError as e:
            raise ImportError(
                str(e)
                + """\n\nPlease ensure you have run `pip install "open-interpreter[server]"` to install server dependencies."""
            )
