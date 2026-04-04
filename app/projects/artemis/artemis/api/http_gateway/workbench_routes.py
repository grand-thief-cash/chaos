"""策略研发工作台 API 路由。"""

from fastapi import APIRouter, HTTPException

from artemis.engines.workbench import list_strategies, run_backtest
from artemis.log.logger import get_logger
from artemis.models.workbench import WorkbenchRunReq, IndicatorsRequest

logger = get_logger("workbench.routes")

router = APIRouter(prefix="/workbench", tags=["workbench"])


@router.get("/strategies")
async def get_strategies():
    """返回所有可用策略及其参数 schema。"""
    return list_strategies()


@router.get("/market-data")
async def get_market_data(
    symbol: str,
    start_date: str,
    end_date: str,
    timeframe: str = "daily",
    adjust: str = "nf",
):
    """获取 K 线 OHLCV 数据。"""
    from artemis.engines.market_data_service import get_market_bars

    try:
        return get_market_bars(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            timeframe=timeframe,
            adjust=adjust,
        )
    except ValueError as e:
        logger.warning({"event": "market_data_validation_error", "error": str(e)})
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error({"event": "market_data_failed", "error": str(e)}, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")


@router.get("/indicators")
async def list_indicators():
    """返回所有可用技术指标。"""
    from artemis.engines.indicator_engine import list_available_indicators

    return {"indicators": list_available_indicators()}


@router.post("/indicators")
async def compute_indicators(req: IndicatorsRequest):
    """计算技术指标。"""
    import pandas as pd

    from artemis.engines.indicator_engine import compute_indicators as do_compute
    from artemis.engines.market_data_service import get_market_bars

    try:
        # 1. 获取 K 线数据
        market_data = get_market_bars(
            symbol=req.symbol,
            start_date=req.start_date,
            end_date=req.end_date,
            timeframe=req.timeframe,
            adjust=req.adjust,
        )
        df = pd.DataFrame(market_data["bars"])

        # 2. 计算指标
        indicator_requests = [r.model_dump() for r in req.indicators]
        series, meta = do_compute(df, indicator_requests)

        return {
            "symbol": req.symbol,
            "timeframe": req.timeframe,
            "indicators": series,
            "indicator_meta": meta,
        }
    except ValueError as e:
        logger.warning({"event": "indicators_validation_error", "error": str(e)})
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error({"event": "indicators_failed", "error": str(e)}, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")


@router.post("/run")
async def run(req: WorkbenchRunReq):
    """同步执行一次回测，返回完整结果 JSON。"""
    try:
        return run_backtest(req)
    except ValueError as e:
        logger.warning({"event": "workbench_run_validation_error", "error": str(e)})
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error({"event": "workbench_run_failed", "error": str(e)}, exc_info=True)
        raise HTTPException(status_code=500, detail="internal error")
