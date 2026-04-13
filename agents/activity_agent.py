"""
Activity Agent —— 活动/景点推荐 Agent。

职责: 推荐景点/餐厅/体验，生成每日行程安排。
在并行阶段执行，与 Flight Agent / Hotel Agent 同时运行。

"""

from __future__ import annotations

import json
import re
import random
from datetime import datetime, timedelta

from loguru import logger

from models.schemas import Activity, ActivitySearchResult, DayPlan, TravelPlanState

from .base_agent import BaseAgent

MOCK_ACTIVITIES_DB: dict[str, list[dict]] = {
    "default": [
        {"name": "城市地标打卡", "category": "sightseeing", "duration_hours": 2.0, "price": 0, "rating": 8.5, "time_slot": "morning"},
        {"name": "当地市场探索", "category": "food", "duration_hours": 1.5, "price": 100, "rating": 8.0, "time_slot": "morning"},
        {"name": "博物馆参观", "category": "sightseeing", "duration_hours": 3.0, "price": 80, "rating": 8.8, "time_slot": "morning"},
        {"name": "特色午餐", "category": "food", "duration_hours": 1.5, "price": 150, "rating": 9.0, "time_slot": "afternoon"},
        {"name": "历史街区漫步", "category": "sightseeing", "duration_hours": 2.0, "price": 0, "rating": 7.5, "time_slot": "afternoon"},
        {"name": "手工艺体验", "category": "experience", "duration_hours": 2.0, "price": 200, "rating": 8.5, "time_slot": "afternoon"},
        {"name": "日落观景", "category": "sightseeing", "duration_hours": 1.0, "price": 50, "rating": 9.0, "time_slot": "evening"},
        {"name": "当地夜市美食", "category": "food", "duration_hours": 2.0, "price": 120, "rating": 8.5, "time_slot": "evening"},
        {"name": "文化演出", "category": "experience", "duration_hours": 2.0, "price": 300, "rating": 9.2, "time_slot": "evening"},
        {"name": "温泉/SPA体验", "category": "experience", "duration_hours": 2.0, "price": 350, "rating": 9.0, "time_slot": "afternoon"},
        {"name": "公园休闲", "category": "sightseeing", "duration_hours": 1.5, "price": 0, "rating": 7.0, "time_slot": "morning"},
        {"name": "购物街逛逛", "category": "experience", "duration_hours": 2.0, "price": 0, "rating": 7.5, "time_slot": "afternoon"},
    ],
}


