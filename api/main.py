from __future__ import annotations

import os
import re

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.block import router as block_router
from api.routes.events import router as events_router
from api.routes.search import router as search_router


def _cors_config() -> tuple[list[str], str | None]:
    raw_origins = os.getenv("ALLOWED_ORIGINS", "")
    exact_origins: list[str] = []
    regexes: list[str] = []

    for origin in [item.strip() for item in raw_origins.split(",") if item.strip()]:
        if origin == "*":
            return ["*"], None
        if "*" in origin:
            regexes.append("^" + re.escape(origin).replace("\\*", ".*") + "$")
        else:
            exact_origins.append(origin)

    return exact_origins, "|".join(regexes) if regexes else None


allowed_origins, allowed_origin_regex = _cors_config()

app = FastAPI(title="NYC Block Pulse API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=allowed_origin_regex,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(events_router)
app.include_router(block_router)
app.include_router(search_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
