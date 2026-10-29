"""Asset-type aware data-status + refresh helpers for the API."""

from __future__ import annotations

from datetime import date
from typing import Any

from backend.api.deps import latest_market_date, latest_pipeline
from backend.config import get_settings
from backend.db import get_supabase
from backend.indicators.calculate_daily import calculate_for_all
from backend.ingestion.helpers import finish_pipeline_run, start_pipeline_run
from backend.ingestion.sync_crypto_data import run_sync_crypto
from backend.ingestion.sync_market_data import run_sync


def _requests_used_today(run_types: list[str]) -> int:
    client = get_supabase()
    today_iso = date.today().isoformat()
    rows = (
        client.table("pipeline_runs")
        .select("api_requests_used,started_at,run_type")
        .gte("started_at", f"{today_iso}T00:00:00")
        .in_("run_type", run_types)
        .execute()
    ).data or []
    return sum(int(r.get("api_requests_used") or 0) for r in rows)


def data_status_for(asset_type: str) -> dict[str, Any]:
    settings = get_settings()
    asset = asset_type.upper()
    client = get_supabase()

    instruments = (
        client.table("market_instruments")
        .select("id", count="exact")
        .eq("active", True)
        .eq("asset_type", asset)
        .execute()
    )
    ids = [r["id"] for r in (instruments.data or [])]
    # Count instruments that have at least one daily candle. Do not SELECT all
    # price rows — PostgREST caps pages (~1000) and under-counts large histories.
    with_data = 0
    for instrument_id in ids:
        sample = (
            client.table("market_prices_daily")
            .select("instrument_id")
            .eq("instrument_id", instrument_id)
            .limit(1)
            .execute()
        ).data or []
        if sample:
            with_data += 1

    if asset == "CRYPTO":
        ingestion = latest_pipeline("ingestion_crypto")
        calculation = latest_pipeline("calculation_crypto")
        refresh = latest_pipeline("refresh_crypto")
        used = _requests_used_today(
            ["ingestion_crypto", "refresh_crypto", "calculation_crypto"]
        )
        limit = settings.max_freecryptoapi_requests_per_run
        provider = "FreeCryptoAPI"
        max_per_run = settings.max_freecryptoapi_requests_per_run
    else:
        ingestion = latest_pipeline("ingestion")
        calculation = latest_pipeline("calculation")
        refresh = latest_pipeline("refresh")
        used = _requests_used_today(["ingestion", "refresh", "calculation"])
        limit = 20
        provider = "EODHD"
        max_per_run = settings.max_eodhd_requests_per_run

    last_candle = latest_market_date(asset)
    last_refresh = (refresh or {}).get("finished_at") or (refresh or {}).get(
        "started_at"
    )
    status = "up_to_date" if last_candle else "no_data"

    # Surface last pipeline outcome for ops (universe source, errors, etc.)
    last_sync_detail: dict[str, Any] = {}
    sync_run = ingestion or refresh
    if isinstance(sync_run, dict) and isinstance(sync_run.get("detail"), dict):
        detail = sync_run["detail"]
        universe = detail.get("universe")
        if isinstance(universe, dict):
            last_sync_detail["universe_source"] = universe.get("source")
            last_sync_detail["universe_tickers"] = universe.get("tickers")
        if detail.get("error"):
            last_sync_detail["error"] = detail.get("error")
        if detail.get("provider"):
            last_sync_detail["sync_provider"] = detail.get("provider")
        last_sync_detail["pipeline_status"] = sync_run.get("status")

    return {
        "asset_type": asset,
        "provider": provider,
        "last_daily_candle": last_candle.isoformat() if last_candle else None,
        "last_ingestion": (ingestion or {}).get("finished_at")
        or (ingestion or {}).get("started_at"),
        "last_calculation": (calculation or {}).get("finished_at")
        or (calculation or {}).get("started_at"),
        "last_refresh": last_refresh,
        "instruments": instruments.count or 0,
        "instruments_with_data": with_data,
        "api_requests_used": used,
        "api_requests_limit": limit,
        "max_requests_per_run": max_per_run,
        "status": status,
        "top_n": settings.crypto_top_n if asset == "CRYPTO" else None,
        "last_sync_detail": last_sync_detail or None,
    }


def refresh_stocks() -> dict[str, Any]:
    """EODHD → stock prices → stock indicators/triggers/performance only."""
    run_id = start_pipeline_run("refresh")
    try:
        sync_detail = run_sync()
        calc_detail = calculate_for_all(asset_type="STOCK")
        api_used = int(sync_detail.get("api_requests_used") or 0)
        detail = {
            "asset_type": "STOCK",
            "sync": sync_detail,
            "calculation": calc_detail,
        }
        finish_pipeline_run(
            run_id, status="success", detail=detail, api_requests_used=api_used
        )
        return {"status": "ok", "asset_type": "STOCK", "detail": detail}
    except Exception as exc:
        finish_pipeline_run(
            run_id,
            status="failed",
            detail={"error": str(exc), "asset_type": "STOCK"},
            api_requests_used=0,
        )
        raise


def refresh_crypto() -> dict[str, Any]:
    """FreeCryptoAPI → crypto prices → crypto indicators/triggers/performance only."""
    run_id = start_pipeline_run("refresh_crypto")
    try:
        # run_sync_crypto already recalculates CRYPTO by default
        sync_detail = run_sync_crypto(recalculate=True)
        api_used = int(sync_detail.get("api_requests_used") or 0)
        detail = {"asset_type": "CRYPTO", "sync": sync_detail}
        finish_pipeline_run(
            run_id, status="success", detail=detail, api_requests_used=api_used
        )
        return {"status": "ok", "asset_type": "CRYPTO", "detail": detail}
    except Exception as exc:
        finish_pipeline_run(
            run_id,
            status="failed",
            detail={"error": str(exc), "asset_type": "CRYPTO"},
            api_requests_used=0,
        )
        raise
