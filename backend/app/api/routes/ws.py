import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from backend.app.core.events import event_bus, AgentEvent
from backend.app.core.logging import logger

router = APIRouter(tags=["Real-Time Streaming"])

@router.websocket("/ws/{conversation_id}")
async def websocket_endpoint(websocket: WebSocket, conversation_id: str):
    await websocket.accept()
    queue = await event_bus.subscribe(conversation_id)
    logger.info(f"WebSocket client connected for conversation: {conversation_id}")

    try:
        while True:
            # We can concurrently receive client ping/messages and send agent events
            event: AgentEvent = await queue.get()
            await websocket.send_text(event.model_dump_json())
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for conversation: {conversation_id}")
    except Exception as e:
        logger.warning(f"WebSocket error: {e}")
    finally:
        await event_bus.unsubscribe(queue, conversation_id)

@router.get("/stream/{conversation_id}")
async def sse_endpoint(conversation_id: str):
    """Server-Sent Events fallback streaming for conversations"""
    queue = await event_bus.subscribe(conversation_id)

    async def event_generator():
        try:
            while True:
                event: AgentEvent = await queue.get()
                payload = json.dumps(event.model_dump())
                yield f"data: {payload}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            await event_bus.unsubscribe(queue, conversation_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
