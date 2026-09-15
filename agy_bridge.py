"""
⚡ AGY Bridge — Persistent Antigravity AI Local HTTP Server
============================================================
Keeps ONE warm `agy --input-format stream-json` process alive.
Exposes: POST http://localhost:8400/analyze
Response time: ~3-5s (vs 35s cold-start subprocess)

Features:
  • Persistent agy process — no cold-start overhead
  • In-memory response cache (TTL = 5 min for 15M, 20 min for 4H)
  • Async request queue — thread-safe single-process piping
  • Auto-restart agy if it crashes
  • GET /health  → status check
  • GET /cache   → cache stats
"""

import asyncio
import hashlib
import json
import os
import re
import shutil
import time
import threading
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

# ── Config ─────────────────────────────────────────────────────
PORT            = 8400
AGY_BIN         = shutil.which("agy") or os.path.expanduser("~/.local/bin/agy")
CACHE_TTL_15M   = 300    # 5 minutes
CACHE_TTL_4H    = 1200   # 20 minutes
MAX_RESPONSE_WAIT = 120  # seconds to wait for agy response

# ── FastAPI app ─────────────────────────────────────────────────
app = FastAPI(title="AGY Bridge", version="1.0")

# ── State ───────────────────────────────────────────────────────
class AgyBridge:
    def __init__(self):
        self.process: Optional[asyncio.subprocess.Process] = None
        self.lock = asyncio.Lock()
        self.cache: dict = {}           # key → (result, timestamp)
        self.stats = {"hits": 0, "misses": 0, "errors": 0, "requests": 0}
        self.conversation_id: Optional[str] = None
        self.started_at = time.time()

    async def start_process(self):
        """Launch a fresh persistent agy stream-json process."""
        if self.process and self.process.returncode is None:
            return  # already running

        print(f"[AGY-BRIDGE] Starting persistent agy process: {AGY_BIN}")
        self.process = await asyncio.create_subprocess_exec(
            AGY_BIN,
            "--input-format", "stream-json",
            "--output-format", "stream-json",
            "--dangerously-skip-permissions",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )

        # Read the init event to confirm startup
        init_line = await asyncio.wait_for(
            self.process.stdout.readline(), timeout=15.0
        )
        init_data = json.loads(init_line.decode().strip())
        self.conversation_id = init_data.get("init", {}).get("conversation_id") or \
                               init_data.get("conversation_id", "unknown")
        print(f"[AGY-BRIDGE] ✅ agy ready — conversation_id: {self.conversation_id}")

    async def restart_process(self):
        """Kill and restart the agy process."""
        print("[AGY-BRIDGE] ♻️  Restarting agy process...")
        try:
            if self.process and self.process.returncode is None:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=5)
        except Exception:
            pass
        self.process = None
        self.conversation_id = None
        await self.start_process()

    def cache_key(self, prompt: str) -> str:
        return hashlib.md5(prompt.encode()).hexdigest()

    def get_cache(self, key: str, ttl: int) -> Optional[dict]:
        if key in self.cache:
            result, ts = self.cache[key]
            if time.time() - ts < ttl:
                self.stats["hits"] += 1
                return result
        return None

    def set_cache(self, key: str, result: dict):
        self.cache[key] = (result, time.time())
        # Keep cache bounded
        if len(self.cache) > 200:
            oldest = sorted(self.cache.keys(), key=lambda k: self.cache[k][1])
            for k in oldest[:50]:
                del self.cache[k]

    async def query(self, prompt: str, ttl: int = CACHE_TTL_15M) -> dict:
        """Send a prompt to agy and return parsed JSON result."""
        self.stats["requests"] += 1
        key = self.cache_key(prompt)

        # Cache hit?
        cached = self.get_cache(key, ttl)
        if cached:
            print(f"[AGY-BRIDGE] ⚡ Cache HIT (saved ~4s)")
            cached["_source"] = "cache"
            return cached

        self.stats["misses"] += 1

        async with self.lock:
            # Ensure process is alive
            if self.process is None or self.process.returncode is not None:
                await self.restart_process()

            # Send the prompt as NDJSON
            message = json.dumps({
                "event": "user",
                "message": {"role": "user", "content": prompt}
            }) + "\n"

            try:
                t0 = time.time()
                self.process.stdin.write(message.encode())
                await self.process.stdin.drain()

                # Read lines until we get the "result" event
                raw_text = ""
                while True:
                    line = await asyncio.wait_for(
                        self.process.stdout.readline(),
                        timeout=MAX_RESPONSE_WAIT
                    )
                    if not line:
                        raise RuntimeError("agy process closed stdout unexpectedly")

                    decoded = line.decode().strip()
                    if not decoded:
                        continue

                    try:
                        event = json.loads(decoded)
                    except json.JSONDecodeError:
                        continue

                    ev_type = event.get("event", "")

                    if ev_type == "step_update":
                        delta = event.get("step_update", {}).get("text_delta", "")
                        if delta:
                            raw_text += delta

                    elif ev_type == "result":
                        elapsed = time.time() - t0
                        result_obj = event.get("result", {})
                        status = result_obj.get("status", "")
                        response_text = result_obj.get("response", raw_text).strip()

                        if status != "SUCCESS":
                            err = result_obj.get("error", "unknown error")
                            raise RuntimeError(f"agy returned status={status}: {err}")

                        print(f"[AGY-BRIDGE] ✅ Response in {elapsed:.2f}s")

                        # Parse the JSON trading signal from the response
                        parsed = extract_json(response_text)
                        parsed["_elapsed_s"] = round(elapsed, 2)
                        parsed["_source"] = "agy-live"

                        self.set_cache(key, parsed)
                        return parsed

            except asyncio.TimeoutError:
                self.stats["errors"] += 1
                await self.restart_process()
                raise HTTPException(status_code=504, detail="agy response timed out — process restarted, retry")
            except Exception as e:
                self.stats["errors"] += 1
                await self.restart_process()
                raise HTTPException(status_code=500, detail=str(e))


