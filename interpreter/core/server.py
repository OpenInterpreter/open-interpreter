# This is a websocket interpreter, TTS and STT disabled.
# It makes a websocket on a port that sends/receives LMC messages in *streaming* format.

### You MUST send a start and end flag with each message! For example: ###

"""
{"role": "user", "type": "message", "start": True})
{"role": "user", "type": "message", "content": "hi"})
{"role": "user", "type": "message", "end": True})
"""

import asyncio
import json
import os
import threading

###
# from pynput import keyboard
# from RealtimeTTS import TextToAudioStream, OpenAIEngine, CoquiEngine
# from RealtimeSTT import AudioToTextRecorder
# from beeper import Beeper
import time
import traceback
from typing import Any, Dict, List

import uvicorn
from fastapi import FastAPI, Header, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel

# import argparse
# from profiles.default import interpreter
# from interpreter import interpreter

# Parse command line arguments for port number
# parser = argparse.ArgumentParser(description="FastAPI server.")
# parser.add_argument("--port", type=int, default=63863, help="Port to run on.")
# args = parser.parse_args()


# interpreter.tts = "openai"


class Settings(BaseModel):
    auto_run: bool
    custom_instructions: str
    model: str


class AsyncInterpreter:
    def __init__(self, interpreter):
        self.interpreter = interpreter

        # STT
        # self.stt = AudioToTextRecorder(use_microphone=False)
        # self.stt.stop() # It needs this for some reason

        # TTS
        # if self.interpreter.tts == "coqui":
        #     engine = CoquiEngine()
        # elif self.interpreter.tts == "openai":
        #     engine = OpenAIEngine()
        # self.tts = TextToAudioStream(engine)

        self.active_chat_messages = []

        # Clock
        # clock()

        # self.beeper = Beeper()

        # Startup sounds
        # self.beeper.beep("Blow")
        # self.tts.feed("Hi, how can I help you?")
        # self.tts.play_async(on_audio_chunk=self.on_tts_chunk, muted=True)

        self._input_queue = asyncio.Queue()  # Queue that .input will shove things into
        self._output_queue = asyncio.Queue()  # Queue to put output chunks into
        self._last_lmc_start_flag = None  # Unix time of last LMC start flag received
        self._in_keyboard_write_block = (
            False  # Tracks whether interpreter is trying to use the keyboard
        )

        self.loop = asyncio.get_event_loop()

    async def _add_to_queue(self, queue, item):
        print(f"Adding item to output", item)
        await queue.put(item)

    async def clear_queue(self, queue):
        while not queue.empty():
            await queue.get()

    async def clear_input_queue(self):
        await self.clear_queue(self._input_queue)

    async def clear_output_queue(self):
        await self.clear_queue(self._output_queue)

    async def input(self, chunk):
        """
        Expects a chunk in streaming LMC format.
        """
        if isinstance(chunk, bytes):
            # It's probably a chunk of audio
            # self.stt.feed_audio(chunk)
            pass
        else:
            try:
                chunk = json.loads(chunk)
            except:
                pass

            if "start" in chunk:
                # self.stt.start()
                self._last_lmc_start_flag = time.time()
                # self.interpreter.computer.terminal.stop() # Stop any code execution... maybe we should make interpreter.stop()?
            elif "end" in chunk:
                print("yep")
                asyncio.create_task(self.run())
            else:
                await self._add_to_queue(self._input_queue, chunk)

    def add_to_output_queue_sync(self, chunk):
        """
        Synchronous function to add a chunk to the output queue.
        """
        print("ADDING TO QUEUE:", chunk)
        asyncio.create_task(self._add_to_queue(self._output_queue, chunk))

    async def run(self):
        """
        Runs OI on the audio bytes submitted to the input. Will add streaming LMC chunks to the _output_queue.
        """
        print("heyyyy")
        self.interpreter.messages = self.active_chat_messages
        # interpreter.messages = self.active_chat_messages
        # self.beeper.start()

        # self.stt.stop()
        # message = self.stt.text()
        # print("THE MESSAGE:", message)

        input_queue = list(self._input_queue._queue)
        message = [i for i in input_queue if i["type"] == "message"][0]["content"]

        def generate(message):
            last_lmc_start_flag = self._last_lmc_start_flag
            self.interpreter.messages = self.active_chat_messages
            # interpreter.messages = self.active_chat_messages
            print("🍀🍀🍀🍀GENERATING, using these messages: ", self.interpreter.messages)
            print("🍀   🍀   🍀   🍀 active_chat_messages: ", self.active_chat_messages)
            print("passing this in:", message)
            for chunk in self.interpreter.chat(message, display=False, stream=True):
                print("FROM INTERPRETER. CHUNK:", chunk)

                if self._last_lmc_start_flag != last_lmc_start_flag:
                    # self.beeper.stop()
                    break

                # self.add_to_output_queue_sync(chunk) # To send text, not just audio

                content = chunk.get("content")

                # Handle message blocks
                if chunk.get("type") == "message":
                    self.add_to_output_queue_sync(chunk)  # To send text, not just audio
                    if content:
                        # self.beeper.stop()

                        # Experimental: The AI voice sounds better with replacements like these, but it should happen at the TTS layer
                        # content = content.replace(". ", ". ... ").replace(", ", ", ... ").replace("!", "! ... ").replace("?", "? ... ")

                        yield content

                # Handle code blocks
                elif chunk.get("type") == "code":
                    # if "start" in chunk:
                    # self.beeper.start()

                    # Experimental: If the AI wants to type, we should type immediately
                    if (
                        self.interpreter.messages[-1]
                        .get("content", "")
                        .startswith("computer.keyboard.write(")
                    ):
                        keyboard.controller.type(content)
                        self._in_keyboard_write_block = True
                    if "end" in chunk and self._in_keyboard_write_block:
                        self._in_keyboard_write_block = False
                        # (This will make it so it doesn't type twice when the block executes)
                        if self.interpreter.messages[-1]["content"].startswith(
                            "computer.keyboard.write("
                        ):
                            self.interpreter.messages[-1]["content"] = (
                                "dummy_variable = ("
                                + self.interpreter.messages[-1]["content"][
                                    len("computer.keyboard.write(") :
                                ]
                            )

            # Send a completion signal
            self.add_to_output_queue_sync(
                {"role": "server", "type": "completion", "content": "DONE"}
            )

        # Feed generate to RealtimeTTS
        # self.tts.feed(generate(message))
        for _ in generate(message):
            pass
        # self.tts.play_async(on_audio_chunk=self.on_tts_chunk, muted=True)

    async def output(self):
        return await self._output_queue.get()


