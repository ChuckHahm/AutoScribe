"""Local review UI. Binds to loopback only (run.py or docker-compose); no outbound calls.

PHI handling: uploaded photos live in memory only (small LRU) and are never
written to disk. Only synthetic samples and PHI-free metrics are persisted.
"""
import io
import json
import os
import platform
import secrets
import sys
import threading
import time
from collections import OrderedDict
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
import pytesseract
from PIL import Image

from . import capture, epic, logs, version
from .extract import compare, extract
from .schema import SLOTS
from .synth import make_sample

log = logs.log.getChild("server")

DATA = Path(os.environ.get("DATA_DIR", Path(__file__).resolve().parents[2] / "data"))  # Docker sets /data
HERE = Path(__file__).parent
DEV_UI = os.environ.get("USREPORT_DEV", "1") != "0"  # set USREPORT_DEV=0 to hide the developer interface
logs.setup(DATA)


def _build_stamp():
    """Build date shown in the UI header: BUILD_TIME env var if set (e.g. in Docker), else version.BUILD_DATE."""
    return os.environ.get("BUILD_TIME") or version.BUILD_DATE


BUILD = _build_stamp()


@asynccontextmanager
async def _lifespan(_):
    _startup()
    yield


app = FastAPI(title="US report assistant", lifespan=_lifespan)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
IMAGES: "OrderedDict[str, bytes]" = OrderedDict()  # id -> JPEG bytes, memory only
LATEST_PLAN: dict = {}
ADVANCE_KEY = os.environ.get("ADVANCE_KEY", "tab")  # key between Epic fields; verify with the reviewer (tab vs F2)
TYPING_MODE = os.environ.get("USREPORT_TYPING", "live")  # "dry": transcription logs what it would type, presses nothing
JOB: dict = dict(status="idle", step=0, total=0, message="", typed=0)  # current/last Epic transcription
ABORT = threading.Event()
_QUIET = ("/api/logs", "/api/log", "/api/system", "/api/transcribe/status", "/api/image", "/static", "/favicon")


def _startup():
    log.info("service started: python %s, data dir %s, typing mode %s, dev UI %s", sys.version.split()[0], DATA, TYPING_MODE, DEV_UI)
    try:
        log.info("tesseract %s at %s", pytesseract.get_tesseract_version(), pytesseract.pytesseract.tesseract_cmd)
    except Exception as e:
        log.error("tesseract not usable: %s", e)
    try:
        log.info("monitors: %s", capture.monitors())
    except Exception as e:
        log.warning("screen capture unavailable: %s", e)


@app.middleware("http")
async def _access_log(request, call_next):
    t0 = time.time()
    resp = await call_next(request)
    if not request.url.path.startswith(_QUIET):
        lvl = 40 if resp.status_code >= 500 else 30 if resp.status_code >= 400 else 10
        log.log(lvl, "%s %s -> %s (%d ms)", request.method, request.url.path, resp.status_code, (time.time() - t0) * 1000)
    return resp


@app.exception_handler(Exception)
async def _unhandled(request, exc):
    log.error("unhandled error on %s %s: %s", request.method, request.url.path, type(exc).__name__, exc_info=exc)
    return JSONResponse({"detail": f"internal error: {type(exc).__name__} (see Developer > Logs)"}, status_code=500)


def _remember(img):
    sid = secrets.token_hex(6)
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=92)
    IMAGES[sid] = buf.getvalue()
    while len(IMAGES) > 20:
        IMAGES.popitem(last=False)
    return sid


def _result(sid, img, truth=None):
    t0 = time.time()
    r = extract(img)
    flagged = sorted(set(r["issues"]) | set(r["low_conf"]))
    log.info("extracted %dx%d image: %d/%d fields read, flagged %s (%d ms)", img.width, img.height,
             sum(v is not None for v in r["values"].values()), len(SLOTS), ",".join(flagged) or "none", (time.time() - t0) * 1000)
    out = dict(id=sid, slots=[s.__dict__ for s in SLOTS], **r)
    if truth:
        out["match"] = compare(r["values"], truth["values"])
    return out


@app.get("/", response_class=HTMLResponse)
def index():
    """User interface: capture, review, approve."""
    return (HERE / "templates" / "user.html").read_text(encoding="utf-8").replace("__BUILD__", BUILD)


@app.get("/dev", response_class=HTMLResponse)
def dev():
    """Developer interface: synthetic data, benchmark, plan/metrics, system diagnostics."""
    if not DEV_UI:
        raise HTTPException(404)
    return (HERE / "templates" / "dev.html").read_text(encoding="utf-8").replace("__BUILD__", BUILD)


@app.get("/sim", response_class=HTMLResponse)
def sim():
    """Simulated ultrasound screen: stands in for the GE display so Capture has something to grab."""
    if not DEV_UI:
        raise HTTPException(404)
    return (HERE / "templates" / "sim.html").read_text(encoding="utf-8")


