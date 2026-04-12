"""
Streamlit 前端 —— 交互式行程规划界面。

修复：使用强力 CSS 选择器彻底覆盖 Streamlit 顽固的默认黑色按钮样式。
风格：纯白背景简约风。

运行方式:
  cd python
  streamlit run ui/streamlit_app.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from models.schemas import PlanningState, TravelPlanState, TravelStyle, UserPreferences
from orchestrator.pipeline import TravelPlanningPipeline

st.set_page_config(page_title="智能旅游行程规划", page_icon="✈️", layout="wide")

# ── 样式表（增强了按钮的强制覆盖 CSS） ──
st.markdown("""
<style>
/* 1. 强制覆盖 Streamlit 默认底层背景和顶部栏 */
.stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
    background-color: #f9fafb !important;
}

/* 2. 强制全局基础字体 */
html, body, [class*="css"] { 
    font-family: "PingFang SC", "Microsoft YaHei", sans-serif; 
}

/* 强制文字颜色为深灰 */
p, span, div, label {
    color: #374151;
}

/* ── 新增：强力覆盖所有按钮样式（彻底消灭黑底） ── */
/* 目标：选中所有 stButton 容器内的 button，以及通过 data-testid 选中的 button */
.stButton button, 
div[data-testid="stButton"] button {
    background-color: #ffffff !important;
    background: #ffffff !important; /* 覆盖可能存在的渐变背景 */
    border: 1px solid #d1d5db !important;
    border-radius: 8px !important;
    padding: 6px 0 !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important;
    transition: all 0.2s ease !important;
}

/* 强制按钮内的文本颜色（防止 Streamlit 内部的 <p> 标签覆盖颜色） */
.stButton button p,
.stButton button div,
div[data-testid="stButton"] button p {
    color: #111827 !important;
    font-weight: 600 !important;
    transition: color 0.2s ease !important;
}

/* 悬停状态 (Hover)：边框变蓝、背景微变、文字变蓝 */
.stButton button:hover, 
div[data-testid="stButton"] button:hover {
    border-color: #3b82f6 !important;
    background-color: #f8fafc !important;
    background: #f8fafc !important;
}

/* 悬停时内部文字变蓝 */
.stButton button:hover p,
.stButton button:hover div,
div[data-testid="stButton"] button:hover p {
    color: #3b82f6 !important;
}

