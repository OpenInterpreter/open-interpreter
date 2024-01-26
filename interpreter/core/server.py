from typing import Generator

import uvicorn
from fastapi import Body, FastAPI, Request, Response
from fastapi.responses import PlainTextResponse, StreamingResponse


def server(interpreter, host="0.0.0.0", port=8000):
    app = FastAPI()

    @app.post("/chat")
    async def stream_endpoint(request: Request) -> Response:
        async def event_stream() -> Generator[str, None, None]:
            data = await request.json()
            for response in interpreter.chat(message=data["message"], stream=True):
                yield response

        return Response(event_stream(), media_type="text/event-stream")

    @app.post("/", response_class=PlainTextResponse)
    async def i_endpoint(request: Request):
        message = await request.body()
        message = message.decode("utf-8")  # Convert bytes to string

        async def event_stream() -> Generator[str, None, None]:
            for response in interpreter.chat(
                message=message, stream=True, display=False
            ):
                if (
                    response.get("type") == "message"
                    and response["role"] == "assistant"
                    and "content" in response
                ):
                    yield response["content"] + "\n"
                if (
                    response.get("type") == "message"
                    and response["role"] == "assistant"
                    and response.get("end") == True
                ):
                    yield " \n"

        return StreamingResponse(event_stream(), media_type="text/plain")

    uvicorn.run(app, host=host, port=port)
