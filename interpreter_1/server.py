import asyncio
import json
import os
import time
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse


class ChatCompletionRequest:
    def __init__(
        self,
        messages: List[Dict[str, str]],
        stream: bool = False,
        model: Optional[str] = None,
    ):
        self.messages = messages
        self.stream = stream
        self.model = model


class Server:
    def __init__(self, interpreter):
        self.interpreter = interpreter

        # Get host/port from env vars or use defaults
        self.host = os.getenv("INTERPRETER_SERVER_HOST", "127.0.0.1")
        self.port = int(os.getenv("INTERPRETER_SERVER_PORT", "8000"))

        self.app = FastAPI(title="Open Interpreter API")

        # Setup routes
        self.app.post("/v1/chat/completions")(self.chat_completion)
        self.app.get("/v1/models")(self.list_models)

    async def list_models(self):
        """List available models endpoint"""
        return {
            "data": [
                {
                    "id": self.interpreter.model,
                    "object": "model",
                    "created": int(time.time()),
                    "owned_by": "open-interpreter",
                }
            ]
        }

    async def chat_completion(self, request: Request):
        """Main chat completion endpoint"""
        body = await request.json()
        req = ChatCompletionRequest(**body)

        # Update interpreter messages
        self.interpreter.messages = [
            {"role": msg["role"], "content": msg["content"]} for msg in req.messages
        ]

        if req.stream:
            return StreamingResponse(
                self._stream_response(), media_type="text/event-stream"
            )

        # For non-streaming, collect all chunks
        response_text = ""
        for chunk in self.interpreter.respond():
            if chunk.get("type") == "chunk":
                response_text += chunk["chunk"]

        return {
            "id": "chatcmpl-" + str(time.time()),
            "object": "chat.completion",
            "created": int(time.time()),
            "model": req.model or self.interpreter.model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": response_text},
                    "finish_reason": "stop",
                }
            ],
        }

    async def _stream_response(self):
        """Stream the response in OpenAI-compatible format"""
        for chunk in self.interpreter.respond():
            if chunk.get("type") == "chunk":
                data = {
                    "id": "chatcmpl-" + str(time.time()),
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": self.interpreter.model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": chunk["chunk"]},
                            "finish_reason": None,
                        }
                    ],
                }
                yield f"data: {json.dumps(data)}\n\n"
                await asyncio.sleep(0)

        # Send final chunk
        data = {
            "id": "chatcmpl-" + str(time.time()),
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": self.interpreter.model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }
        yield f"data: {json.dumps(data)}\n\n"
        yield "data: [DONE]\n\n"

    def run(self):
        """Start the server"""
        uvicorn.run(self.app, host=self.host, port=self.port)
