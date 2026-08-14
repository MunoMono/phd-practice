"""Immutable archival experiment API; distinct from mutable training experiments."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse

from app.core.database import LocalSessionLocal
from app.models.research_outputs import ExperimentRun
from app.services.experiment_run_service import ExperimentRunRequest, ExperimentRunService, ResearcherAssessmentInput, render_run_report, serialize_run

router = APIRouter()
service = ExperimentRunService()


def _get_run(db, run_id: str) -> ExperimentRun:
    run = db.query(ExperimentRun).filter(ExperimentRun.run_id == run_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Experiment run not found")
    return run


@router.post("", status_code=201)
@router.post("/", status_code=201)
async def create_experiment_run(request: ExperimentRunRequest):
    db = LocalSessionLocal()
    try:
        return serialize_run(await service.run_archival_experiment(db, request))
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        db.close()


@router.get("")
@router.get("/")
async def list_experiment_runs():
    db = LocalSessionLocal()
    try:
        runs = db.query(ExperimentRun).order_by(ExperimentRun.created_at.desc()).limit(50).all()
        return {"count": len(runs), "experiment_runs": [serialize_run(run, include_evidence=False) for run in runs]}
    finally:
        db.close()


@router.get("/{run_id}/export")
async def export_experiment_run(run_id: str):
    db = LocalSessionLocal()
    try:
        return JSONResponse(content=serialize_run(_get_run(db, run_id)))
    finally:
        db.close()


@router.get("/{run_id}/report")
async def report_experiment_run(run_id: str):
    db = LocalSessionLocal()
    try:
        return PlainTextResponse(render_run_report(_get_run(db, run_id)), media_type="text/markdown")
    finally:
        db.close()


@router.post("/{run_id}/assessment")
async def save_researcher_assessment(run_id: str, request: ResearcherAssessmentInput):
    db = LocalSessionLocal()
    try:
        run = _get_run(db, run_id)
        service.save_assessment(db, run, request)
        return {"run_id": run_id, "assessment": serialize_run(run, include_evidence=False)["assessment"]}
    finally:
        db.close()


@router.get("/{run_id}")
async def get_experiment_run(run_id: str):
    db = LocalSessionLocal()
    try:
        return serialize_run(_get_run(db, run_id))
    finally:
        db.close()
