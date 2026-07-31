from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.core.exceptions import EvaluationError
from app.evaluation.dataset import load_dataset
from app.evaluation.runner import run_evaluation
from app.models.database import EvaluationResultRecord, EvaluationRunRecord
from app.models.schemas import (
    EvaluationResultRow, EvaluationResultsResponse, EvaluationRunRequest, EvaluationRunResponse,
    EvaluationRunSummarySchema,
)
from app.services.pipeline import RetrievalMode

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.post("/run", response_model=EvaluationRunResponse)
async def run_evaluation_endpoint(request: EvaluationRunRequest, db: Session = Depends(get_db)):
    cases = load_dataset()
    if not cases:
        raise EvaluationError("No evaluation cases found. Populate data/evaluation/golden_dataset.json first.")

    modes = [RetrievalMode(m.value) for m in request.modes] if request.modes else None

    try:
        summaries = run_evaluation(db, modes=modes)
    except Exception as exc:
        raise EvaluationError(f"Evaluation run failed: {exc}") from exc

    return EvaluationRunResponse(
        dataset_case_count=len(cases),
        runs=[
            EvaluationRunSummarySchema(run_id=s.run_id, retrieval_mode=s.retrieval_mode, case_count=s.case_count, metrics=s.metrics)
            for s in summaries
        ],
    )


@router.get("/results", response_model=EvaluationResultsResponse)
async def list_evaluation_results(db: Session = Depends(get_db)):
    rows = (
        db.query(EvaluationResultRecord, EvaluationRunRecord)
        .join(EvaluationRunRecord, EvaluationResultRecord.run_id == EvaluationRunRecord.run_id)
        .order_by(EvaluationRunRecord.created_at.desc())
        .all()
    )
    return EvaluationResultsResponse(
        results=[
            EvaluationResultRow(
                run_id=run.run_id, retrieval_mode=run.retrieval_mode, created_at=run.created_at,
                metric_name=result.metric_name, metric_value=result.metric_value,
            )
            for result, run in rows
        ]
    )


@router.get("/results/{run_id}", response_model=EvaluationResultsResponse)
async def get_evaluation_run_results(run_id: str, db: Session = Depends(get_db)):
    rows = (
        db.query(EvaluationResultRecord, EvaluationRunRecord)
        .join(EvaluationRunRecord, EvaluationResultRecord.run_id == EvaluationRunRecord.run_id)
        .filter(EvaluationRunRecord.run_id == run_id)
        .all()
    )
    return EvaluationResultsResponse(
        results=[
            EvaluationResultRow(
                run_id=run.run_id, retrieval_mode=run.retrieval_mode, created_at=run.created_at,
                metric_name=result.metric_name, metric_value=result.metric_value,
            )
            for result, run in rows
        ]
    )
