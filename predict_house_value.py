"""
Predict median_house_value for a new California housing record using
the Gemini API, few-shot prompted with the same 65 sampled examples
(seed=42) built in generate_few_shot_prompt.py.

Usage:
    python3 predict_house_value.py

You will be prompted to enter the 8 housing features for a new record.
The script builds the few-shot prompt, inserts your record as the final
query, sends it to Gemini, and prints the predicted median_house_value.

Configuration:
    Create a .env.local file (see .env.local.example) containing:
        GOOGLE_GENAI_API_KEY=your_real_key_here

    Optional, also in .env.local or as an environment variable:
        GEMINI_MODEL=gemini-3.6-flash   (default shown)

The API key is read from .env.local only — it is never hardcoded or
printed anywhere in this script.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request

from generate_few_shot_prompt import (
    CSV_PATH,
    FEATURE_COLUMNS,
    NUM_SAMPLES,
    RANDOM_SEED,
    build_few_shot_examples,
    build_prompt_template,
    load_data,
    sample_rows,
)

ENV_FILE = ".env.local"
API_KEY_VAR = "GOOGLE_GENAI_API_KEY"
MODEL_VAR = "GEMINI_MODEL"
DEFAULT_MODEL = "gemini-3.6-flash"
API_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)


def load_env_file(path: str) -> dict:
    """Very small .env parser: KEY=VALUE per line, '#' comments allowed."""
    env = {}
    if not os.path.exists(path):
        return env
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def get_config() -> tuple:
    env = load_env_file(ENV_FILE)
    api_key = env.get(API_KEY_VAR) or os.environ.get(API_KEY_VAR)
    if not api_key:
        raise RuntimeError(
            f"{API_KEY_VAR} not found.\n"
            f"Create a '{ENV_FILE}' file (see .env.local.example) containing:\n"
            f"  {API_KEY_VAR}=your_real_key_here"
        )
    model = env.get(MODEL_VAR) or os.environ.get(MODEL_VAR) or DEFAULT_MODEL
    return api_key, model


def prompt_for_features() -> dict:
    print("Enter the 8 housing features for the new record:")
    values = {}
    for col in FEATURE_COLUMNS:
        while True:
            raw = input(f"  {col}: ").strip()
            try:
                values[col] = float(raw)
                break
            except ValueError:
                print(f"    Please enter a numeric value for {col}.")
    return values


def build_final_prompt(user_values: dict) -> str:
    rows = load_data(CSV_PATH)
    sampled = sample_rows(rows, NUM_SAMPLES, RANDOM_SEED)
    few_shot_examples = build_few_shot_examples(sampled)
    template = build_prompt_template(few_shot_examples)
    return template.format(**user_values)


def call_gemini(prompt: str, api_key: str, model: str) -> str:
    url = API_URL_TEMPLATE.format(model=model)
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.0},
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Gemini API request failed ({e.code} {e.reason}): {error_body}"
        ) from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"Could not reach Gemini API: {e.reason}") from None

    try:
        candidates = body["candidates"]
        parts = candidates[0]["content"]["parts"]
        text = "".join(part.get("text", "") for part in parts)
    except (KeyError, IndexError, TypeError):
        raise RuntimeError(f"Unexpected Gemini response format: {body}") from None

    return text.strip()


def extract_number(text: str):
    match = re.search(r"-?\d[\d,]*\.?\d*", text)
    if not match:
        return None
    return float(match.group(0).replace(",", ""))


def main():
    try:
        api_key, model = get_config()
    except RuntimeError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)

    user_values = prompt_for_features()
    prompt = build_final_prompt(user_values)

    try:
        prediction_text = call_gemini(prompt, api_key, model)
    except RuntimeError as e:
        print(f"Prediction failed: {e}", file=sys.stderr)
        sys.exit(1)

    predicted_value = extract_number(prediction_text)

    print()
    print("Gemini raw response:")
    print(f"  {prediction_text}")
    if predicted_value is not None:
        print()
        print(f"Predicted median_house_value: {predicted_value:,.2f}")
    else:
        print("Could not parse a numeric prediction from the response.")


if __name__ == "__main__":
    main()
