# Lumiq AI Health & Wellness Companion

Lumiq is a Streamlit-based AI health and wellness companion built for an India-first daily coaching experience. It combines simple daily recovery inputs, a local Indian food macro log, weekly trend charts, and a warm Claude-powered planning flow.

## What it does

- Creates a personalized daily plan from sleep, HRV or resting heart rate, steps, stress, mood, and weight
- Recommends a workout focus, daily macro targets, nutrition guidance, and a mental wellness prompt
- Tracks food intake with common Indian foods such as roti, rice, dal, sabzi, paneer, dosa, idli, poha, upma, curd, and chai
- Compares logged macros against the day's recommended targets
- Shows last 7 days of sleep, mood, and energy trends with Plotly charts
- Supports an evening reflection flow with a caring AI response
- Stores data locally in SQLite so the app works across sessions without login

## Project structure

- `app.py` - Streamlit app and UI flow
- `ai_engine.py` - Claude prompt construction, response handling, and fallback guidance
- `food_db.py` - Common Indian food macro database and food helpers
- `data_store.py` - SQLite persistence for daily logs, plans, meals, and settings

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Add your Anthropic API key in one of these ways:

- Set an environment variable:

```bash
export ANTHROPIC_API_KEY="your_key_here"
```

- Or leave it blank and add the key inside the app's Settings page.

4. Run the app:

```bash
streamlit run app.py
```

5. Open the local Streamlit URL in your browser.

## Notes

- Default weight starts at 60 kg and can be changed in Settings.
- If no Anthropic key is available, Lumiq still generates a smart local fallback plan so the experience remains usable.
- Local data is stored in `wellness_companion.db`.
