#!/usr/bin/env python3
"""Execute the one authorized CI3-v2 / v1.4 formal run without JSON repair."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings
from app.core.database import LocalSessionLocal
from app.models.research_outputs import ExperimentRun, TurinRetrievalPlan
from app.services.experiment_run_service import ExperimentRunRequest, ExperimentRunService, serialize_run
from app.services.granite_service import get_granite_service
from app.services.retrieval_protocol import RetrievalPlan
from app.services.retrieval_validation_service import RetrievalValidationRequest
from app.services.turin_experiment_service import CONTEXT_ASSEMBLY_PROTOCOL_VERSION, RESPONSE_SCHEMA_VERSION, structured_output_max_tokens
from app.services.turin_question_register import TURIN_QUESTION_REGISTER


PLAN_ID = 'CI3-v2'
QUESTION_ID = 'CI3'
CORPUS_VERSION = 'corpus_f40d78dbce52'
PROTOCOL = 'turin-retrieval-protocol-v1.4'
AUTHORIZATION_ID = 'turin-q07-ci3-v2-v14-primary-authorization'
EXPECTED_PARAMETERS = {'max_tokens': 1500, 'temperature': 0.0, 'top_p': 1.0, 'do_sample': False, 'granite_timeout_seconds': 1200}


def load_preflight(db) -> RetrievalPlan:
    if settings.ENVIRONMENT.lower() != 'production':
        raise RuntimeError('Q07 formal execution is production-only.')
    stored = db.query(TurinRetrievalPlan).filter(TurinRetrievalPlan.plan_id == PLAN_ID).one_or_none()
    if stored is None:
        raise RuntimeError('CI3-v2 is not registered.')
    plan = RetrievalPlan.model_validate(stored.plan_json)
    case, question = TURIN_QUESTION_REGISTER[QUESTION_ID]
    if any((
        plan.question_id != QUESTION_ID, plan.plan_version != '2.0', plan.top_k != 6,
        plan.run_classification != 'primary', plan.supersedes_plan_id != 'CI3-v1',
        stored.researcher_approval_state != 'approved', plan.researcher_approval_state != 'approved',
        case != 'contested_interpretation', not question,
        structured_output_max_tokens(PROTOCOL) != 1500,
        CONTEXT_ASSEMBLY_PROTOCOL_VERSION != 'turin-retrieval-protocol-v1.1',
        RESPONSE_SCHEMA_VERSION != 'turin-archival-analysis-response-v1',
    )):
        raise RuntimeError('CI3-v2/v1.4 preflight identity does not match the governed configuration.')
    plan.require_formal_approval()
    authorization = db.execute(text('SELECT plan_id, plan_version, execution_protocol_version, corpus_version, retrieval_scope, run_classification, authorization_category, model_name, model_parameters_json FROM turin_formal_protocol_authorizations WHERE authorization_id=:id'), {'id': AUTHORIZATION_ID}).mappings().one_or_none()
    if authorization is None or dict(authorization['model_parameters_json']) != EXPECTED_PARAMETERS or any((
        authorization['plan_id'] != PLAN_ID, authorization['plan_version'] != '2.0',
        authorization['execution_protocol_version'] != PROTOCOL, authorization['corpus_version'] != CORPUS_VERSION,
        authorization['retrieval_scope'] != 'corpus_wide', authorization['run_classification'] != 'primary',
        authorization['authorization_category'] != 'q07_ci3_v2_v14_primary_authorization',
        authorization['model_name'] != 'granite3.1-dense:2b-instruct-q4_K_M',
    )):
        raise RuntimeError('Q07 requires its exact unmodified v2/v1.4 authorization.')
    for label, sql, expected in (
        ('authorization consumption', 'SELECT count(*) FROM experiment_runs WHERE formal_authorization_id=:id', 0),
        ('CI3-v2 formal runs', "SELECT count(*) FROM experiment_runs WHERE question_id='CI3' AND retrieval_plan_id='CI3-v2' AND fixture_only=false", 0),
        ('CI3 evaluable results', "SELECT count(*) FROM turin_formal_run_evaluability_classifications WHERE question_id='CI3'", 0),
        ('Q08-Q12 runs', "SELECT count(*) FROM experiment_runs WHERE question_id IN ('CI4','SM1','SM2','SM3','SM4')", 0),
    ):
        if db.execute(text(sql), {'id': AUTHORIZATION_ID}).scalar_one() != expected:
            raise RuntimeError(f'Q07 execution blocked: {label} is no longer {expected}.')
    return plan


async def verify_write_ahead_shell(run: ExperimentRun) -> None:
    db = LocalSessionLocal()
    try:
        shell = db.query(ExperimentRun).filter(ExperimentRun.run_id == run.run_id).one_or_none()
        if shell is None or any((
            shell.status != 'running', shell.formal_authorization_id != AUTHORIZATION_ID,
            shell.question_id != QUESTION_ID, shell.retrieval_plan_id != PLAN_ID,
            shell.retrieval_plan_version != '2.0', shell.retrieval_protocol_version != PROTOCOL,
            shell.corpus_version != CORPUS_VERSION, shell.retrieval_scope != 'corpus_wide',
            shell.retrieval_run_classification != 'primary',
            shell.model_name != 'granite3.1-dense:2b-instruct-q4_K_M',
            shell.model_parameters_json != EXPECTED_PARAMETERS,
        )):
            raise RuntimeError('Q07 write-ahead shell is not durably present with the governed identity.')
        print(json.dumps({'write_ahead_shell': {'run_id': shell.run_id, 'status': shell.status, 'authorization_id': shell.formal_authorization_id, 'question_id': shell.question_id, 'plan_id': shell.retrieval_plan_id, 'plan_version': shell.retrieval_plan_version, 'protocol': shell.retrieval_protocol_version, 'corpus': shell.corpus_version, 'classification': shell.retrieval_run_classification, 'model': shell.model_name, 'parameters': shell.model_parameters_json, 'started_at': shell.created_at.isoformat()}}, default=str), flush=True)
    finally:
        db.close()


async def main() -> None:
    db = LocalSessionLocal()
    try:
        plan = load_preflight(db)
        case, question = TURIN_QUESTION_REGISTER[QUESTION_ID]
        granite = get_granite_service()
        if not granite.get_load_status().get('model_ready') and not granite.load_model():
            raise RuntimeError(f"Granite runtime could not load: {granite.get_load_status().get('last_error')}")
        if granite.timeout_seconds != 1200 or granite.model_name != 'granite3.1-dense:2b-instruct-q4_K_M' or granite.get_load_status().get('model_status') != 'ready':
            raise RuntimeError('Granite health/configuration preflight failed.')
        run = await ExperimentRunService(granite_service=granite).run_archival_experiment(
            db,
            ExperimentRunRequest(
                research_case=case, research_question=question, question_id=QUESTION_ID,
                retrieval=RetrievalValidationRequest(query=question, top_k=plan.top_k, corpus_version=CORPUS_VERSION),
                context_budget=6000, retrieval_plan=plan, execution_protocol_version=PROTOCOL,
                formal_authorization_id=AUTHORIZATION_ID, fixture_only=False, allow_repair=False,
            ),
            on_write_ahead_shell=verify_write_ahead_shell,
        )
        print(json.dumps(serialize_run(run), indent=2, default=str))
    finally:
        db.close()


if __name__ == '__main__':
    asyncio.run(main())