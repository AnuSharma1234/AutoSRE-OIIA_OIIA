import redis.asyncio as redis
import json
import uuid
from datetime import datetime
from app.config import settings

redis_client = redis.from_url(settings.redis_url, decode_responses=True)

TASK_QUEUE_KEY = "autosre:tasks"
TASK_TTL_SECONDS = 3600  # 1 hour

async def enqueue_task(incident_id: str, task_type: str = "analyze") -> str:
    """Push a task to the Redis queue. Returns task_id."""
    task_id = str(uuid.uuid4())
    task_data = {
        "task_id": task_id,
        "incident_id": incident_id,
        "task_type": task_type,
        "status": "pending",
        "created_at": datetime.utcnow().isoformat(),
    }
    await redis_client.lpush(TASK_QUEUE_KEY, json.dumps(task_data))
    # Also store task data for status lookup
    await redis_client.setex(
        f"autosre:task:{task_id}",
        TASK_TTL_SECONDS,
        json.dumps(task_data)
    )
    return task_id

async def dequeue_task(timeout: int = 5) -> dict | None:
    """Blocking pop from queue. Returns task dict or None."""
    result = await redis_client.brpop(TASK_QUEUE_KEY, timeout=timeout)
    if result:
        _, task_json = result
        return json.loads(task_json)
    return None

async def get_task_status(task_id: str) -> dict | None:
    """Get task status from Redis. Returns dict or None."""
    data = await redis_client.get(f"autosre:task:{task_id}")
    if data:
        return json.loads(data)
    return None

async def update_task_status(task_id: str, status: str, result: dict | None = None):
    """Update task status in Redis."""
    key = f"autosre:task:{task_id}"
    data = await redis_client.get(key)
    if data:
        task = json.loads(data)
        task["status"] = status
        if result:
            task["result"] = result
        task["updated_at"] = datetime.utcnow().isoformat()
        await redis_client.setex(key, TASK_TTL_SECONDS, json.dumps(task))

async def get_redis() -> redis.Redis:
    """Dependency for FastAPI."""
    return redis_client
