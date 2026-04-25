import html
import os
from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from ai_engine import default_macro_targets, generate_daily_plan, generate_evening_support
from data_store import (
    get_daily_metrics,
    get_daily_plan,
    get_evening_checkin,
    get_food_logs,
    get_food_totals,
    get_recent_metrics,
    get_settings,
    init_db,
    save_daily_plan,
    save_evening_checkin,
    update_settings,
    upsert_daily_metrics,
    add_food_log,
)
from food_db import calculate_food_macros, get_food, get_food_choices


st.set_page_config(
    page_title="Lumiq Health Companion",
    page_icon=":sparkles:",
    layout="wide",
)

init_db()


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700;800&display=swap');

        html, body, [class*="css"] {
            font-family: 'Manrope', sans-serif;
        }

        .stApp {
            background:
                radial-gradient(circle at top right, rgba(255, 194, 116, 0.25), transparent 28%),
                linear-gradient(180deg, #fffaf2 0%, #f4f8ff 60%, #eef5f2 100%);
        }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0f172a 0%, #16243f 100%);
        }

        [data-testid="stSidebar"] * {
            color: #f8fafc;
        }

        .hero-card, .soft-card {
            border-radius: 20px;
            padding: 1.2rem 1.25rem;
            margin-bottom: 1rem;
        }

        .hero-card {
            background: linear-gradient(135deg, rgba(255,255,255,0.96), rgba(255,244,222,0.95));
            border: 1px solid rgba(237, 177, 87, 0.25);
            box-shadow: 0 14px 40px rgba(15, 23, 42, 0.08);
        }

        .soft-card {
            background: rgba(255, 255, 255, 0.78);
            border: 1px solid rgba(148, 163, 184, 0.18);
            box-shadow: 0 10px 28px rgba(15, 23, 42, 0.06);
        }

        .section-label {
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-size: 0.76rem;
            font-weight: 800;
            color: #b45309;
            margin-bottom: 0.2rem;
        }

        .micro-copy {
            color: #475569;
            font-size: 0.92rem;
        }

        div[data-testid="stMetricValue"] {
            font-size: 1.5rem;
        }

        .stButton > button {
            border-radius: 999px;
            border: none;
            background: linear-gradient(135deg, #ea580c, #f59e0b);
            color: white;
            font-weight: 700;
            padding: 0.55rem 1.1rem;
        }

        .stButton > button:hover {
            background: linear-gradient(135deg, #c2410c, #d97706);
            color: white;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_card(title: str, body: str, accent: str) -> None:
    st.markdown(
        f"""
        <div class="soft-card">
            <div class="section-label">{html.escape(title)}</div>
            <div style="font-size: 1.04rem; color: {accent}; line-height: 1.6;">
                {html.escape(body)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def parse_optional_float(raw_value: str) -> float | None:
    cleaned = raw_value.strip()
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def get_api_key(settings: dict[str, object]) -> str:
    stored_key = str(settings.get("anthropic_api_key", "") or "").strip()
    return stored_key or os.getenv("ANTHROPIC_API_KEY", "").strip()


def format_macro_target_source(plan: dict[str, object] | None) -> str:
    if plan and plan.get("generated_with") == "claude":
        return "Claude recommendation"
    if plan:
        return "Smart local recommendation"
    return "Baseline recommendation"


def show_macro_progress(consumed: float, target: int, label: str) -> None:
    ratio = 0.0 if target <= 0 else min(consumed / target, 1.0)
    st.write(f"**{label}**: {consumed:.1f} / {target} g")
    st.progress(ratio)


def build_chart(dataframe: pd.DataFrame, y_column: str, title: str, color: str, y_label: str):
    chart = px.line(
        dataframe,
        x="log_date",
        y=y_column,
        markers=True,
        line_shape="spline",
        title=title,
    )
    chart.update_traces(line=dict(color=color, width=3), marker=dict(size=9, color=color))
    chart.update_layout(
        height=320,
        margin=dict(l=16, r=16, t=56, b=16),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,255,255,0.72)",
        xaxis_title="Date",
        yaxis_title=y_label,
        title_font=dict(size=18),
    )
    return chart


def render_header(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="hero-card">
            <div class="section-label">Lumiq Companion</div>
            <h1 style="margin: 0 0 0.4rem 0; color: #0f172a;">{html.escape(title)}</h1>
            <div class="micro-copy">{html.escape(subtitle)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_todays_plan(settings: dict[str, object]) -> None:
    render_header(
        "Today's Plan",
        "Log your recovery markers, generate a warm personalized plan, and close the day with an evening check-in.",
    )

    today = date.today()
    selected_date = st.date_input("Log date", value=today, help="You can backfill previous days if you want.")
    log_date = selected_date.isoformat()

    existing_metrics = get_daily_metrics(log_date)
    existing_plan = get_daily_plan(log_date)
    existing_checkin = get_evening_checkin(log_date)

    default_weight = float(existing_metrics["weight"]) if existing_metrics else float(settings["user_weight_kg"])
    default_sleep = float(existing_metrics["sleep_hours"]) if existing_metrics else 7.0
    default_steps = int(existing_metrics["steps"]) if existing_metrics else 7000
    default_stress = int(existing_metrics["stress_level"]) if existing_metrics else 5
    default_mood = int(existing_metrics["mood"]) if existing_metrics else 6
    default_hrv = "" if not existing_metrics or existing_metrics["hrv"] is None else str(existing_metrics["hrv"])
    default_resting_hr = (
        "" if not existing_metrics or existing_metrics["resting_hr"] is None else str(existing_metrics["resting_hr"])
    )

    st.caption("Tip: if you do not track HRV, resting heart rate alone still gives Lumi useful recovery context.")

    plan_to_show = existing_plan
    metrics_to_show = existing_metrics

    with st.form("daily_metrics_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            sleep_hours = st.number_input("Sleep hours", min_value=0.0, max_value=14.0, value=default_sleep, step=0.5)
            hrv_input = st.text_input("HRV (optional)", value=default_hrv, placeholder="e.g. 54")
        with col2:
            steps = st.number_input("Steps", min_value=0, max_value=50000, value=default_steps, step=500)
            resting_hr_input = st.text_input("Resting HR (optional)", value=default_resting_hr, placeholder="e.g. 62")
        with col3:
            stress_level = st.slider("Stress level", min_value=1, max_value=10, value=default_stress)
            mood = st.slider("Mood", min_value=1, max_value=10, value=default_mood)

        weight = st.number_input(
            "Weight (kg)",
            min_value=35.0,
            max_value=180.0,
            value=float(default_weight),
            step=0.5,
        )
        generate_clicked = st.form_submit_button("Generate today's plan")

    if generate_clicked:
        daily_data = {
            "date": log_date,
            "sleep_hours": float(sleep_hours),
            "hrv": parse_optional_float(hrv_input),
            "resting_hr": parse_optional_float(resting_hr_input),
            "steps": int(steps),
            "stress_level": int(stress_level),
            "mood": int(mood),
            "weight_kg": float(weight),
        }
        metrics_to_show = upsert_daily_metrics(
            log_date=log_date,
            sleep_hours=float(sleep_hours),
            hrv=daily_data["hrv"],
            resting_hr=daily_data["resting_hr"],
            steps=int(steps),
            stress_level=int(stress_level),
            mood=int(mood),
            weight=float(weight),
        )

        with st.spinner("Lumi is putting together your daily plan..."):
            plan_to_show = generate_daily_plan(daily_data=daily_data, api_key=get_api_key(settings))
        save_daily_plan(log_date, plan_to_show)
        st.success("Your daily plan is ready.")

    if metrics_to_show:
        stats_cols = st.columns(4)
        stats_cols[0].metric("Sleep", f"{metrics_to_show['sleep_hours']} h")
        stats_cols[1].metric("Steps", f"{metrics_to_show['steps']:,}")
        stats_cols[2].metric("Mood", f"{metrics_to_show['mood']}/10")
        stats_cols[3].metric("Energy", f"{metrics_to_show['energy_score']}/100")

    if plan_to_show:
        st.caption(plan_to_show.get("generation_note", ""))
        st.markdown(
            f"""
            <div class="hero-card">
                <div class="section-label">Daily Focus</div>
                <h2 style="margin: 0 0 0.4rem 0; color: #111827;">{html.escape(plan_to_show['headline'])}</h2>
                <div class="micro-copy" style="font-size: 1rem;">{html.escape(plan_to_show['supportive_message'])}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        macro_cols = st.columns(4)
        macro_targets = plan_to_show["macro_targets"]
        macro_cols[0].metric("Carbs", f"{macro_targets['carbs_g']} g")
        macro_cols[1].metric("Protein", f"{macro_targets['protein_g']} g")
        macro_cols[2].metric("Fat", f"{macro_targets['fat_g']} g")
        macro_cols[3].metric("Fiber", f"{macro_targets['fiber_g']} g")

        content_cols = st.columns(2)
        with content_cols[0]:
            render_card("Workout Recommendation", plan_to_show["workout_recommendation"], "#1d4ed8")
            render_card("Nutrition Focus", plan_to_show["nutrition_focus"], "#0f766e")
        with content_cols[1]:
            render_card("Mental Wellness Tip", plan_to_show["mental_wellness_tip"], "#7c3aed")
            render_card("Journal Prompt", plan_to_show["journal_prompt"], "#b45309")
    else:
        st.info("Generate a plan once you log today's data. If no API key is set, Lumi will still create a smart local plan.")

    st.markdown("---")
    st.subheader("Evening Check-in")
    reflection_default = existing_checkin["reflection"] if existing_checkin else ""
    reflection = st.text_area(
        "How did the day feel?",
        value=reflection_default,
        placeholder="Example: I got my walk in, but I felt mentally heavy after work.",
        height=110,
    )

    if st.button("Get evening support"):
        metrics_for_checkin = metrics_to_show or get_daily_metrics(log_date)
        if not metrics_for_checkin:
            st.warning("Log your day first so Lumi has context for the check-in.")
        elif not reflection.strip():
            st.warning("Add a quick reflection so Lumi can respond personally.")
        else:
            checkin_context = {
                "date": log_date,
                "sleep_hours": float(metrics_for_checkin["sleep_hours"]),
                "hrv": metrics_for_checkin["hrv"],
                "resting_hr": metrics_for_checkin["resting_hr"],
                "steps": int(metrics_for_checkin["steps"]),
                "stress_level": int(metrics_for_checkin["stress_level"]),
                "mood": int(metrics_for_checkin["mood"]),
                "weight_kg": float(metrics_for_checkin["weight"]),
            }
            with st.spinner("Writing your evening note..."):
                message = generate_evening_support(
                    daily_data=checkin_context,
                    daily_plan=plan_to_show or get_daily_plan(log_date),
                    reflection=reflection.strip(),
                    api_key=get_api_key(settings),
                )
            save_evening_checkin(log_date, reflection.strip(), message)
            st.success("Evening reflection saved.")
            st.markdown(
                f"""
                <div class="soft-card">
                    <div class="section-label">Lumi's Evening Note</div>
                    <div style="line-height: 1.7; color: #1f2937;">{html.escape(message)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    elif existing_checkin:
        st.markdown(
            f"""
            <div class="soft-card">
                <div class="section-label">Saved Evening Note</div>
                <div style="line-height: 1.7; color: #1f2937;">{html.escape(existing_checkin['ai_response'])}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_food_log(settings: dict[str, object]) -> None:
    render_header(
        "Food Log",
        "Track simple Indian meals, estimate macros, and compare what you ate against your plan for the day.",
    )

    selected_date = st.date_input("Meal log date", value=date.today(), key="food_log_date")
    log_date = selected_date.isoformat()
    daily_plan = get_daily_plan(log_date)
    daily_metrics = get_daily_metrics(log_date)
    weight_kg = float(daily_metrics["weight"]) if daily_metrics else float(settings["user_weight_kg"])
    macro_targets = (
        daily_plan["macro_targets"]
        if daily_plan
        else default_macro_targets(
            weight_kg=weight_kg,
            steps=int(daily_metrics["steps"]) if daily_metrics else 7000,
            stress_level=int(daily_metrics["stress_level"]) if daily_metrics else 5,
        )
    )

    food_choices = get_food_choices()

    with st.form("food_log_form"):
        col1, col2, col3 = st.columns([1, 1.2, 1])
        with col1:
            meal_type = st.selectbox("Meal type", ["Breakfast", "Lunch", "Snack", "Dinner"])
        with col2:
            food_name = st.selectbox("Food item", food_choices)
        with col3:
            servings = st.number_input("Servings", min_value=0.5, max_value=6.0, value=1.0, step=0.5)

        notes = st.text_input("Quick note (optional)", placeholder="Example: extra curd on the side")
        add_meal_clicked = st.form_submit_button("Add meal")

    selected_food = get_food(food_name)
    st.caption(
        f"{selected_food['serving']} of {food_name}: {selected_food['carbs']}g carbs, "
        f"{selected_food['protein']}g protein, {selected_food['fat']}g fat, {selected_food['fiber']}g fiber."
    )

    if add_meal_clicked:
        macros = calculate_food_macros(food_name, servings=servings)
        add_food_log(
            log_date=log_date,
            meal_type=meal_type,
            food_name=food_name,
            servings=float(servings),
            macros=macros,
            notes=notes.strip(),
        )
        st.success(f"Added {servings} serving(s) of {food_name}.")

    totals = get_food_totals(log_date)
    logs = get_food_logs(log_date)

    top_cols = st.columns([1.2, 1])
    with top_cols[0]:
        st.markdown(
            f"""
            <div class="soft-card">
                <div class="section-label">Target Source</div>
                <div style="font-size: 1.15rem; color: #111827; margin-bottom: 0.4rem;">
                    {html.escape(format_macro_target_source(daily_plan))}
                </div>
                <div class="micro-copy">
                    Carbs {macro_targets['carbs_g']}g, Protein {macro_targets['protein_g']}g,
                    Fat {macro_targets['fat_g']}g, Fiber {macro_targets['fiber_g']}g
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with top_cols[1]:
        st.metric("Calories Logged", f"{totals['calories']:.0f} kcal")

    progress_cols = st.columns(2)
    with progress_cols[0]:
        show_macro_progress(totals["carbs"], macro_targets["carbs_g"], "Carbs")
        show_macro_progress(totals["protein"], macro_targets["protein_g"], "Protein")
    with progress_cols[1]:
        show_macro_progress(totals["fat"], macro_targets["fat_g"], "Fat")
        show_macro_progress(totals["fiber"], macro_targets["fiber_g"], "Fiber")

    comparison_df = pd.DataFrame(
        [
            {"Macro": "Carbs", "Grams": totals["carbs"], "Type": "Consumed"},
            {"Macro": "Carbs", "Grams": macro_targets["carbs_g"], "Type": "Target"},
            {"Macro": "Protein", "Grams": totals["protein"], "Type": "Consumed"},
            {"Macro": "Protein", "Grams": macro_targets["protein_g"], "Type": "Target"},
            {"Macro": "Fat", "Grams": totals["fat"], "Type": "Consumed"},
            {"Macro": "Fat", "Grams": macro_targets["fat_g"], "Type": "Target"},
            {"Macro": "Fiber", "Grams": totals["fiber"], "Type": "Consumed"},
            {"Macro": "Fiber", "Grams": macro_targets["fiber_g"], "Type": "Target"},
        ]
    )
    bar_chart = px.bar(
        comparison_df,
        x="Macro",
        y="Grams",
        color="Type",
        barmode="group",
        color_discrete_map={"Consumed": "#ea580c", "Target": "#1d4ed8"},
        title="Consumed vs target",
    )
    bar_chart.update_layout(
        height=360,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,255,255,0.72)",
        margin=dict(l=16, r=16, t=56, b=16),
    )
    st.plotly_chart(bar_chart, use_container_width=True)

    if logs:
        logs_df = pd.DataFrame(logs)
        logs_df = logs_df.rename(
            columns={
                "meal_type": "Meal",
                "food_name": "Food",
                "servings": "Servings",
                "carbs": "Carbs (g)",
                "protein": "Protein (g)",
                "fat": "Fat (g)",
                "fiber": "Fiber (g)",
                "calories": "Calories",
                "notes": "Notes",
            }
        )
        st.dataframe(
            logs_df[["Meal", "Food", "Servings", "Carbs (g)", "Protein (g)", "Fat (g)", "Fiber (g)", "Calories", "Notes"]],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No meals logged for this date yet.")


def render_progress() -> None:
    render_header(
        "Progress",
        "See how your last seven days are moving across sleep, mood, and a simple energy score built from your daily markers.",
    )

    records = get_recent_metrics(days=7)
    if not records:
        st.info("Add a few daily logs and your weekly trends will show up here.")
        return

    history_df = pd.DataFrame(records)
    history_df["log_date"] = pd.to_datetime(history_df["log_date"])

    date_range = pd.date_range(end=date.today(), periods=7, freq="D")
    full_df = pd.DataFrame({"log_date": date_range})
    full_df = full_df.merge(history_df, on="log_date", how="left")
    full_df["date_label"] = full_df["log_date"].dt.strftime("%d %b")

    avg_sleep = history_df["sleep_hours"].mean()
    avg_mood = history_df["mood"].mean()
    avg_energy = history_df["energy_score"].mean()

    stat_cols = st.columns(3)
    stat_cols[0].metric("Avg sleep", f"{avg_sleep:.1f} h")
    stat_cols[1].metric("Avg mood", f"{avg_mood:.1f}/10")
    stat_cols[2].metric("Avg energy", f"{avg_energy:.0f}/100")

    sleep_chart = build_chart(full_df, "sleep_hours", "Sleep trend", "#2563eb", "Hours")
    mood_chart = build_chart(full_df, "mood", "Mood trend", "#f97316", "Mood / 10")
    energy_chart = build_chart(full_df, "energy_score", "Energy trend", "#059669", "Energy / 100")

    chart_cols = st.columns(3)
    chart_cols[0].plotly_chart(sleep_chart, use_container_width=True)
    chart_cols[1].plotly_chart(mood_chart, use_container_width=True)
    chart_cols[2].plotly_chart(energy_chart, use_container_width=True)

    latest_row = history_df.sort_values("log_date").iloc[-1]
    insight = (
        f"Your latest logged day shows {latest_row['sleep_hours']:.1f} hours of sleep, "
        f"mood {int(latest_row['mood'])}/10, and energy {int(latest_row['energy_score'])}/100. "
        "Small steady improvements here usually compound faster than one perfect day."
    )
    st.markdown(
        f"""
        <div class="soft-card">
            <div class="section-label">Weekly Insight</div>
            <div style="line-height: 1.7; color: #1f2937;">{html.escape(insight)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_settings(settings: dict[str, object]) -> None:
    render_header(
        "Settings",
        "Keep the experience personal with your default weight and Claude API key.",
    )

    env_key_present = bool(os.getenv("ANTHROPIC_API_KEY", "").strip())
    with st.form("settings_form"):
        user_weight = st.number_input(
            "Default weight (kg)",
            min_value=35.0,
            max_value=180.0,
            value=float(settings["user_weight_kg"]),
            step=0.5,
        )
        api_key_value = st.text_input(
            "Anthropic API key",
            value=str(settings.get("anthropic_api_key", "")),
            type="password",
            help="Stored locally for this single-user MVP. Leave blank to rely on ANTHROPIC_API_KEY instead.",
        )
        save_settings_clicked = st.form_submit_button("Save settings")

    if save_settings_clicked:
        updated = update_settings(user_weight_kg=float(user_weight), anthropic_api_key=api_key_value)
        settings.update(updated)
        st.success("Settings updated.")

    status_text = (
        "Claude is ready to use."
        if get_api_key(settings)
        else "No Claude key detected yet. Lumi will still work with smart local fallback guidance."
    )
    st.markdown(
        f"""
        <div class="soft-card">
            <div class="section-label">Connection Status</div>
            <div style="font-size: 1.05rem; color: #111827;">{html.escape(status_text)}</div>
            <div class="micro-copy" style="margin-top: 0.5rem;">
                Environment variable detected: {"Yes" if env_key_present else "No"}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="soft-card">
            <div class="section-label">Macro Framework</div>
            <div style="line-height: 1.7; color: #1f2937;">
                Carbs stay between 270 and 320 g, protein is set at 1.5 g per kg bodyweight,
                fat stays between 45 and 55 g, and fiber stays between 25 and 35 g.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    apply_theme()
    settings = get_settings()

    with st.sidebar:
        st.markdown("## Lumiq")
        st.caption("India-first AI health and wellness coach")
        page = st.radio(
            "Go to",
            ["Today's Plan", "Food Log", "Progress", "Settings"],
            label_visibility="collapsed",
        )
        st.markdown("---")
        st.write("Built for a single-user MVP with local storage.")

    if page == "Today's Plan":
        render_todays_plan(settings)
    elif page == "Food Log":
        render_food_log(settings)
    elif page == "Progress":
        render_progress()
    else:
        render_settings(settings)


if __name__ == "__main__":
    main()
