from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.database import get_db, LOCAL_WORKSPACE_ID
from app.models import EvaluationItem, EvaluationRun
from app.schemas import (
    EvaluationItemCreate,
    EvaluationItemOut,
    EvaluationItemsImport,
    EvaluationRunRequest,
    EvaluationRunSummary,
    EvaluationRunOut,
)
from app.routers.settings_router import _get_or_create
from app.routers.chat import build_context, SYSTEM_PROMPT_TEMPLATE, NO_CONTEXT_SYSTEM_PROMPT, compute_confidence
from app.rag.llm_client import LLMClient
from app.rag.retrieval import retrieve
from app.rag import evaluation as eval_metrics
from app.config import settings as app_settings

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


# ── Test-set items (ground truth) ─────────────────────────────────────
@router.get("/items", response_model=list[EvaluationItemOut])
async def list_items(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(EvaluationItem)
        .where(EvaluationItem.owner_id == LOCAL_WORKSPACE_ID)
        .order_by(EvaluationItem.created_at.desc())
    )
    return result.scalars().all()


@router.post("/items", response_model=EvaluationItemOut)
async def create_item(
    payload: EvaluationItemCreate,
    db: AsyncSession = Depends(get_db),
):
    item = EvaluationItem(
        owner_id=LOCAL_WORKSPACE_ID,
        query=payload.query,
        reference_answer=payload.reference_answer,
        relevant_chunk_ids=payload.relevant_chunk_ids,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.post("/items/import", response_model=list[EvaluationItemOut])
async def import_items(
    payload: EvaluationItemsImport,
    db: AsyncSession = Depends(get_db),
):
    if not payload.items:
        raise HTTPException(400, "لیست خالی است.")
    records = [
        EvaluationItem(
            owner_id=LOCAL_WORKSPACE_ID,
            query=it.query,
            reference_answer=it.reference_answer,
            relevant_chunk_ids=it.relevant_chunk_ids,
        )
        for it in payload.items
    ]
    db.add_all(records)
    await db.commit()
    for r in records:
        await db.refresh(r)
    return records


@router.delete("/items/{item_id}")
async def delete_item(
    item_id: str,
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        delete(EvaluationItem).where(
            EvaluationItem.owner_id == LOCAL_WORKSPACE_ID, EvaluationItem.id == item_id
        )
    )
    await db.commit()
    return {"message": "حذف شد."}


# ── Runs ────────────────────────────────────────────────────────────────
@router.get("/runs", response_model=list[EvaluationRunSummary])
async def list_runs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(EvaluationRun)
        .where(EvaluationRun.owner_id == LOCAL_WORKSPACE_ID)
        .order_by(EvaluationRun.created_at.desc())
    )
    return result.scalars().all()


@router.get("/runs/{run_id}", response_model=EvaluationRunOut)
async def get_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(EvaluationRun).where(
            EvaluationRun.owner_id == LOCAL_WORKSPACE_ID, EvaluationRun.id == run_id
        )
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(404, "اجرای ارزیابی یافت نشد.")
    return run


@router.delete("/runs/{run_id}")
async def delete_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        delete(EvaluationRun).where(
            EvaluationRun.owner_id == LOCAL_WORKSPACE_ID, EvaluationRun.id == run_id
        )
    )
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(404, "اجرای ارزیابی یافت نشد.")
    return {"message": "حذف شد."}


@router.delete("/runs")
async def delete_all_runs(
    db: AsyncSession = Depends(get_db),
):
    await db.execute(delete(EvaluationRun).where(EvaluationRun.owner_id == LOCAL_WORKSPACE_ID))
    await db.commit()
    return {"message": "همهٔ اجراها حذف شد."}


@router.post("/run", response_model=EvaluationRunOut)
async def run_evaluation(
    payload: EvaluationRunRequest,
    db: AsyncSession = Depends(get_db),
):
    items_result = await db.execute(
        select(EvaluationItem).where(EvaluationItem.owner_id == LOCAL_WORKSPACE_ID)
    )
    items = items_result.scalars().all()
    if not items:
        raise HTTPException(400, "ابتدا حداقل یک مورد آزمایشی (سوال + منابع درست) اضافه کنید.")

    user_settings = await _get_or_create(db)
    llm = LLMClient(
        base_url=user_settings.llm_base_url or app_settings.default_llm_base_url,
        api_key=user_settings.llm_api_key or app_settings.default_llm_api_key,
        model=user_settings.llm_model,
    )

    k_values = sorted({k for k in payload.k_values if k > 0}) or [1, 3, 5, 10]

    agg: dict[str, list[float]] = {f"precision@{k}": [] for k in k_values}
    agg.update({f"recall@{k}": [] for k in k_values})
    agg.update({f"ndcg@{k}": [] for k in k_values})
    agg["mrr"] = []
    if payload.evaluate_generation:
        agg["faithfulness"] = []
        agg["answer_relevance"] = []
        agg["context_precision"] = []

    details = []
    for item in items:
        retrieval = await retrieve(item.query, LOCAL_WORKSPACE_ID, db, user_settings, llm)
        retrieved_ids = [r["id"] for r in retrieval["results"]]

        entry: dict = {"item_id": item.id, "query": item.query, "retrieved_ids": retrieved_ids}
        entry["confidence"] = compute_confidence(retrieval)

        relevant_ids = set(item.relevant_chunk_ids or [])
        if relevant_ids:
            r_metrics = eval_metrics.retrieval_metrics(retrieved_ids, relevant_ids, k_values)
            entry["retrieval"] = r_metrics
            for k in k_values:
                agg[f"precision@{k}"].append(r_metrics[f"precision@{k}"])
                agg[f"recall@{k}"].append(r_metrics[f"recall@{k}"])
                agg[f"ndcg@{k}"].append(r_metrics[f"ndcg@{k}"])
            agg["mrr"].append(r_metrics["mrr"])
        else:
            entry["retrieval"] = None  # no ground truth labeled for this item

        if payload.evaluate_generation:
            if retrieval["found"]:
                context = build_context(retrieval["results"])
                system_msg = {
                    "role": "system",
                    "content": SYSTEM_PROMPT_TEMPLATE.format(context=context),
                }
            else:
                system_msg = {"role": "system", "content": NO_CONTEXT_SYSTEM_PROMPT}

            try:
                answer = await llm.chat_completion(
                    [system_msg, {"role": "user", "content": item.query}], temperature=0
                )
            except Exception:
                answer = ""

            context_texts = [r["content"] for r in retrieval["results"]]
            gen_metrics = await eval_metrics.evaluate_generation(
                item.query, answer, context_texts, llm
            )
            entry["answer"] = answer
            entry["generation"] = gen_metrics
            if gen_metrics["faithfulness"] is not None:
                agg["faithfulness"].append(gen_metrics["faithfulness"])
            if gen_metrics["answer_relevance"] is not None:
                agg["answer_relevance"].append(gen_metrics["answer_relevance"])
            if gen_metrics.get("context_precision") is not None:
                agg["context_precision"].append(gen_metrics["context_precision"])

        details.append(entry)

    summary = {key: (sum(vals) / len(vals) if vals else None) for key, vals in agg.items()}

    run = EvaluationRun(
        owner_id=LOCAL_WORKSPACE_ID, item_count=len(items), summary=summary, details=details
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run
