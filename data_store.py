import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any


DB_PATH = Path(__file__).resolve().parent / "wellness_companion.db"

DEFAULT_SETTINGS = {
    "user_weight_kg": "60",
    "anthropic_api_key": "",
}


def _get_connection(db_path: str | Path = DB_PATH) -> sqlite3.Connection:
    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    return connection


def init_db(db_path: str | Path = DB_PATH) -> None:
    with _get_connection(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS daily_metrics (
                log_date TEXT PRIMARY KEY,
                sleep_hours REAL NOT NULL,
                hrv REAL,
                resting_hr REAL,
                steps INTEGER NOT NULL,
                stress_level INTEGER NOT NULL,
                mood INTEGER NOT NULL,
                weight REAL NOT NULL,
                energy_score INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS daily_plans (
                log_date TEXT PRIMARY KEY,
                plan_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS food_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                log_date TEXT NOT NULL,
                meal_type TEXT NOT NULL,
                food_name TEXT NOT NULL,
                servings REAL NOT NULL,
                carbs REAL NOT NULL,
                protein REAL NOT NULL,
                fat REAL NOT NULL,
                fiber REAL NOT NULL,
                calories REAL NOT NULL,
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS evening_checkins (
                log_date TEXT PRIMARY KEY,
                reflection TEXT NOT NULL,
                ai_response TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )

        for key, value in DEFAULT_SETTINGS.items():
            connection.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )


def compute_energy_score(
    sleep_hours: float,
    steps: int,
    stress_level: int,
    mood: int,
) -> int:
    sleep_component = min(max(sleep_hours / 8.0, 0.0), 1.0) * 35
    steps_component = min(max(steps / 10000.0, 0.0), 1.0) * 20
    stress_component = min(max((11 - stress_level) / 10.0, 0.0), 1.0) * 20
    mood_component = min(max(mood / 10.0, 0.0), 1.0) * 25
    return int(round(sleep_component + steps_component + stress_component + mood_component))


def upsert_daily_metrics(
    log_date: str,
    sleep_hours: float,
    hrv: float | None,
    resting_hr: float | None,
    steps: int,
    stress_level: int,
    mood: int,
    weight: float,
    db_path: str | Path = DB_PATH,
) -> dict[str, Any]:
    energy_score = compute_energy_score(
        sleep_hours=sleep_hours,
        steps=steps,
        stress_level=stress_level,
        mood=mood,
    )

    with _get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO daily_metrics (
                log_date, sleep_hours, hrv, resting_hr, steps, stress_level, mood, weight, energy_score
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(log_date) DO UPDATE SET
                sleep_hours = excluded.sleep_hours,
                hrv = excluded.hrv,
                resting_hr = excluded.resting_hr,
                steps = excluded.steps,
                stress_level = excluded.stress_level,
                mood = excluded.mood,
                weight = excluded.weight,
                energy_score = excluded.energy_score,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                log_date,
                sleep_hours,
                hrv,
                resting_hr,
                steps,
                stress_level,
                mood,
                weight,
                energy_score,
            ),
        )

    return get_daily_metrics(log_date, db_path) or {}


def get_daily_metrics(log_date: str, db_path: str | Path = DB_PATH) -> dict[str, Any] | None:
    with _get_connection(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM daily_metrics WHERE log_date = ?",
            (log_date,),
        ).fetchone()

    return dict(row) if row else None


def get_recent_metrics(days: int = 7, db_path: str | Path = DB_PATH) -> list[dict[str, Any]]:
    start_date = (date.today() - timedelta(days=days - 1)).isoformat()
    with _get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM daily_metrics
            WHERE log_date >= ?
            ORDER BY log_date ASC
            """,
            (start_date,),
        ).fetchall()

    return [dict(row) for row in rows]


def save_daily_plan(log_date: str, plan: dict[str, Any], db_path: str | Path = DB_PATH) -> None:
    serialized_plan = json.dumps(plan)
    with _get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO daily_plans (log_date, plan_json)
            VALUES (?, ?)
            ON CONFLICT(log_date) DO UPDATE SET
                plan_json = excluded.plan_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (log_date, serialized_plan),
        )


def get_daily_plan(log_date: str, db_path: str | Path = DB_PATH) -> dict[str, Any] | None:
    with _get_connection(db_path) as connection:
        row = connection.execute(
            "SELECT plan_json FROM daily_plans WHERE log_date = ?",
            (log_date,),
        ).fetchone()

    return json.loads(row["plan_json"]) if row else None


def add_food_log(
    log_date: str,
    meal_type: str,
    food_name: str,
    servings: float,
    macros: dict[str, float],
    notes: str = "",
    db_path: str | Path = DB_PATH,
) -> None:
    with _get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO food_logs (
                log_date, meal_type, food_name, servings, carbs, protein, fat, fiber, calories, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                log_date,
                meal_type,
                food_name,
                servings,
                macros["carbs"],
                macros["protein"],
                macros["fat"],
                macros["fiber"],
                macros["calories"],
                notes,
            ),
        )


def get_food_logs(log_date: str, db_path: str | Path = DB_PATH) -> list[dict[str, Any]]:
    with _get_connection(db_path) as connection:
        rows = connection.execute(
            """
            SELECT id, meal_type, food_name, servings, carbs, protein, fat, fiber, calories, notes, created_at
            FROM food_logs
            WHERE log_date = ?
            ORDER BY created_at ASC, id ASC
            """,
            (log_date,),
        ).fetchall()

    return [dict(row) for row in rows]


def get_food_totals(log_date: str, db_path: str | Path = DB_PATH) -> dict[str, float]:
    with _get_connection(db_path) as connection:
        row = connection.execute(
            """
            SELECT
                COALESCE(SUM(carbs), 0) AS carbs,
                COALESCE(SUM(protein), 0) AS protein,
                COALESCE(SUM(fat), 0) AS fat,
                COALESCE(SUM(fiber), 0) AS fiber,
                COALESCE(SUM(calories), 0) AS calories
            FROM food_logs
            WHERE log_date = ?
            """,
            (log_date,),
        ).fetchone()

    return {key: round(float(row[key]), 1) for key in row.keys()}


def save_evening_checkin(
    log_date: str,
    reflection: str,
    ai_response: str,
    db_path: str | Path = DB_PATH,
) -> None:
    with _get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO evening_checkins (log_date, reflection, ai_response)
            VALUES (?, ?, ?)
            ON CONFLICT(log_date) DO UPDATE SET
                reflection = excluded.reflection,
                ai_response = excluded.ai_response,
                updated_at = CURRENT_TIMESTAMP
            """,
            (log_date, reflection, ai_response),
        )


def get_evening_checkin(log_date: str, db_path: str | Path = DB_PATH) -> dict[str, Any] | None:
    with _get_connection(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM evening_checkins WHERE log_date = ?",
            (log_date,),
        ).fetchone()

    return dict(row) if row else None


def get_settings(db_path: str | Path = DB_PATH) -> dict[str, Any]:
    settings: dict[str, Any] = DEFAULT_SETTINGS.copy()
    with _get_connection(db_path) as connection:
        rows = connection.execute("SELECT key, value FROM settings").fetchall()

    for row in rows:
        settings[row["key"]] = row["value"]

    settings["user_weight_kg"] = float(settings.get("user_weight_kg", 60) or 60)
    return settings


def update_settings(
    user_weight_kg: float,
    anthropic_api_key: str,
    db_path: str | Path = DB_PATH,
) -> dict[str, Any]:
    with _get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            ("user_weight_kg", str(user_weight_kg)),
        )
        connection.execute(
            """
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            ("anthropic_api_key", anthropic_api_key.strip()),
        )

    return get_settings(db_path)