bridge = AgyBridge()


# ── JSON extractor ──────────────────────────────────────────────
def extract_json(text: str) -> dict:
    """Robustly extract a JSON object from agy text response."""
    text = text.strip()
    # Try direct parse
    try:
        return json.loads(text)
    except Exception:
        pass
    # Strip markdown fences
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    # Find outermost {}
    s, e = text.find("{"), text.rfind("}")
    if s != -1 and e > s:
        try:
            return json.loads(text[s:e+1])
        except Exception:
            pass
    raise ValueError(f"Cannot extract JSON from: {text[:300]}")


# ── System prompt ───────────────────────────────────────────────
SYSTEM_PROMPT = """You are a Senior Quantitative Portfolio Manager at an elite Wall Street Hedge Fund.
Your mandate: capital preservation first, then asymmetric risk-to-reward profit generation.

Multi-timeframe methodology:
1. HIGHER TIMEFRAME (4H): Macro directional bias from MA, market structure, HH/LL sequences.
2. LOWER TIMEFRAME (15M): Precise execution — RSI divergence, oversold/overbought, dynamic S/R pullbacks.

RULES:
- ONE action only: "BUY", "SELL", or "HOLD"
- Choppy/high-risk → prefer "HOLD"
- BUY: SL BELOW price, TP ABOVE price, min 1:1.5 RR
- SELL: SL ABOVE price, TP BELOW price, min 1:1.5 RR
- Output ONLY valid JSON — no markdown, no extra text.

JSON schema:
{
  "decision": "BUY",
  "confidence": 78,
  "suggested_entry": 2650.50,
  "stop_loss": 2638.00,
  "take_profit": 2675.00,
  "risk_reward_ratio": "1:2.0",
  "h4_trend_analysis": "...",
  "m15_setup_analysis": "...",
  "reasoning": "..."
}"""


# ── Request / Response models ───────────────────────────────────
class AnalyzeRequest(BaseModel):
    symbol: str
    current_price: float
    atr: float = 0.0
    rsi_15m: float = 50.0
    h4_summary: str = ""
    m15_summary: str = ""
    ttl: int = CACHE_TTL_15M   # cache TTL override in seconds


class AnalyzeResponse(BaseModel):
    decision: str
    confidence: int
    suggested_entry: float
    stop_loss: float
    take_profit: float
    risk_reward_ratio: str
    h4_trend_analysis: str
    m15_setup_analysis: str
    reasoning: str
    _elapsed_s: float = 0.0
    _source: str = "agy-live"


# ── Routes ──────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    await bridge.start_process()


@app.get("/health")
async def health():
    alive = bridge.process is not None and bridge.process.returncode is None
    return {
        "status": "ok" if alive else "degraded",
        "agy_alive": alive,
        "conversation_id": bridge.conversation_id,
        "cache_size": len(bridge.cache),
        "uptime_s": round(time.time() - bridge.started_at, 1),
        "stats": bridge.stats,
    }


@app.get("/cache")
async def cache_stats():
    now = time.time()
    return {
        "total_entries": len(bridge.cache),
        "entries": [
            {"key": k[:8] + "...", "age_s": round(now - v[1], 1)}
            for k, v in bridge.cache.items()
        ],
        "stats": bridge.stats,
    }


@app.delete("/cache")
async def clear_cache():
    bridge.cache.clear()
    return {"status": "cache cleared"}


@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    prompt = f"""{SYSTEM_PROMPT}

MARKET SNAPSHOT:
ASSET: {req.symbol}
CURRENT PRICE: {req.current_price:.4f}
ATR (VOLATILITY): {req.atr:.4f}
15M RSI (14): {req.rsi_15m:.2f}

{req.h4_summary}

{req.m15_summary}

Instructions:
1. Assess 4H directional bias.
2. Evaluate 15M tactical entry.
3. Return BUY/SELL/HOLD with exact SL, TP, confidence, reasoning.

Output ONLY valid JSON. No markdown. No extra text."""

    result = await bridge.query(prompt, ttl=req.ttl)
    return JSONResponse(content=result)


@app.post("/restart")
async def restart():
    await bridge.restart_process()
    return {"status": "restarted", "conversation_id": bridge.conversation_id}


# ── Entry point ─────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "agy_bridge:app",
        host="127.0.0.1",
        port=PORT,
        log_level="info",
        loop="asyncio"
    )
