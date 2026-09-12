from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.optimization import router as optimization_router
from api.routes.mission import router as mission_router


app = FastAPI(
    title="Antarctic Maritime Resupply Navigation Simulator",
    description="Decision-support API for Antarctic maritime resupply optimization.",
    version="0.1.0",
)


# Allow the Vite React frontend to communicate with the FastAPI backend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
        "http://localhost:5176",
        "http://127.0.0.1:5176",
        "http://localhost:5177",
        "http://127.0.0.1:5177",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(optimization_router)
app.include_router(mission_router)


@app.get("/")
def root():
    return {
        "name": "Antarctic Maritime Resupply Navigation Simulator",
        "status": "running",
        "version": "0.1.0",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
    }