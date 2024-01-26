from typing import Generator

import uvicorn
from fastapi import FastAPI, Request, Response


def server(interpreter, host="0.0.0.0", port=8000):
    app = FastAPI()

    @app.post("/chat")
    async def stream_endpoint(request: Request) -> Response:
        async def event_stream() -> Generator[str, None, None]:
            data = await request.json()
            for response in interpreter.chat(message=data["message"], stream=True):
                yield response

        return Response(event_stream(), media_type="text/event-stream")

    uvicorn.run(app, host=host, port=port)