def server(interpreter):
    interpreter.llm.model = "gpt-4"
    interpreter = AsyncInterpreter(interpreter)

    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],  # Allow all methods (GET, POST, etc.)
        allow_headers=["*"],  # Allow all headers
    )

    @app.post("/load")
    async def load(messages: List[Dict[str, Any]], settings: Settings):
        # Load messages
        interpreter.interpreter.messages = messages
        print("🪼🪼🪼🪼🪼🪼 Messages loaded: ", interpreter.interpreter.messages)

        # Load Settings
        interpreter.interpreter.llm.model = settings.model
        interpreter.interpreter.llm.custom_instructions = settings.custom_instructions
        interpreter.interpreter.auto_run = settings.auto_run

        interpreter.interpreter.llm.api_key = "<openai_key>"

        return {"status": "success"}

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        try:

            async def receive_input():
                while True:
                    data = await websocket.receive()
                    print(data)
                    if isinstance(data, bytes):
                        await interpreter.input(data)
                    else:
                        await interpreter.input(data["text"])

            async def send_output():
                while True:
                    output = await interpreter.output()
                    if isinstance(output, bytes):
                        # await websocket.send_bytes(output)
                        # we dont send out bytes rn, no TTS
                        pass
                    elif isinstance(output, dict):
                        print("sending:", output)
                        await websocket.send_text(json.dumps(output))

            await asyncio.gather(receive_input(), send_output())
        except Exception as e:
            print(f"WebSocket connection closed with exception: {e}")
            traceback.print_exc()
        finally:
            await websocket.close()

    class Rename(BaseModel):
        input: str

    @app.post("/rename-chat")
    async def rename_chat(body_content: Rename, x_api_key: str = Header(None)):
        print("RENAME CHAT REQUEST in PY 🌙🌙🌙🌙")
        input_value = body_content.input
        client = OpenAI(
            # defaults to os.environ.get("OPENAI_API_KEY")
            api_key=x_api_key,
        )
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "user",
                        "content": f"Given the following chat snippet, create a unique and descriptive title in less than 8 words. Your answer must not be related to customer service.\n\n{input_value}",
                    }
                ],
                temperature=0.3,
                stream=False,
            )
            print(response)
            completion = response["choices"][0]["message"]["content"]
            return {"data": {"content": completion}}
        except Exception as e:
            print(f"Error: {e}")
            traceback.print_exc()
            return {"error": str(e)}

    uvicorn.run(app, host="0.0.0.0", port=8000)
