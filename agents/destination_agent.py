"""
Destination Agent —— 目的地推荐 Agent。

职责: 根据用户偏好推荐目的地，考虑季节、签证、安全性、性价比。
在 Pipeline 中处于第二个节点，接收 preferences，输出 DestinationRecommendation。

面试考点:
  - 推荐算法: 基于多维加权评分（预算匹配度、季节适宜度、安全评分）
  - 为什么不直接让用户选城市？ —— 提升用户体验，发现长尾目的地
  - Mock 数据库 vs 真实 API: 演示用 mock，生产环境接 Amadeus / Google Places
"""

from __future__ import annotations

import json
import re
from datetime import datetime

from loguru import logger

from models.schemas import (
    Destination,
    DestinationRecommendation,
    PlanningState,
    TravelPlanState,
)
#pydantic， 数据结构+状态定义 引入

from .base_agent import BaseAgent

MOCK_DESTINATIONS: list[dict] = [
    {
        "city": "东京",
        "country": "日本",
        "description": "传统与现代的完美融合，美食天堂",
        "best_season": "spring,autumn",
        "visa_required": True,
        "safety_score": 9.5,
        "cost_level": "high",
        "highlights": ["浅草寺", "涩谷十字路口", "筑地市场", "东京塔"],
    },
    {
        "city": "曼谷",
        "country": "泰国",
        "description": "热带风情，物美价廉的旅游胜地",
        "best_season": "winter",
        "visa_required": False,
        "safety_score": 7.5,
        "cost_level": "low",
        "highlights": ["大皇宫", "卧佛寺", "考山路", "暹罗广场"],
    },
    {
        "city": "巴黎",
        "country": "法国",
        "description": "浪漫之都，艺术与美食的殿堂",
        "best_season": "spring,summer",
        "visa_required": True,
        "safety_score": 8.0,
        "cost_level": "high",
        "highlights": ["埃菲尔铁塔", "卢浮宫", "香榭丽舍大街", "蒙马特高地"],
    },
    {
        "city": "清迈",
        "country": "泰国",
        "description": "宁静的兰纳古城，适合文化与休闲",
        "best_season": "winter",
        "visa_required": False,
        "safety_score": 8.5,
        "cost_level": "low",
        "highlights": ["双龙寺", "古城", "夜间动物园", "周末夜市"],
    },
    {
        "city": "首尔",
        "country": "韩国",
        "description": "潮流时尚与历史文化交汇",
        "best_season": "spring,autumn",
        "visa_required": False,
        "safety_score": 9.0,
        "cost_level": "medium",
        "highlights": ["景福宫", "明洞", "北村韩屋村", "南山塔"],
    },
    {
        "city": "大阪",
        "country": "日本",
        "description": "日本的厨房，环球影城所在地",
        "best_season": "spring,autumn",
        "visa_required": True,
        "safety_score": 9.5,
        "cost_level": "medium",
        "highlights": ["大阪城", "道顿堀", "环球影城", "黑门市场"],
    },
]