/* 顶部 Hero 区域 */
.hero {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    border-radius: 16px; 
    padding: 40px 48px; 
    margin-bottom: 32px;
}
.hero h1 { font-size: 2.2rem; font-weight: 700; margin: 0 0 8px 0; color: #111827 !important; }
.hero p  { font-size: 1rem; color: #6b7280 !important; margin: 0; }

.agent-flow { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; margin-top: 20px; }
.agent-tag {
    background: #f3f4f6; border: 1px solid #d1d5db;
    border-radius: 20px; padding: 4px 14px; font-size: 0.78rem; color: #374151 !important;
    font-weight: 500;
}
.agent-arrow { color: #9ca3af !important; font-size: 0.9rem; }

/* 目的地卡片 */
.dest-card {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    border-radius: 16px; padding: 28px 32px; margin-bottom: 24px;
}
.dest-card h2 { font-size: 1.8rem; margin: 0 0 6px 0; color: #111827 !important; }
.dest-card p  { color: #4b5563 !important; margin: 0 0 16px 0; font-size: 0.95rem; }
.highlight-tag {
    display: inline-block; background: #f3f4f6; border: 1px solid #e5e7eb; border-radius: 12px;
    padding: 3px 12px; font-size: 0.8rem; margin: 3px 4px 3px 0; color: #374151 !important;
}

/* 推荐理由卡片 */
.reasoning-box {
    background: #fffbeb; border-left: 4px solid #f59e0b;
    border-radius: 0 10px 10px 0; padding: 14px 18px;
    margin: 16px 0; font-size: 0.92rem; color: #78350f !important;
}

/* 信息卡片 */
.info-card {
    background: #ffffff; border-radius: 12px; padding: 20px 24px;
    border: 1px solid #e5e7eb; margin-bottom: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.info-card-title { font-size: 0.78rem; color: #9ca3af !important; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px; }
.info-card-value { font-size: 1.3rem; font-weight: 600; color: #111827 !important; }
.info-card-sub   { font-size: 0.85rem; color: #6b7280 !important; margin-top: 4px; }

/* 预算进度条 */
.budget-bar-wrap { background: #e5e7eb; border-radius: 8px; height: 10px; margin: 10px 0 4px; overflow: hidden; }
.budget-bar-fill { height: 100%; border-radius: 8px; }

/* 欢迎页 Agent 说明卡 */
.welcome-agent-card { background: #ffffff; border-radius: 12px; padding: 16px 20px; border: 1px solid #e5e7eb; margin-bottom: 10px; box-shadow: 0 1px 2px rgba(0,0,0,0.03); }
.welcome-agent-name { font-weight: 600; color: #111827 !important; font-size: 0.95rem; }
.welcome-agent-desc { color: #6b7280 !important; font-size: 0.85rem; margin-top: 3px; }

#MainMenu, footer, header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ── 顶部 Hero ──
st.markdown("""
<div class="hero">
  <h1>✈️ 智能旅游行程规划</h1>
  <p>告诉我你的预算和喜好，AI 帮你决定去哪、怎么玩</p>
  <div class="agent-flow">
    <span class="agent-tag">偏好收集</span>
    <span class="agent-arrow">→</span>
    <span class="agent-tag">🤖 目的地推荐</span>
    <span class="agent-arrow">→</span>
    <span class="agent-tag">✈️ 航班</span>
    <span class="agent-tag">🏨 酒店</span>
    <span class="agent-tag">🤖 行程生成</span>
    <span class="agent-arrow">→</span>
    <span class="agent-tag">💰 预算校验</span>
  </div>
</div>
""", unsafe_allow_html=True)

# ── 左右分栏布局 ──
col1, col2 = st.columns([1, 2], gap="large")

# ── 左侧：表单输入 ──
with col1:
    st.markdown("#### 📝 旅行偏好")
    budget    = st.number_input("总预算（¥）", min_value=1000, max_value=500000, value=10000, step=1000)
    departure = st.text_input("出发城市", value="北京")
    dcol1, dcol2 = st.columns(2)
    with dcol1:
        start_date = st.date_input("出发日期")
    with dcol2:
        end_date = st.date_input("返回日期")
        
    style_options = ["comfort", "budget", "luxury", "adventure", "cultural", "relaxation"]
    style_labels  = {"comfort": "🛋️ 舒适", "budget": "💰 经济", "luxury": "👑 豪华",
                     "adventure": "🧗 探险", "cultural": "🏛️ 文化", "relaxation": "🏖️ 休闲"}
    style     = st.selectbox("旅行风格", style_options, format_func=lambda x: style_labels[x])
    travelers = st.number_input("出行人数", min_value=1, max_value=10, value=1)
    interests = st.multiselect("兴趣标签",
        ["🍜 美食", "🏛️ 历史", "🎨 艺术", "🌿 自然", "🛍️ 购物", "📷 摄影", "⚽ 运动"])
    notes = st.text_area("额外备注", placeholder="例：想去澳洲、不吃辣、需要无障碍设施...")
    
    st.markdown("<br>", unsafe_allow_html=True)
    plan_btn = st.button("🚀 开始规划", type="primary", use_container_width=True)

# ── 右侧：结果展示 ──
with col2:
    if plan_btn:
        with st.spinner("6个 Agent 正在协作规划您的行程，请稍候..."):
            prefs = UserPreferences(
                budget=float(budget),
                travel_style=TravelStyle(style),
                departure_city=departure,
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
                num_travelers=travelers,
                interests=[i.split(" ", 1)[-1] for i in interests],
                notes=notes,
            )
            pipeline = TravelPlanningPipeline()
            state: TravelPlanState = asyncio.run(pipeline.run(prefs))

        if state.state == PlanningState.FAILED:
            st.error("❌ 规划失败：预算不足以支撑此次行程")
            for msg in state.error_messages:
                st.markdown(f"""
                <div style="background:#fff7ed;border-left:4px solid #f97316;
                border-radius:0 10px 10px 0;padding:14px 18px;
                color:#7c2d12 !important;font-size:0.92rem;margin:8px 0">{msg}</div>
                """, unsafe_allow_html=True)
            st.stop()

        # 目的地展示卡片
        if state.selected_destination:
            d = state.selected_destination
            highlights_html = "".join(f'<span class="highlight-tag">{h}</span>' for h in d.highlights)
            st.markdown(f"""
            <div class="dest-card">
              <h2>🌍 {d.city}，{d.country}</h2>
              <p>{d.description}</p>
              <div>{highlights_html}</div>
            </div>""", unsafe_allow_html=True)

            if state.destination_rec and state.destination_rec.reasoning:
                st.markdown(f"""
                <div class="reasoning-box">
                💡 <strong>AI 推荐理由：</strong>{state.destination_rec.reasoning}
                </div>""", unsafe_allow_html=True)

            if state.destination_rec and len(state.destination_rec.destinations) > 1:
                with st.expander("🗺️ 查看其他候选目的地"):
                    for alt in state.destination_rec.destinations[1:]:
                        st.markdown(f"**{alt.city}**，{alt.country}　｜　{alt.description}")

        # 核心结果 Tabs
        tab1, tab2, tab3, tab4 = st.tabs(["✈️  航班", "🏨  酒店", "📅  每日行程", "💰  预算"])

        with tab1:
            if state.flight_result:
                fr = state.flight_result
                fc1, fc2 = st.columns(2)
                if fr.recommended_outbound:
                    o = fr.recommended_outbound
                    with fc1:
                        st.markdown(f"""
                        <div class="info-card">
                          <div class="info-card-title">去程推荐</div>
                          <div class="info-card-value">{o.airline}</div>
                          <div class="info-card-sub">{o.flight_no}　·　{o.duration_hours}h　·　经停 {o.stops} 次</div>
                          <div style="margin-top:10px;font-size:1.1rem;font-weight:600;color:#dc2626 !important">¥{o.price:.0f}</div>
                        </div>""", unsafe_allow_html=True)
                if fr.recommended_return:
                    r = fr.recommended_return
                    with fc2:
                        st.markdown(f"""
                        <div class="info-card">
                          <div class="info-card-title">返程推荐</div>
                          <div class="info-card-value">{r.airline}</div>
                          <div class="info-card-sub">{r.flight_no}　·　{r.duration_hours}h　·　经停 {r.stops} 次</div>
                          <div style="margin-top:10px;font-size:1.1rem;font-weight:600;color:#dc2626 !important">¥{r.price:.0f}</div>
                        </div>""", unsafe_allow_html=True)
                st.markdown(f"""
                <div style="text-align:right;color:#6b7280;font-size:0.9rem;margin-top:4px">
                航班总费用：<strong style="color:#111827;font-size:1rem">¥{fr.total_flight_cost:.0f}</strong>
                </div>""", unsafe_allow_html=True)

        with tab2:
            if state.hotel_result and state.hotel_result.recommended:
                h = state.hotel_result.recommended
                stars = "⭐" * int(h.star_rating)
                amenities_html = "".join(
                    f'<span style="background:#f3f4f6;border-radius:8px;padding:3px 10px;'
                    f'font-size:0.8rem;margin:3px 4px 3px 0;display:inline-block;color:#374151">{a}</span>'
                    for a in h.amenities)
                st.markdown(f"""
                <div class="info-card">
                  <div class="info-card-title">推荐住宿</div>
                  <div class="info-card-value">{h.name}</div>
                  <div class="info-card-sub">{stars}　·　距市中心 {h.distance_to_center_km}km</div>
                  <div style="margin:12px 0 8px">{amenities_html}</div>
                  <div style="display:flex;justify-content:space-between;align-items:center;
                  margin-top:12px;padding-top:12px;border-top:1px solid #f3f4f6">
                    <span style="color:#6b7280;font-size:0.88rem">¥{h.price_per_night:.0f} / 晚 × {state.hotel_result.total_nights} 晚</span>
                    <span style="font-size:1.1rem;font-weight:600;color:#dc2626 !important">¥{state.hotel_result.total_hotel_cost:.0f}</span>
                  </div>
                </div>""", unsafe_allow_html=True)

        with tab3:
            if state.activity_result:
                slot_config = {
                    "morning":   ("上午", "#fef3c7", "#92400e"),
                    "afternoon": ("下午", "#dbeafe", "#1e40af"),
                    "evening":   ("晚上", "#ede9fe", "#5b21b6"),
                }
                
                for day in state.activity_result.day_plans:
                    with st.container():
                        st.markdown(f"""
                        <div style="display: flex; justify-content: space-between; align-items: center; 
                                    padding-bottom: 8px; border-bottom: 2px solid #e5e7eb; margin-bottom: 12px; margin-top: 16px;">
                            <span style="font-size: 1.05rem; font-weight: 600; color: #111827 !important;">📅 {day.date}</span>
                            <span style="color: #6b7280 !important; font-size: 0.88rem;">日花费 ¥{day.day_cost:.0f}</span>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        for act in day.activities:
                            label, bg, color = slot_config.get(act.time_slot, ("其他", "#f3f4f6", "#374151"))
                            price_str   = "免费" if act.price == 0 else f"¥{act.price:.0f}"
                            price_color = "#059669" if act.price == 0 else "#dc2626"
                            desc_html   = f'<div style="font-size: 0.82rem; color: #6b7280; margin-top: 4px;">{act.description}</div>' if act.description else ""
                            
                            act_col1, act_col2, act_col3 = st.columns([1.5, 6, 1.5])
                            
                            with act_col1:
                                st.markdown(f"""
                                <div style="background: {bg}; color: {color} !important; font-size: 0.75rem; font-weight: 600; 
                                     padding: 4px 8px; border-radius: 8px; text-align: center; margin-top: 2px; white-space: nowrap;">
                                     {label}
                                </div>
                                """, unsafe_allow_html=True)
                                
                            with act_col2:
                                st.markdown(f"""
                                <div style="font-size: 0.95rem; font-weight: 600; color: #111827 !important;">{act.name}</div>
                                {desc_html}
                                """, unsafe_allow_html=True)
                                
                            with act_col3:
                                st.markdown(f"""
                                <div style="text-align: right; font-size: 0.95rem; font-weight: 600; color: {price_color} !important;">{price_str}</div>
                                <div style="text-align: right; font-size: 0.8rem; color: #9ca3af; margin-top: 2px;">{act.duration_hours}h</div>
                                """, unsafe_allow_html=True)
                                
                            st.markdown("<hr style='margin: 12px 0; border: none; border-top: 1px dashed #e5e7eb;'>", unsafe_allow_html=True)

        with tab4:
            if state.budget_breakdown:
                bb = state.budget_breakdown
                used_pct  = min(bb.total_cost / bb.budget * 100, 100) if bb.budget > 0 else 0
                bar_color = "#10b981" if bb.is_within_budget else "#ef4444"
                
                mc1, mc2, mc3 = st.columns(3)
                mc1.metric("✈️ 航班", f"¥{bb.flight_cost:.0f}")
                mc2.metric("🏨 酒店",  f"¥{bb.hotel_cost:.0f}")
                mc3.metric("🎯 活动", f"¥{bb.activity_cost:.0f}")
                st.markdown("<br>", unsafe_allow_html=True)
                
                status_text  = f"✅ 预算内，节省 ¥{bb.remaining:.0f}" if bb.is_within_budget else f"⚠️ 超出预算 ¥{bb.over_budget_amount:.0f}"
                status_color = "#059669" if bb.is_within_budget else "#dc2626"
                
                st.markdown(f"""
                <div style="margin-bottom:6px;display:flex;justify-content:space-between;align-items:center">
                  <span style="font-size:0.9rem;color:#374151">
                    总花费 <strong style="color: #111827 !important;">¥{bb.total_cost:.0f}</strong>　/　预算 <strong style="color: #111827 !important;">¥{bb.budget:.0f}</strong>
                  </span>
                  <span style="font-size:0.88rem;font-weight: 600;color:{status_color} !important">{status_text}</span>
                </div>
                <div class="budget-bar-wrap">
                  <div class="budget-bar-fill" style="width:{used_pct:.1f}%;background:{bar_color}"></div>
                </div>
                <div style="text-align:right;font-size:0.78rem;color:#9ca3af;margin-top:4px;">{used_pct:.1f}% 已使用</div>
                """, unsafe_allow_html=True)
                
                if state.adjustment_round > 0:
                    st.info(f"🔄 经过 {state.adjustment_round} 轮预算调整后达到当前方案")
                if bb.suggestions:
                    with st.expander("💡 节省建议"):
                        for s in bb.suggestions:
                            st.markdown(f"- {s}")

        if state.error_messages:
            for msg in state.error_messages:
                st.warning(msg)

    # ── 空白默认状态 ──
    else:
        st.markdown("""
        <div style="background:#f0f9ff;border:1px solid #bae6fd;border-radius:12px;
        padding:20px 24px;margin-bottom:28px;color:#0c4a6e !important;font-size:0.95rem">
        👈 在左侧填写你的旅行偏好，点击「开始规划」，AI 会自动推荐目的地并生成完整行程。
        </div>""", unsafe_allow_html=True)

        st.markdown("#### 🤖 6个 Agent 如何协作")
        agents = [
            ("⚙️", "Preference Agent",  "收集偏好，自动补充兴趣标签"),
            ("🌍", "Destination Agent", "LLM 推荐目的地，考虑季节 / 签证 / 性价比"),
            ("✈️", "Flight Agent",      "搜索航班，多因素加权推荐最优组合"),
            ("🏨", "Hotel Agent",       "按旅行风格匹配星级和价格范围"),
            ("📅", "Activity Agent",    "LLM 生成每日行程，上午 / 下午 / 晚上分配"),
            ("💰", "Budget Agent",      "预算校验，超预算渐进式调整，最多 3 轮"),
        ]
        for icon, name, desc in agents:
            st.markdown(f"""
            <div class="welcome-agent-card">
              <div class="welcome-agent-name">{icon} {name}</div>
              <div class="welcome-agent-desc">{desc}</div>
            </div>""", unsafe_allow_html=True)