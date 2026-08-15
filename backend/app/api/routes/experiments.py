"""Immutable archival experiment API; distinct from mutable training experiments."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse

from app.core.database import LocalSessionLocal
from app.models.research_outputs import ExperimentRun
from app.services.experiment_run_service import ExperimentRunRequest, ExperimentRunService, ResearchInterrogationRequest, ResearcherAssessmentInput, render_run_report, serialize_run

router = APIRouter()
service = ExperimentRunService()


def serialize_interrogation(run: ExperimentRun) -> dict:
    payload = serialize_run(run)
    response = payload["structured_response"] or {}
    contexts = payload["authority_context"].get("contexts", [])

    def authority_evidence(item: dict) -> dict:
        fields = item["fields"]
        if item["authority_type"] == "ddr_projects":
            return {
                "authority_type": "ddr_projects",
                "authority_id": item["authority_id"],
                "source": item["source"],
                "job_number": fields.get("job_number"),
                "title": fields.get("title"),
                "funder_name": fields.get("funder_name"),
                "duration_text": fields.get("duration_text"),
                "project_lead_name": fields.get("project_lead_name"),
                "start_year": fields.get("start_year"),
                "end_year": fields.get("end_year"),
                "filter": fields.get("authority_filter"),
            }
        if item["authority_type"] != "agent_employment":
            return {
                "authority_type": item["authority_type"],
                "authority_id": item["authority_id"],
                "source": item["source"],
                "label": fields.get("label"),
                "code": fields.get("code"),
                "description": fields.get("description"),
                "metadata": {key: value for key, value in fields.items() if key not in {"label", "code", "description", "epistemic_type", "authority_classification"}},
                "epistemic_type": fields.get("epistemic_type"),
                "authority_classification": fields.get("authority_classification"),
            }
        return {
            "authority_type": item["authority_type"],
            "assertion": fields.get("name"),
            "source": item["source"],
            "authority_id": item["authority_id"],
            "role": fields.get("job_title_label"),
            "tenure": {"start_date": fields.get("start_date"), "end_date": fields.get("end_date")},
        }

    return {
        **payload,
        "answer": response.get("answer", "The supplied authority and retrieved corpus do not establish this."),
        "authority_evidence": [authority_evidence(item) for item in contexts],
        "documentary_evidence": response.get("evidence", []),
        "inferences": response.get("inferences", []),
        "contradictions": response.get("contradictions", []),
        "missingness": response.get("missingness", []),
        "follow_up_queries": response.get("follow_up_queries", []),
        "provenance_validation": payload["provenance_validation"],
    }


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


@router.post("/interrogate", status_code=201)
async def interrogate_research_corpus(request: ResearchInterrogationRequest):
    db = LocalSessionLocal()
    try:
        return serialize_interrogation(await service.run_research_interrogation(db, request))
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
