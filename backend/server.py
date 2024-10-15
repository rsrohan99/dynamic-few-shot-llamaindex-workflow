import json

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from pydantic import BaseModel
from llama_index.utils.workflow import draw_all_possible_flows

from models import ChatData
from workflow import CustomerSupportWorkflow, StreamEvent

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    message: str


@app.post("/chat")
async def chat(request: Request, data: ChatData):
    try:
        last_message = data.get_last_message_content()
        messages = data.get_history_messages()
        workflow = CustomerSupportWorkflow(
            timeout=360,
            chat_history=messages,
            last_message=last_message,
        )
        # draw_all_possible_flows(workflow)
        handler = workflow.run()
        # return result["response"]

        await handler

        async def event_generator():
            async for ev in handler.stream_events():
                if await request.is_disconnected():
                    break
                if isinstance(ev, StreamEvent):
                    yield f"0:{json.dumps(ev.token)}\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"X-Experimental-Stream-Data": "true"},
        )

    except Exception as e:
        # logger.exception("Error in chat engine", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error in workflow: {e}",
        ) from e


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app)