@app.get("/api/sim_image")
def sim_image(unit: str = "mm", seed: int | None = None):
    """A clean synthetic GE measurement page (what a screenshot would show), as PNG. Not stored."""
    if unit not in ("mm", "cm"):
        raise HTTPException(400, "unit must be mm or cm")
    img, _ = make_sample(seed if seed is not None else secrets.randbelow(10**6), unit, False, 0)
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "PNG")
    return Response(buf.getvalue(), media_type="image/png", headers={"Cache-Control": "no-store"})


@app.get("/api/system")
def system():
    try:
        tver = str(pytesseract.get_tesseract_version())
    except Exception:
        tver = None
    try:
        mons = capture.monitors()
    except Exception:
        mons = []
    return dict(tesseract=dict(version=tver, cmd=pytesseract.pytesseract.tesseract_cmd), monitors=mons,
                platform=platform.platform(), python=sys.version.split()[0], data_dir=str(DATA),
                build=BUILD, advance_key=ADVANCE_KEY, bind=os.environ.get("USREPORT_BIND", "127.0.0.1"), dev_ui=DEV_UI)


@app.get("/api/metrics")
def metrics():
    """Which slots reviewers had to correct, from the PHI-free metrics log."""
    f = DATA / "metrics.jsonl"
    rows = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()] if f.exists() else []
    by_slot: dict = {}
    for r in rows:
        for k in r["corrected"]:
            by_slot[k] = by_slot.get(k, 0) + 1
    return dict(reports=len(rows), reports_clean=sum(not r["corrected"] for r in rows),
                corrected_by_slot=dict(sorted(by_slot.items())))


@app.get("/api/image/{sid}")
def image(sid: str):
    if sid not in IMAGES:
        raise HTTPException(404)
    return Response(IMAGES[sid], media_type="image/jpeg")


@app.post("/api/synthetic")
def synthetic(unit: str = "mm", photo: bool = False, seed: int | None = None, severity: float = 1.0):
    if unit not in ("mm", "cm"):
        raise HTTPException(400, "unit must be mm or cm")
    seed = seed if seed is not None else secrets.randbelow(10**6)
    log.info("synthetic page: unit=%s photo=%s severity=%s seed=%s", unit, photo, severity, seed)
    img, truth = make_sample(seed, unit, photo, severity)
    return _result(_remember(img), img, truth)


@app.post("/api/extract")
async def extract_upload(file: UploadFile = File(...)):
    try:
        img = Image.open(io.BytesIO(await file.read()))
        img.load()
    except Exception:
        log.warning("upload rejected: not a readable image (%s)", file.filename and Path(file.filename).suffix)
        raise HTTPException(400, "not a readable image")
    log.info("image uploaded: %dx%d", img.width, img.height)
    return _result(_remember(img), img)


@app.post("/api/capture")
def capture_screen(monitor: int = 1, delay: float = 3.0):
    """Screenshot this machine's screen and extract. delay lets the user bring the GE page forward."""
    delay = min(max(delay, 0.0), 15.0)
    log.info("screen capture: monitor %s in %.1f s", monitor, delay)
    try:
        img = capture.grab(monitor, delay)
    except Exception as e:
        log.error("screen capture failed on monitor %s: %s", monitor, e)
        raise HTTPException(400, f"screen capture failed: {e}")
    log.info("screen captured: %dx%d", img.width, img.height)
    return _result(_remember(img), img)


@app.get("/api/benchmark")
def benchmark(n: int = 20, photo: bool = True, unit: str = "mm", severity: float = 1.0):
    """Field-level accuracy of extraction on n fresh synthetic samples."""
    n = max(1, min(n, 100))
    log.info("benchmark started: n=%d photo=%s unit=%s severity=%s", n, photo, unit, severity)
    t0 = time.time()
    hits = {s.key: 0 for s in SLOTS}
    flagged_wrong = missed_wrong = full = 0
    for seed in range(10_000, 10_000 + n):
        img, truth = make_sample(seed, unit, photo, severity)
        r = extract(img)
        ok = compare(r["values"], truth["values"])
        for k, v in ok.items():
            hits[k] += v
        full += all(ok.values())
        bad = {s.letter for s in SLOTS if not ok[s.key]}
        flagged = set(r["issues"]) | set(r["low_conf"])
        flagged_wrong += len(bad & flagged)
        missed_wrong += len(bad - flagged)  # silent errors: the dangerous ones
    total = n * len(SLOTS)
    log.info("benchmark done in %.0f s: accuracy %.1f%%, wrong&flagged %d, wrong&SILENT %d", time.time() - t0,
             100 * sum(hits.values()) / total, flagged_wrong, missed_wrong)
    return dict(n=n, photo=photo, unit=unit, severity=severity, field_accuracy=round(sum(hits.values()) / total, 4),
                reports_fully_correct=f"{full}/{n}", wrong_and_flagged=flagged_wrong,
                wrong_and_silent=missed_wrong, per_slot={k: round(v / n, 2) for k, v in hits.items()})


