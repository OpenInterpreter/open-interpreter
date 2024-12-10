import asyncio
import json
import os
import time
from typing import Any, Dict, List, Optional, Union

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from asyncio import CancelledError, Task


class ChatCompletionRequest(BaseModel):
    messages: List[Dict[str, Union[str, list, None]]]
    stream: bool = False
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    tools: Optional[List[Dict[str, Any]]] = None


class Server:
    def __init__(self, interpreter):
        self.interpreter = interpreter

        # Get host/port from env vars or use defaults
        self.host = os.getenv("INTERPRETER_SERVER_HOST", "127.0.0.1")
        self.port = int(os.getenv("INTERPRETER_SERVER_PORT", "8000"))

        self.app = FastAPI(title="Open Interpreter API")

        # Setup routes
        self.app.post("/chat/completions")(self.chat_completion)


    async def chat_completion(self, request: Request):
        """Main chat completion endpoint"""
        body = await request.json()
        if self.interpreter.debug:
            print("Request body:", body)
        try:
            req = ChatCompletionRequest(**body)
        except Exception as e:
            print("Validation error:", str(e))
            print("Request body:", body)
            raise

        # Filter out system message
        req.messages = [msg for msg in req.messages if msg["role"] != "system"]

        # Update interpreter messages
        self.interpreter.messages = req.messages

        if req.stream:
            return StreamingResponse(
                self._stream_response(), media_type="text/event-stream"
            )

        raise NotImplementedError("Non-streaming is not supported yet")

    async def _stream_response(self):
        """Stream the response in OpenAI-compatible format"""
        try:
            async for chunk in self.interpreter.async_respond():
                # Convert tool_calls to dict if present
                choices = []
                for choice in chunk.choices:
                    delta = {}
                    if choice.delta:
                        if choice.delta.content is not None:
                            delta["content"] = choice.delta.content
                        if choice.delta.role is not None:
                            delta["role"] = choice.delta.role
                        if choice.delta.function_call is not None:
                            delta["function_call"] = choice.delta.function_call
                        if choice.delta.tool_calls is not None:
                            pass

                    choices.append(
                        {
                            "index": choice.index,
                            "delta": delta,
                            "finish_reason": choice.finish_reason,
                        }
                    )

                data = {
                    "id": chunk.id,
                    "object": chunk.object,
                    "created": chunk.created,
                    "model": chunk.model,
                    "choices": choices,
                }

                if hasattr(chunk, "system_fingerprint"):
                    data["system_fingerprint"] = chunk.system_fingerprint

                yield f"data: {json.dumps(data)}\n\n"

        except CancelledError:
            # Handle cancellation gracefully
            print("Request cancelled - cleaning up...")

            raise
        except Exception as e:
            print(f"Error in stream: {str(e)}")
        finally:
            # Always send DONE message and cleanup
            yield "data: [DONE]\n\n"

    def run(self):
        """Start the server"""
        uvicorn.run(self.app, host=self.host, port=self.port)
