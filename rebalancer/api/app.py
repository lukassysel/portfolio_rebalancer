"""FastAPI layer: thin parse → engine → JSON (doc 07 §8). Stateless: every request carries the full dataset and
policies; the bundled original workbook is read-only. Decimals travel as strings, dates as ISO strings."""

import asyncio
import os
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from .. import MODEL_VERSION
from ..adapters import WorkbookError, load_demo, read_book, write_workbook
from ..adapters.workbook import MAX_UPLOAD
from ..engine import Assumptions, Dataset, Policy, default_policies, evaluate
from ..engine.policy import EDITABLE, RANGES, default_policy
from ..engine.results import EvaluationResult, Issue
from ..serialize import to_json_bytes


def _json(obj, tp) -> Response:
    return Response(to_json_bytes(obj, tp), media_type="application/json")

MAX_REQUEST = 1024 * 1024
TIME_LIMIT = 5.0
WEB_DIST = Path(os.environ.get("WEB_DIST", Path(__file__).resolve().parents[2] / "web" / "dist"))

app = FastAPI(title="Rebalancování portfolií", version=MODEL_VERSION,
              description="Rozhodovací podpora pro rebalancování klientských portfolií (návrh, nikoli pokyn k obchodu).")


class Snapshot(BaseModel):
    """Dataset + policies + result: what the UI holds in memory (no server state)."""

    model_version: str
    dataset: Dataset
    policies: dict[str, Policy]
    issues: list[Issue]
    result: EvaluationResult
    demo: bool


class EvaluateRequest(BaseModel):
    model_version: str = MODEL_VERSION
    dataset: Dataset
    policies: dict[str, Policy]
    assumptions: Assumptions | None = None
    issues: list[Issue] = Field(default_factory=list)


class ImportError_(BaseModel):
    detail: str
    issues: list[Issue]


class Meta(BaseModel):
    model_version: str
    default_policy: Policy  # defaults with empty targets — the starting point for a new client
    editable: list[str]  # parameters edited per client; the rest keep the defaults
    ranges: dict[str, list[str]]
    assumptions: Assumptions


class BodyLimit:
    """Counts the bytes actually received (also for chunked bodies) and answers 413 above the limit."""

    def __init__(self, app, limit: int, paths: tuple[str, ...]):
        self.app, self.limit, self.paths = app, limit, paths

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] not in self.paths:
            return await self.app(scope, receive, send)
        declared = dict(scope.get("headers") or []).get(b"content-length")
        if declared and declared.isdigit() and int(declared) > self.limit:
            response = JSONResponse({"detail": "Požadavek je větší než 1 MiB."}, status_code=413)
            return await response(scope, receive, send)
        chunks, size, more = [], 0, True
        while more:
            msg = await receive()
            if msg["type"] != "http.request":
                return
            chunks.append(msg.get("body", b""))
            size += len(chunks[-1])
            more = msg.get("more_body", False)
            if size > self.limit:
                response = JSONResponse({"detail": "Požadavek je větší než 1 MiB."}, status_code=413)
                return await response(scope, receive, send)
        body, sent = b"".join(chunks), False

        async def replay():
            nonlocal sent
            if sent:
                return await receive()
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        await self.app(scope, replay, send)


app.add_middleware(BodyLimit, limit=MAX_REQUEST, paths=("/api/evaluate", "/api/export"))


async def _bounded(fn, *args):
    """Run CPU work in a worker thread with the 5 s evaluation limit (doc 08 §12)."""
    try:
        return await asyncio.wait_for(run_in_threadpool(fn, *args), timeout=TIME_LIMIT)
    except asyncio.TimeoutError:
        raise HTTPException(503, "Výpočet překročil časový limit 5 s.")


def _snapshot(ds: Dataset, issues: list[Issue], demo: bool, policies: dict[str, Policy] | None = None) -> Snapshot:
    policies = policies or default_policies(ds)
    return Snapshot(model_version=MODEL_VERSION, dataset=ds, policies=policies, issues=issues,
                    result=evaluate(ds, policies, issues=issues), demo=demo)


@app.get("/api/health")
def health() -> dict:
    ds, _ = load_demo()  # proves the bundled data is present and readable
    return {"status": "ok", "model_version": MODEL_VERSION, "clients": len(ds.clients),
            "web": (WEB_DIST / "index.html").exists()}


@app.get("/api/meta", response_model=Meta)
def meta() -> Meta:
    return Meta(model_version=MODEL_VERSION, default_policy=default_policy({}),
                editable=EDITABLE,
                ranges={k: [str(lo), str(hi)] for k, (lo, hi) in RANGES.items()},
                assumptions=Assumptions())


@app.get("/api/demo", response_model=Snapshot)
def demo() -> Snapshot:
    ds, issues = load_demo()
    return _json(_snapshot(ds, issues, True), Snapshot)


@app.post("/api/evaluate", response_model=EvaluationResult)
async def evaluate_endpoint(req: EvaluateRequest) -> EvaluationResult:
    if req.model_version != MODEL_VERSION:
        raise HTTPException(409, f"Verze modelu se liší (server {MODEL_VERSION}, klient {req.model_version}). "
                                 "Obnovte stránku.")
    result = await _bounded(evaluate, req.dataset, req.policies, req.assumptions, req.issues)
    return _json(result, EvaluationResult)


@app.post("/api/import", response_model=Snapshot, responses={422: {"model": ImportError_}})
async def import_workbook(file: UploadFile = File(...)):
    data = await file.read(MAX_UPLOAD + 1)
    try:
        ds, issues, policies = await _bounded(read_book, data, file.filename or "upload.xlsx")
    except WorkbookError as e:
        return JSONResponse(ImportError_(detail="Soubor nelze použít.", issues=e.issues).model_dump(mode="json"),
                            status_code=422)
    return _json(await _bounded(_snapshot, ds, issues, False, policies), Snapshot)


class ExportRequest(BaseModel):
    dataset: Dataset
    policies: dict[str, Policy]


@app.post("/api/export", response_class=Response,
          responses={200: {"content": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}}}})
def export_workbook(req: ExportRequest) -> Response:
    """The current client book (data + strategies) as an .xlsx in the import format."""
    d = req.dataset.valuation_date
    return Response(write_workbook(req.dataset, req.policies),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="klienti-{d.isoformat()}.xlsx"'})


@app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "DELETE"], include_in_schema=False)
def api_not_found(rest: str):
    return JSONResponse({"detail": "Neznámý API endpoint."}, status_code=404)


if WEB_DIST.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = WEB_DIST / path
        if path and f.is_file() and WEB_DIST in f.resolve().parents:
            return FileResponse(f)
        return FileResponse(WEB_DIST / "index.html")
