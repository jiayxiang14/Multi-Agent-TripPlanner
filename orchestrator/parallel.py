"""
并行执行器 —— 同时运行多个 Agent，等待全部完成后合并结果。

  - 为什么并行？ Flight/Hotel/Activity 三个 Agent 互不依赖，串行执行浪费时间
  - asyncio.gather vs ThreadPoolExecutor: 纯 IO 密集用 asyncio，CPU 密集用线程
  - 错误处理: 某个 Agent 失败不影响其他 Agent，用 return_exceptions=True
  - 超时控制: asyncio.wait_for 限制单个 Agent 最大执行时间
"""

from __future__ import annotations

import asyncio
import time
from typing import Sequence

from loguru import logger

from agents.base_agent import BaseAgent
from config.settings import settings
from models.schemas import TravelPlanState


class ParallelExecutor:
    """并行执行一组 Agent，将各自输出合并到同一 state 对象。"""

    def __init__(self, agents: Sequence[BaseAgent], timeout: int | None = None):
        self.agents = list(agents)
        self.timeout = timeout or settings.PARALLEL_TIMEOUT

    async def run(self, state: TravelPlanState) -> TravelPlanState:
        logger.info(f"[ParallelExecutor] 启动 {len(self.agents)} 个 Agent 并行执行...")

        start = time.time()

        tasks = [
            asyncio.wait_for(agent.run(state), timeout=self.timeout)
            for agent in self.agents
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 遍历每个 Agent 的执行结果
        for agent, result in zip(self.agents, results):
            if isinstance(result, Exception):
                # 某个 Agent 失败，记录错误但不影响其他 Agent
                err_msg = f"{agent.name} 并行执行失败: {result}"
                logger.error(err_msg)
                state.error_messages.append(err_msg)
            else:
                # 把每个 Agent 写入的字段显式合并回主 state
                # 修复原始代码依赖对象引用副作用的问题
                if result.flight_result is not None:
                    state.flight_result = result.flight_result
                if result.hotel_result is not None:
                    state.hotel_result = result.hotel_result
                if result.activity_result is not None:
                    state.activity_result = result.activity_result

        elapsed = time.time() - start
        estimated_serial = elapsed * len(self.agents)
        logger.info(
            f"[ParallelExecutor] 并行执行完成，"
            f"实际耗时 {elapsed:.1f}s（若串行约需 {estimated_serial:.1f}s，"
            f"并行节省约 {estimated_serial - elapsed:.1f}s）"
        )

        return state