def _approve(values, original):
    """Record an approval: latest plan for the helper, plus PHI-free correction metrics."""
    plan = epic.build_plan(values)
    LATEST_PLAN.clear()
    LATEST_PLAN.update(plan=plan, advance_key=ADVANCE_KEY, approved_at=time.time())
    DATA.mkdir(parents=True, exist_ok=True)  # metrics: which slots needed correction, no values
    corrected = [s.letter for s in SLOTS if str(original.get(s.key)) != str(values.get(s.key))]
    with open(DATA / "metrics.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(dict(t=int(time.time()), corrected=corrected)) + "\n")
    log.info("approved: %d fields, reviewer corrected %s", sum(not p.get("skip") for p in plan), ",".join(corrected) or "none")
    return plan, corrected


@app.post("/api/approve")
def approve(body: dict):
    """Reviewer approved (possibly edited) values -> keystroke plan for the native helper."""
    plan, corrected = _approve(body.get("values", {}), body.get("original", {}))
    return dict(ok=True, corrected=corrected, plan=plan)


def _run_job(plan, countdown, dry_run):
    def progress(step, total, msg):
        JOB.update(step=step, total=total, message=msg)
        if step in (0, total) or step % 6 == 0:
            log.info("transcribe: %s", msg)
    JOB.update(status="running", step=0, total=len(plan), typed=0, message="starting", dry_run=dry_run)
    try:
        n = epic.type_plan(plan, ADVANCE_KEY, progress, ABORT, countdown=countdown, dry_run=dry_run)
        JOB.update(status="done", typed=n, message=f"{'DRY RUN: would have typed' if dry_run else 'Typed'} {n} fields into Epic. Review the report in Epic before signing.")
        log.info("transcribe finished: %d fields %s", n, "(dry run)" if dry_run else "")
    except Exception as e:
        stopped = ABORT.is_set() or "aborted" in str(e) or type(e).__name__ == "FailSafeException"
        JOB.update(status="aborted" if stopped else "error", message="Stopped. Epic may be partly filled." if stopped else str(e) or type(e).__name__)
        (log.warning if stopped else log.error)("transcribe %s: %s", "aborted" if stopped else "failed", type(e).__name__ + ": " + str(e)[:200])


@app.post("/api/transcribe")
def transcribe(body: dict):
    """Approve the reviewed values and type them into the Epic template. The reviewer then reviews in Epic."""
    if JOB["status"] == "running":
        raise HTTPException(409, "a transcription is already running")
    values, original = body.get("values", {}), body.get("original", {})
    plan, corrected = _approve(values, original)
    if all(p.get("skip") for p in plan):
        log.warning("transcribe refused: no values to type")
        raise HTTPException(400, "no values to type")
    flagged = [str(x) for x in body.get("flagged", [])]
    dry_run = bool(body.get("dry_run")) or TYPING_MODE == "dry"
    countdown = int(min(max(body.get("countdown", 5), 0), 30))
    log.info("transcribe requested: %d fields, countdown %d s, flagged fields included: %s%s", sum(not p.get("skip") for p in plan),
             countdown, ",".join(flagged) or "none", ", DRY RUN" if dry_run else "")
    ABORT.clear()
    threading.Thread(target=_run_job, args=(plan, countdown, dry_run), daemon=True).start()
    return dict(ok=True, corrected=corrected)


@app.get("/api/transcribe/status")
def transcribe_status():
    return JOB


@app.post("/api/transcribe/abort")
def transcribe_abort():
    ABORT.set()
    log.warning("transcribe: abort requested")
    return dict(ok=True)


@app.get("/api/logs")
def get_logs(n: int = 200, level: str = "DEBUG"):
    """Most recent log records, newest first."""
    return dict(logs=logs.tail(min(max(n, 1), 1000), level.upper()))


@app.post("/api/log")
def client_log(body: dict):
    """Browser-side errors and notes land in the same history (message text only; truncated)."""
    lvl = {"error": 40, "warning": 30}.get(str(body.get("level")), 20)
    logs.log.getChild("browser").log(lvl, "%s", str(body.get("msg", ""))[:300])
    return dict(ok=True)


@app.get("/epicsim", response_class=HTMLResponse)
def epicsim():
    """Stand-in for the Epic result template (fields A-W in tab order) to try transcription safely."""
    if not DEV_UI:
        raise HTTPException(404)
    return (HERE / "templates" / "epicsim.html").read_text(encoding="utf-8").replace("__SLOTS__", json.dumps([x.__dict__ for x in SLOTS]))


@app.get("/api/plan")
def plan():
    """Polled by tools/keystroke_helper.py running on the reviewer's machine."""
    if not LATEST_PLAN:
        return JSONResponse({"error": "nothing approved yet"}, status_code=404)
    return LATEST_PLAN