class ActivityAgent(BaseAgent):
    name = "ActivityAgent"

    async def execute(self, state: TravelPlanState) -> TravelPlanState:
        pref = state.preferences
        dest = state.selected_destination
        if pref is None or dest is None:
            raise ValueError("缺少偏好或目的地信息")

        days = self._get_travel_days(pref.start_date, pref.end_date)
        daily_budget = (pref.budget * 0.25) / max(len(days), 1) / pref.num_travelers

        system_prompt = """你是一位专业的旅行规划师，熟悉全球各地的景点、美食和文化体验。
请根据用户的目的地、行程日期和兴趣爱好，生成详细的每日行程安排，行程规划要合理、丰富且具有当地特色。
你必须严格按照以下JSON格式返回，不要输出任何其他内容，不要有markdown代码块：
{
  "day_plans": [
    {
      "date": "YYYY-MM-DD",
      "activities": [
        {
          "name": "具体活动名称（要有当地特色，不要泛泛而谈）",
          "category": "sightseeing或food或experience",
          "duration_hours": 时长数字,
          "price": 人民币价格数字,
          "rating": 7到10之间的评分数字,
          "time_slot": "morning或afternoon或evening",
          "description": "一句话描述这个活动的亮点"
        }
      ]
    }
  ]
}
每天必须包含morning、afternoon、evening各一个活动，活动要有当地特色，避免重复。"""

        user_prompt = f"""请为以下旅行生成每日行程：
- 目的地：{dest.city}，{dest.country}
- 行程日期：{', '.join(days)}（共 {len(days)} 天）
- 旅行风格：{pref.travel_style.value}
- 兴趣爱好：{', '.join(pref.interests) if pref.interests else '未指定'}
- 每人每日活动预算：¥{daily_budget:.0f}
- 出行人数：{pref.num_travelers}人
- 额外备注：{pref.notes if pref.notes else '无'}

要求：
1. 活动名称要具体，体现{dest.city}的当地特色
2. 不同天的活动不要重复
3. 价格参考当地实际水平，单位为人民币"""

        try:
            '''
            调用LLM并解析JSON
            '''
            raw = await self.call_llm(user_prompt, system_prompt)
            logger.info(f"[{self.name}] LLM 原始返回: {raw[:200]}")

            match = re.search(r'\{.*\}', raw, re.DOTALL)
            #re.DOTALL 让 . 可以匹配换行符，确保能提取多行的 JSON
            #从返回文本里找第一个{开始的 JSON 对象，防止 LLM 输出了额外的文字或 markdown 代码块}
            if not match:
                raise ValueError("LLM 返回内容中未找到 JSON")

            data = json.loads(match.group())
            # match.group() 取出正则匹配的字符串，json.loads 解析成 Python 字典

            llm_day_plans = data.get("day_plans", [])
            if not llm_day_plans:
                raise ValueError("LLM 返回的 day_plans 列表为空")
            

            '''
            把LLM返回的字典转换成 ActivitySearchResult 结构，计算总活动费用
            '''
            day_plans: list[DayPlan] = []
            total_cost = 0.0

            for dp in llm_day_plans:
                activities = []
                for a in dp.get("activities", []):
                    activities.append(Activity(
                        name=a["name"],
                        category=a.get("category", "sightseeing"),#用.get()default避免KeyError
                        location=dest.city,
                        duration_hours=float(a.get("duration_hours", 2.0)),
                        price=float(a.get("price", 0)),
                        rating=float(a.get("rating", 8.0)),
                        description=a.get("description", ""),
                        time_slot=a.get("time_slot", "morning"),
                    ))

                day_cost = sum(a.price for a in activities) * pref.num_travelers
                total_cost += day_cost
                day_plans.append(DayPlan(
                    date=dp["date"],
                    activities=activities,
                    day_cost=day_cost,
                ))

            state.activity_result = ActivitySearchResult(
                day_plans=day_plans,
                total_activity_cost=total_cost,
            )
            logger.info(f"[{self.name}] LLM 生成 {len(day_plans)} 天行程, 活动总费用: ¥{total_cost:.0f}")

            '''
            LLM 调用失败时的降级方案，使用原始 mock 逻辑，保证系统的鲁棒性和用户体验
            '''
        except Exception as e:
            logger.warning(f"[{self.name}] LLM 调用失败 ({e})，降级使用 mock 数据")
            state = self._mock_execute(state, days, daily_budget, dest.city, pref)

        return state

    def _mock_execute(self, state, days, daily_budget, city, pref) -> TravelPlanState:
        """LLM 失败时的降级方案，使用原始 mock 逻辑。"""
        pool = self._get_activity_pool(city)
        day_plans: list[DayPlan] = []
        total_cost = 0.0

        for date_str in days:
            plan = self._plan_one_day(date_str, pool, daily_budget, pref.interests)
            day_cost = sum(a.price for a in plan.activities) * pref.num_travelers
            plan.day_cost = day_cost
            total_cost += day_cost
            day_plans.append(plan)

        state.activity_result = ActivitySearchResult(
            day_plans=day_plans,
            total_activity_cost=total_cost,
        )
        logger.info(f"[{self.name}] mock 生成 {len(day_plans)} 天行程, 活动总费用: ¥{total_cost:.0f}")
        return state

    @staticmethod
    def _get_travel_days(start: str, end: str) -> list[str]:
        try:
            d1 = datetime.strptime(start, "%Y-%m-%d")
            d2 = datetime.strptime(end, "%Y-%m-%d")
            days_count = max((d2 - d1).days, 1)
            return [(d1 + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days_count)]
        except (ValueError, TypeError):
            return ["2026-01-01", "2026-01-02", "2026-01-03"]

    @staticmethod
    def _get_activity_pool(city: str) -> list[dict]:
        pool = MOCK_ACTIVITIES_DB.get(city, MOCK_ACTIVITIES_DB["default"])
        return [dict(a, location=city) for a in pool]

    @staticmethod
    def _plan_one_day(date: str, pool: list[dict], daily_budget: float, interests: list[str]) -> DayPlan:
        slots = ["morning", "afternoon", "evening"]
        activities: list[Activity] = []

        for slot in slots:
            candidates = [a for a in pool if a["time_slot"] == slot]
            if not candidates:
                continue

            for c in candidates:
                bonus = sum(2 for tag in interests if tag in c["name"] or tag in c["category"])
                c["_score"] = c["rating"] + bonus + random.uniform(0, 1)

            candidates.sort(key=lambda x: x["_score"], reverse=True)
            best = candidates[0]
            activities.append(Activity(
                name=best["name"],
                category=best["category"],
                location=best.get("location", ""),
                duration_hours=best["duration_hours"],
                price=float(best["price"]),
                rating=best["rating"],
                description=f"{date} {slot} - {best['name']}",
                time_slot=slot,
            ))

        return DayPlan(date=date, activities=activities)