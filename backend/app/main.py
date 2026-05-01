from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import export, kpis, regions, rivals

app = FastAPI(title="OTA Worldmap API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(regions.router)
app.include_router(rivals.router)
app.include_router(kpis.router)
app.include_router(export.router)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
