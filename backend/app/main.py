from fastapi import FastAPI


app = FastAPI(
    title="AutoSRE API",
    version="1.0.0",
)


@app.get("/health")
async def health():
    return {"status": "ok"}