class DestinationAgent(BaseAgent):
    name = "DestinationAgent"  # 类变量，用于日志输出识别

    async def execute(self, state: TravelPlanState) -> TravelPlanState:
        pref = state.preferences  # 从状态中获取用户偏好
        if pref is None:
            raise ValueError("缺少用户偏好")

        system_prompt = """你是一位专业的旅游顾问。根据用户的旅行偏好，推荐3个最合适的目的地。
你必须严格按照以下JSON格式返回，不要输出任何其他内容，不要有markdown代码块：
{
  "destinations": [
    {
      "city": "城市名",
      "country": "国家名",
      "description": "一句话描述",
      "best_season": "spring或summer或autumn或winter，多个用英文逗号分隔",
      "visa_required": true或false,
      "safety_score": 1到10之间的浮点数,
      "cost_level": "low或medium或high",
      "highlights": ["亮点1", "亮点2", "亮点3", "亮点4"]
    }
  ],
  "reasoning": "推荐理由，一两句话"
}"""

        user_prompt = f"""用户旅行偏好：
- 出发城市：{pref.departure_city}
- 出行日期：{pref.start_date} 至 {pref.end_date}
- 总预算：¥{pref.budget}（{pref.num_travelers}人）
- 旅行风格：{pref.travel_style.value}
- 兴趣爱好：{', '.join(pref.interests) if pref.interests else '未指定'}
- 额外备注：{pref.notes if pref.notes else '无'}

请推荐3个最适合的目的地，按推荐优先级排列，第一个是最推荐的。"""

        try:
            raw = await self.call_llm(user_prompt, system_prompt)
            logger.info(f"[{self.name}] LLM 原始返回: {raw[:200]}")

            # 提取 JSON，防止 LLM 多输出文字或 markdown 代码块
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if not match:
                raise ValueError("LLM 返回内容中未找到 JSON")

            data = json.loads(match.group())
            dest_list = data.get("destinations", [])

            if not dest_list:
                raise ValueError("LLM 返回的 destinations 列表为空")

            destinations = []
            for d in dest_list:
                destinations.append(Destination(
                    city=d["city"],
                    country=d["country"],
                    description=d["description"],
                    best_season=d.get("best_season", ""),
                    visa_required=d.get("visa_required", False),
                    safety_score=float(d.get("safety_score", 8.0)),
                    cost_level=d.get("cost_level", "medium"),
                    highlights=d.get("highlights", []),
                ))

            selected = destinations[0]
            reasoning = data.get("reasoning", f"根据您的偏好，推荐 {selected.city}")

            state.destination_rec = DestinationRecommendation(
                destinations=destinations,
                selected=selected,
                reasoning=reasoning,
            )
            state.state = PlanningState.SEARCHING_PARALLEL
            logger.info(f"[{self.name}] LLM 推荐目的地: {selected.city}, {selected.country}")

        except Exception as e:
            logger.warning(f"[{self.name}] LLM 调用失败 ({e})，降级使用 mock 数据")
            state = self._mock_execute(state)

        return state

    def _mock_execute(self, state: TravelPlanState) -> TravelPlanState:
        """LLM 失败时的降级方案，使用原始 mock 逻辑。"""
        pref = state.preferences
        scored = []
        for d_data in MOCK_DESTINATIONS:
            dest = Destination(**d_data)
            score = self._score_destination(dest, pref.budget, pref.travel_style.value, pref.start_date)
            scored.append((score, dest))

        scored.sort(key=lambda x: x[0], reverse=True)
        top3 = [d for _, d in scored[:3]]
        selected = top3[0]

        state.destination_rec = DestinationRecommendation(
            destinations=top3,
            selected=selected,
            reasoning=f"根据您 ¥{pref.budget} 的预算和 {pref.travel_style.value} 风格，推荐 {selected.city}",
        )
        state.state = PlanningState.SEARCHING_PARALLEL
        logger.info(f"[{self.name}] mock 推荐目的地: {selected.city}, {selected.country}")
        return state

    @staticmethod  # 纯函数，输入相同输出相同，无副作用，方便测试和维护
    def _score_destination(dest: Destination, budget: float, style: str, start_date: str) -> float:
        score = 0.0

        cost_budget_map = {"low": 8000, "medium": 15000, "high": 25000}
        est_cost = cost_budget_map.get(dest.cost_level, 15000)
        if budget >= est_cost:
            score += 30
        elif budget >= est_cost * 0.7:
            score += 15

        score += dest.safety_score * 3

        try:
            month = datetime.strptime(start_date, "%Y-%m-%d").month
        except (ValueError, TypeError):
            month = 6

        season_map = {12: "winter", 1: "winter", 2: "winter",
                      3: "spring", 4: "spring", 5: "spring",
                      6: "summer", 7: "summer", 8: "summer",
                      9: "autumn", 10: "autumn", 11: "autumn"}
        current_season = season_map.get(month, "summer")
        if current_season in dest.best_season:
            score += 20

        style_cost_pref = {"budget": "low", "comfort": "medium", "luxury": "high",
                           "adventure": "low", "cultural": "medium", "relaxation": "medium"}
        if style_cost_pref.get(style) == dest.cost_level:
            score += 15

        if not dest.visa_required:
            score += 10

        return score