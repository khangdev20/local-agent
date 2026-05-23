"""
Web API — FastAPI backend với WebSocket streaming.
Chạy: uvicorn interfaces.web.api:app --reload --port 8000
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent.core import Agent
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


def get_agent() -> Agent:
    global _agent
    if _agent is None:
        model = os.getenv("AGENT_MODEL", "qwen2.5-coder:7b")
        url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        _agent = Agent(model=model, ollama_url=url)
    return _agent


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
    model = body.get("model", "qwen2.5-coder:7b")
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
                await ws.send_json({"type": "error", "data": {"message": "Empty task"}})
                continue

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
