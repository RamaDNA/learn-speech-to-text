from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.agent.ollama_client import ollama_client
from app.config import settings
from app.db import Base, engine
from app.routers import agent, items, locations, stock, transactions
from seed_data import seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    seed(engine)
    # pull model di background biar startup tidak blocking
    import threading
    threading.Thread(target=ollama_client._ensure_model, daemon=True).start()
    print(f"[api] READY — ollama={settings.ollama_base_url} model={settings.ollama_model}")
    yield


app = FastAPI(title="Warehouse Voice Assistant API", version="0.1.0", lifespan=lifespan)

app.include_router(items.router)
app.include_router(locations.router)
app.include_router(stock.router)
app.include_router(transactions.router)
app.include_router(agent.router)


@app.get("/health")
def health():
    return {"status": "ok"}