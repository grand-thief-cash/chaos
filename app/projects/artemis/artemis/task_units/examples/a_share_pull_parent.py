from datetime import datetime, timedelta
from typing import Any, Dict, List

from artemis.core.context import TaskContext
from artemis.task_units.parent import ParentTaskUnit


class ASharePullParentTask(ParentTaskUnit):
    """Parent task: orchestrates fetching codes & last update dates and fans out children.

    设计要点：
    - 只在注册层面对外暴露 parent（a_share_pull_parent），child 只由 parent 内部使用。
    - parent 负责：
      * 补齐 period / adjust（用于 task.yaml variant 匹配）。
      * 拉取 codes / last_updates（动态参数）。
      * 统一计算一份 end_date（例如今天），保证所有子任务用同一个结束日期，避免不一致。
    - start_date 仍由子任务根据 task.yaml 的 start_date 默认值 + last_update 自己计算。
    """

    def parameter_check(self, ctx: TaskContext):
        # Ensure period/adjust exist from incoming or defaults
        inc = ctx.incoming_params or {}
        if not inc.get('period'):
            inc['period'] = 'daily'
        if 'adjust' not in inc:
            inc['adjust'] = ''
        ctx.incoming_params = inc

    def load_dynamic_parameters(self, ctx: TaskContext) -> Dict[str, Any]:
        """Mock external systems: fetch code list and last update map, and compute unified end_date.

        返回：
        - codes: List[str]
        - last_updates: Dict[str, str]
        - end_date: str (YYYYMMDD)，所有子任务共用的结束日期
        """
        cfg = ctx.incoming_params or {}
        # Pretend to call codes service
        codes = cfg.get('codes')
        if not codes:
            codes = ['000001', '000002', '000003']
        # Pretend to call last update service per code
        last_updates: Dict[str, str] = {}
        today = datetime.now().date()
        for c in codes:
            # stagger last updates
            delta = (int(c[-1]) % 5) + 1
            last_date = today - timedelta(days=delta * 3)
            last_updates[c] = last_date.strftime('%Y%m%d')
        # 统一的 end_date，由 parent 计算出一个字符串给所有子任务使用
        end_date = today.strftime('%Y%m%d')
        return {
            'codes': codes,
            'last_updates': last_updates,
            'end_date': end_date,
        }

    def fan_out(self, ctx: TaskContext) -> List[Dict[str, Any]]:
        """Fan out child tasks per symbol.

        - 不在这里计算 start_date；子任务自己计算。
        - 把 parent 统一计算好的 end_date 传给每个子任务，确保更新区间一致。
        """
        params = ctx.params or {}
        codes = params.get('codes') or []
        sink_cfg = params.get('sink') or {}
        period = params.get('period', 'daily')
        adjust = params.get('adjust', '')
        end_date = params.get('end_date')  # 来自 load_dynamic_parameters

        specs: List[Dict[str, Any]] = []
        for sym in codes:
            specs.append({
                'key': 'a_share_pull_child',
                'params': {
                    'symbol': sym,
                    'period': period,
                    'adjust': adjust,
                    # 子任务会自己根据 symbol + last_updates 计算 start_date
                    'last_updates': params.get('last_updates') or {},
                    # 统一的 end_date 由 parent 计算，这里直接透传
                    'end_date': end_date,
                    'sink': sink_cfg,
                }
            })
        return specs

# register
try:
    from artemis.core import task_registry
    task_registry.register('a_share_pull_parent', ASharePullParentTask)
except Exception:
    pass
