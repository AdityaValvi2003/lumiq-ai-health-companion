import json
import re
from typing import Any

from anthropic import Anthropic


MODEL_NAME = "claude-sonnet-4-6"

SYSTEM_PROMPT = """
You are Lumi, a warm and motivating AI health companion for a young Indian fitness enthusiast.
Your role is to turn daily wellness data into practical, encouraging guidance that feels personal,
supportive, and grounded in real life in India.

You are not clinical, cold, or robotic. You sound like a thoughtful coach who wants the user to win
without burning out. You adapt your tone based on recovery:
- If mood and recovery are strong, sound energetic, upbeat, and action-oriented.
- If sleep is low, stress is high, or mood is low, sound gentle, reassuring, and recovery-focused.

Important guidance:
- Always be warm, personal, and concise.
- Use Indian food examples naturally when helpful.
- Never diagnose conditions or make extreme claims.
- Keep workout suggestions realistic for a normal day.
- Macro targets must follow these guardrails:
  - carbs: 270 to 320 g
  - protein: 1.5 g per kg bodyweight
  - fat: 45 to 55 g
  - fiber: 25 to 35 g
"""


def default_macro_targets(
    weight_kg: float,
    steps: int = 0,
    stress_level: int = 5,
) -> dict[str, int]:
    carbs = int(round(min(320, max(270, 270 + (steps / 10000.0) * 50))))
    protein = int(round(weight_kg * 1.5))
    fat = int(round(min(55, max(45, 45 + stress_level))))
    fiber = int(round(min(35, max(25, 26 + (steps / 3000.0)))))
    return {
        "carbs_g": carbs,
        "protein_g": protein,
        "fat_g": fat,
        "fiber_g": fiber,
    }


def _extract_json_block(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in Claude response.")

    return json.loads(cleaned[start : end + 1])


def _normalize_macro_targets(
    raw_targets: dict[str, Any] | None,
    weight_kg: float,
    steps: int,
    stress_level: int,
) -> dict[str, int]:
    fallback = default_macro_targets(weight_kg, steps=steps, stress_level=stress_level)
    if not raw_targets:
        return fallback

    def _safe_number(key: str, default: int) -> int:
        try:
            return int(round(float(raw_targets.get(key, default))))
        except (TypeError, ValueError):
            return default

    return {
        "carbs_g": min(320, max(270, _safe_number("carbs_g", fallback["carbs_g"]))),
        "protein_g": int(round(weight_kg * 1.5)),
        "fat_g": min(55, max(45, _safe_number("fat_g", fallback["fat_g"]))),
        "fiber_g": min(35, max(25, _safe_number("fiber_g", fallback["fiber_g"]))),
    }


def _fallback_plan(daily_data: dict[str, Any]) -> dict[str, Any]:
    sleep_hours = float(daily_data.get("sleep_hours", 0))
    mood = int(daily_data.get("mood", 5))
    stress_level = int(daily_data.get("stress_level", 5))
    steps = int(daily_data.get("steps", 0))
    weight_kg = float(daily_data.get("weight_kg", 60))
    macro_targets = default_macro_targets(
        weight_kg=weight_kg,
        steps=steps,
        stress_level=stress_level,
    )

    strong_day = sleep_hours >= 7 and mood >= 7 and stress_level <= 5
    recovery_day = sleep_hours < 6 or mood <= 4 or stress_level >= 8

    if strong_day:
        headline = "You have good momentum today. Let us turn it into a focused win."
        workout = (
            "Go for a 40 to 50 minute strength or hybrid session, then finish with 8 to 10 minutes "
            "of mobility or a slow cooldown walk."
        )
        nutrition_focus = (
            "Lean into steady energy: roti or rice with dal, paneer or eggs for protein, and curd or fruit "
            "around training so you stay fueled without feeling heavy."
        )
        mental_tip = "Channel the good mood well: take one minute before your workout to set an intention."
        journal_prompt = "Where do I already have momentum today, and how can I build on it?"
        supportive_message = "You are in a solid zone today. A little structure will go a long way."
    elif recovery_day:
        headline = "Today looks like a recovery-first day, and that is still progress."
        workout = (
            "Keep it light with a 25 to 35 minute easy walk, gentle yoga, or mobility work. "
            "Skip all-out intensity and aim to feel better after moving."
        )
        nutrition_focus = (
            "Prioritize simple, comforting meals with enough protein: dal, curd rice, paneer bhurji, "
            "khichdi, fruit, and plenty of water through the day."
        )
        mental_tip = "Pause for five slow breaths before lunch and again in the evening to bring your system down."
        journal_prompt = "What is one small thing that would help me feel supported today?"
        supportive_message = "A softer day is not a setback. Recovery is part of the plan."
    else:
        headline = "You are in a balanced zone today. Consistency beats intensity."
        workout = (
            "Aim for a 30 to 40 minute moderate session: brisk walk, easy run, bodyweight circuit, "
            "or a short gym session with clean form."
        )
        nutrition_focus = (
            "Keep each meal balanced: carbs for energy, protein at every meal, and fiber from sabzi, dal, "
            "fruit, or oats so your energy stays steady."
        )
        mental_tip = "Pick one anchor habit today, like a 10 minute walk after meals or a short stretch break."
        journal_prompt = "What one habit would make today feel more grounded and on track?"
        supportive_message = "You do not need a perfect day. You just need a well-paced one."

    return {
        "headline": headline,
        "workout_recommendation": workout,
        "nutrition_focus": nutrition_focus,
        "macro_targets": macro_targets,
        "mental_wellness_tip": mental_tip,
        "journal_prompt": journal_prompt,
        "supportive_message": supportive_message,
        "generated_with": "fallback",
        "generation_note": "Smart local guidance is active because Claude is not connected right now.",
    }


def _normalize_plan(raw_plan: dict[str, Any], daily_data: dict[str, Any]) -> dict[str, Any]:
    fallback = _fallback_plan(daily_data)
    normalized = fallback.copy()
    normalized.update(
        {
            "headline": str(raw_plan.get("headline", fallback["headline"])).strip(),
            "workout_recommendation": str(
                raw_plan.get("workout_recommendation", fallback["workout_recommendation"])
            ).strip(),
            "nutrition_focus": str(raw_plan.get("nutrition_focus", fallback["nutrition_focus"])).strip(),
            "mental_wellness_tip": str(
                raw_plan.get("mental_wellness_tip", fallback["mental_wellness_tip"])
            ).strip(),
            "journal_prompt": str(raw_plan.get("journal_prompt", fallback["journal_prompt"])).strip(),
            "supportive_message": str(
                raw_plan.get("supportive_message", fallback["supportive_message"])
            ).strip(),
        }
    )

    normalized["macro_targets"] = _normalize_macro_targets(
        raw_targets=raw_plan.get("macro_targets"),
        weight_kg=float(daily_data.get("weight_kg", 60)),
        steps=int(daily_data.get("steps", 0)),
        stress_level=int(daily_data.get("stress_level", 5)),
    )
    normalized["generated_with"] = "claude"
    normalized["generation_note"] = "Personalized with Claude Sonnet 4.6."
    return normalized


def generate_daily_plan(daily_data: dict[str, Any], api_key: str | None) -> dict[str, Any]:
    if not api_key:
        return _fallback_plan(daily_data)

    client = Anthropic(api_key=api_key)
    protein_target = int(round(float(daily_data.get("weight_kg", 60)) * 1.5))
    user_payload = {
        "task": "Create a personalized daily wellness plan for today.",
        "response_format": {
            "headline": "short motivating headline",
            "workout_recommendation": "1 paragraph",
            "nutrition_focus": "1 paragraph with Indian meal suggestions when useful",
            "macro_targets": {
                "carbs_g": "integer between 270 and 320",
                "protein_g": f"integer exactly {protein_target}",
                "fat_g": "integer between 45 and 55",
                "fiber_g": "integer between 25 and 35",
            },
            "mental_wellness_tip": "1 sentence",
            "journal_prompt": "1 sentence",
            "supportive_message": "1 to 2 warm sentences",
        },
        "rules": [
            "Return JSON only.",
            "Be warm, motivating, and personal, not clinical.",
            "Adapt tone to the mood score and recovery signals.",
            "If recovery looks low, emphasize recovery, nourishment, and gentle movement.",
            "If recovery looks strong, sound more energetic and performance-focused.",
            "Keep all macro targets inside the required bounds.",
        ],
        "daily_context": daily_data,
    }

    try:
        response = client.messages.create(
            model=MODEL_NAME,
            max_tokens=900,
            temperature=0.5,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": json.dumps(user_payload, indent=2),
                }
            ],
        )
        text_blocks = [
            block.text
            for block in response.content
            if getattr(block, "type", "") == "text" and getattr(block, "text", "")
        ]
        raw_text = "\n".join(text_blocks)
        raw_plan = _extract_json_block(raw_text)
        return _normalize_plan(raw_plan, daily_data)
    except Exception as error:
        plan = _fallback_plan(daily_data)
        plan["generation_note"] = (
            "Claude was unavailable just now, so smart local guidance is active instead."
        )
        plan["fallback_reason"] = error.__class__.__name__
        return plan


