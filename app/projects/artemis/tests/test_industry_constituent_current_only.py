from types import SimpleNamespace

import pandas as pd

from artemis.consts import DeptServices
from artemis.engines.task_engine.download.zh.stock_zh_a_industry_constituent_swhy import (
    StockZHAIndustryConstituentSWHY,
)


class _Logger:
    def __init__(self):
        self.events = []

    def info(self, event):
        self.events.append(event)


def test_current_only_filters_historical_and_unknown_registry_securities():
    task = StockZHAIndustryConstituentSWHY()
    ctx = SimpleNamespace(
        params={
            "current_only": True,
            "known_security_keys": [["600183", "SH"]],
        },
        run_id="industry-current-test",
        logger=_Logger(),
    )
    frame = pd.DataFrame(
        [
            {
                "INDEX_CODE": "801080.SI",
                "CON_CODE": "600183.SH",
                "INDATE": "20200101",
                "OUTDATE": None,
                "INDEX_NAME": "电子",
            },
            {
                "INDEX_CODE": "801080.SI",
                "CON_CODE": "600762.SH",
                "INDATE": "20100101",
                "OUTDATE": "20191231",
                "INDEX_NAME": "电子",
            },
            {
                "INDEX_CODE": "801080.SI",
                "CON_CODE": "999999.SH",
                "INDATE": "20200101",
                "OUTDATE": None,
                "INDEX_NAME": "电子",
            },
        ]
    )

    rows = task.post_process(ctx, {"801080.SI": frame})

    assert len(rows) == 1
    assert rows[0]["symbol"] == "600183"
    event = ctx.logger.events[-1]
    assert event["filtered_historical"] == 1
    assert event["filtered_unknown"] == 1


def test_current_only_loads_only_active_registry_securities():
    class _Phoenix:
        def get_securities(self, **kwargs):
            assert kwargs["status"] == "active"
            return {
                4889: {
                    "symbol": "600183",
                    "exchange": "SH",
                }
            }

    task = StockZHAIndustryConstituentSWHY()
    ctx = SimpleNamespace(
        params={"current_only": True},
        dept_http={DeptServices.PHOENIXA: _Phoenix()},
    )

    task.load_dynamic_parameters(ctx)

    assert ctx.params["known_security_keys"] == [["600183", "SH"]]
