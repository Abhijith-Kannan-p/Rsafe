"""Serve the built frontend (frontend/dist) from the API, for a single-service deployment.

In development Vite serves the frontend and proxies /api; in a deployed container the API
serves both, so the app has one URL and its session cookie is same-origin.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse


def mount_frontend(app: FastAPI, dist: Path) -> bool:
    """Add a catch-all route after the API routes: real files from dist, otherwise index.html so
    deep links like /app/dashboard work. Returns False (and adds nothing) if dist is missing."""
    index = dist / "index.html"
    if not index.is_file():
        return False
    root = dist.resolve()

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise HTTPException(404, "Not found.")  # unknown API paths stay JSON 404s
        if path:
            f = (root / path).resolve()
            if f.is_file() and root in f.parents:  # no escaping the dist folder
                # hashed build assets never change; everything else is revalidated
                cache = "public, max-age=31536000, immutable" if path.startswith("assets/") else "no-cache"
                return FileResponse(f, headers={"Cache-Control": cache})
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    return True