def _fallback_evening_message(daily_data: dict[str, Any], reflection: str) -> str:
    mood = int(daily_data.get("mood", 5))
    sleep_hours = float(daily_data.get("sleep_hours", 0))

    if mood <= 4 or sleep_hours < 6:
        return (
            "Thank you for checking in honestly tonight. It sounds like today asked a lot from you, "
            "so be generous with yourself. One lighter day does not erase your progress. A calm bedtime "
            "routine and a simple nourishing meal can help you reset for tomorrow."
        )

    if mood >= 7:
        return (
            "That is a lovely note to end the day on. You carried good energy today, and the real win is "
            "that you noticed it. Hold onto one thing that worked well and repeat it tomorrow."
        )

    return (
        "You showed up and paid attention to your day, and that matters. Keep tonight simple: hydrate, "
        "slow your pace a little, and let tomorrow start from a steadier place."
    )


def generate_evening_support(
    daily_data: dict[str, Any],
    daily_plan: dict[str, Any] | None,
    reflection: str,
    api_key: str | None,
) -> str:
    if not api_key:
        return _fallback_evening_message(daily_data, reflection)

    client = Anthropic(api_key=api_key)
    user_payload = {
        "task": "Respond to this evening reflection as a warm, supportive health companion.",
        "rules": [
            "Keep it under 120 words.",
            "Be kind, encouraging, and personal.",
            "Do not sound clinical or preachy.",
            "Reference the day context naturally.",
        ],
        "daily_context": daily_data,
        "planned_focus": daily_plan or {},
        "reflection": reflection,
    }

    try:
        response = client.messages.create(
            model=MODEL_NAME,
            max_tokens=220,
            temperature=0.7,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": json.dumps(user_payload, indent=2),
                }
            ],
        )
        text_blocks = [
            block.text
            for block in response.content
            if getattr(block, "type", "") == "text" and getattr(block, "text", "")
        ]
        message = "\n".join(text_blocks).strip()
        return message or _fallback_evening_message(daily_data, reflection)
    except Exception:
        return _fallback_evening_message(daily_data, reflection)
