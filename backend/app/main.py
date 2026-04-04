import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.core.database import init_db
    await init_db()
    from app.tasks.queue import run_queue_worker
    from app.services.event_poller import run_k8s_event_watcher_streaming

    queue_task = asyncio.create_task(run_queue_worker())
    poller_task = asyncio.create_task(run_k8s_event_watcher_streaming())
    yield
    poller_task.cancel()
    queue_task.cancel()
    for t in (poller_task, queue_task):
        try:
            await t
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="AutoSRE API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health():
    from app.services.event_poller import is_watcher_running
    return {
        "status": "ok",
        "k8s_watcher_running": is_watcher_running(),
    }


@app.get("/metrics")
async def metrics():
    from fastapi.responses import PlainTextResponse
    from app.services.event_poller import get_poller_metrics
    m = get_poller_metrics()
    lines = [
        f'autosre_events_received_total{{source="k8s_events"}} {m["events_received"]}',
        f'autosre_events_emitted_total{{source="k8s_events"}} {m["events_emitted"]}',
        f'autosre_spacetimedb_write_failures_total {m["spacetimedb_write_failures"]}',
        f'autosre_duplicates_dropped_total {m["duplicates_dropped"]}',
    ]
    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")

