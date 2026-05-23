"""
Web API — FastAPI backend với WebSocket streaming.
Chạy: uvicorn interfaces.web.api:app --reload --port 8000
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from uuid import uuid4
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agent.core import Agent
from agent.default_task import get_default_task
from agent.memory import Memory

# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(title="Local AI Coding Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (Web UI)
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Global agent instance (shared across connections)
_agent: Agent | None = None

# In-memory task state for REST clients. This is intentionally simple for a
# local agent; persist it later if you need restart-safe orchestration.
TASKS: dict[str, dict] = {}
MAX_TASK_EVENTS = 500


def get_agent() -> Agent:
    global _agent
    if _agent is None:
        model = os.getenv("AGENT_MODEL", "qwen3:8b")
        url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        _agent = Agent(model=model, ollama_url=url)
    return _agent


class TaskRequest(BaseModel):
    task: str = ""
    model: str | None = None
    auto_confirm: bool = False
    max_steps: int | None = Field(default=None, ge=1, le=100)


class ConfirmRequest(BaseModel):
    confirmation_id: str
    confirmed: bool


def _task_view(task_id: str) -> dict:
    state = TASKS[task_id]
    return {
        "task_id": task_id,
        "status": state["status"],
        "task": state["task"],
        "created_at": state["created_at"],
        "updated_at": state["updated_at"],
        "model": state["model"],
        "pending_confirmation": state.get("pending_confirmation"),
        "answer": state.get("answer"),
        "error": state.get("error"),
        "events": state["events"],
    }


def _append_task_event(state: dict, event: dict) -> None:
    state["events"].append(event)
    state["updated_at"] = time.time()
    if len(state["events"]) > MAX_TASK_EVENTS:
        state["events"] = state["events"][-MAX_TASK_EVENTS:]


async def _run_rest_task(task_id: str) -> None:
    state = TASKS[task_id]
    agent = Agent(
        model=state["model"],
        ollama_url=state["ollama_url"],
        max_steps=state["max_steps"],
    )
    agent.safety.auto_confirm = state["auto_confirm"]

    async def confirm_fn(tool_name: str, args: dict) -> bool:
        confirmation_id = str(uuid4())
        prompt = agent.safety.format_confirmation_prompt(tool_name, args)
        request = {
            "confirmation_id": confirmation_id,
            "tool": tool_name,
            "args": args,
            "prompt": prompt,
        }
        state["status"] = "waiting_confirmation"
        state["pending_confirmation"] = request
        _append_task_event(state, {"type": "confirm_request", "data": request})

        try:
            response = await asyncio.wait_for(state["confirm_queue"].get(), timeout=3600.0)
        except asyncio.TimeoutError:
            state["pending_confirmation"] = None
            _append_task_event(state, {
                "type": "error",
                "data": {"message": "Confirmation timed out."},
            })
            return False

        state["pending_confirmation"] = None
        state["status"] = "running"
        return bool(response.get("confirmed"))

    state["status"] = "running"
    _append_task_event(state, {"type": "start", "data": {"task": state["task"]}})

    try:
        async for event in agent.stream(state["task"], confirm_fn=confirm_fn):
            _append_task_event(state, event)
            if event["type"] == "final":
                state["status"] = "completed"
                state["answer"] = event["data"].get("answer", "")
            elif event["type"] == "error":
                state["status"] = "failed"
                state["error"] = event["data"].get("message", "Unknown error")
    except Exception as e:
        state["status"] = "failed"
        state["error"] = str(e)
        _append_task_event(state, {"type": "error", "data": {"message": str(e)}})
    finally:
        state["updated_at"] = time.time()
        await agent.close()


# ── REST endpoints ────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    index = STATIC_DIR / "index.html"
    return FileResponse(str(index))


@app.get("/api/health")
async def health():
    import httpx
    agent = get_agent()
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{agent.ollama_url}/api/tags")
            models = [m["name"] for m in r.json().get("models", [])]
        return {"status": "ok", "model": agent.model, "models": models}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.get("/api/models")
async def list_models():
    import httpx
    agent = get_agent()
    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.get(f"{agent.ollama_url}/api/tags")
    return r.json()


@app.post("/api/model")
async def set_model(body: dict):
    global _agent
    model = body.get("model", "qwen3:8b")
    if _agent:
        _agent.model = model
    return {"model": model}


@app.get("/api/history")
async def get_history(n: int = 20):
    mem = Memory()
    return {"turns": mem.get_recent(n)}


@app.delete("/api/history")
async def clear_history():
    agent = get_agent()
    agent.memory.clear_short()
    return {"status": "cleared"}


@app.get("/api/stats")
async def get_stats():
    mem = Memory()
    return mem.get_stats()


@app.post("/api/tasks")
async def create_task(body: TaskRequest):
    """Create an async agent task from an external client."""
    task_id = str(uuid4())
    base_agent = get_agent()
    task = body.task.strip() or get_default_task()
    state = {
        "task": task,
        "status": "queued",
        "created_at": time.time(),
        "updated_at": time.time(),
        "model": body.model or base_agent.model,
        "ollama_url": base_agent.ollama_url,
        "max_steps": body.max_steps or base_agent.max_steps,
        "auto_confirm": body.auto_confirm,
        "confirm_queue": asyncio.Queue(),
        "pending_confirmation": None,
        "answer": None,
        "error": None,
        "events": [],
    }
    TASKS[task_id] = state
    asyncio.create_task(_run_rest_task(task_id))
    return _task_view(task_id)


@app.get("/api/tasks")
async def list_tasks():
    return {"tasks": [_task_view(task_id) for task_id in reversed(list(TASKS.keys()))]}


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    if task_id not in TASKS:
        raise HTTPException(status_code=404, detail="Task not found")
    return _task_view(task_id)


@app.post("/api/tasks/{task_id}/confirm")
async def confirm_task(task_id: str, body: ConfirmRequest):
    if task_id not in TASKS:
        raise HTTPException(status_code=404, detail="Task not found")

    state = TASKS[task_id]
    pending = state.get("pending_confirmation")
    if not pending:
        raise HTTPException(status_code=409, detail="Task is not waiting for confirmation")
    if pending["confirmation_id"] != body.confirmation_id:
        raise HTTPException(status_code=409, detail="Confirmation id does not match pending request")

    await state["confirm_queue"].put({
        "confirmation_id": body.confirmation_id,
        "confirmed": body.confirmed,
    })
    _append_task_event(state, {
        "type": "confirm_response",
        "data": {
            "confirmation_id": body.confirmation_id,
            "confirmed": body.confirmed,
        },
    })
    return {"status": "accepted", "task_id": task_id}


# ── WebSocket streaming ───────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    agent = get_agent()

    try:
        while True:
            # Receive task from client
            raw = await ws.receive_text()
            data = json.loads(raw)
            task = data.get("task", "").strip()

            if not task:
                task = get_default_task()

            # Handle settings update
            if data.get("type") == "settings":
                if "model" in data:
                    agent.model = data["model"]
                if "auto_confirm" in data:
                    agent.safety.auto_confirm = data["auto_confirm"]
                await ws.send_json({"type": "settings_updated"})
                continue

            # Stream agent progress back to client
            async def confirm_fn(tool_name: str, args: dict) -> bool:
                """Ask client for confirmation via WebSocket."""
                await ws.send_json({
                    "type": "confirm_request",
                    "data": {
                        "tool": tool_name,
                        "args": args,
                        "prompt": agent.safety.format_confirmation_prompt(tool_name, args),
                    }
                })
                # Wait for client response
                response = await asyncio.wait_for(ws.receive_text(), timeout=60.0)
                resp_data = json.loads(response)
                return resp_data.get("confirmed", False)

            await ws.send_json({"type": "start", "data": {"task": task}})

            async for event in agent.stream(task, confirm_fn=confirm_fn):
                await ws.send_json(event)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await ws.send_json({"type": "error", "data": {"message": str(e)}})
        except Exception:
            pass


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("interfaces.web.api:app", host="0.0.0.0", port=8000, reload=True)
