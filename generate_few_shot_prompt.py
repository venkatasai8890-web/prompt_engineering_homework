"""
Generate a few-shot prompt for predicting median_house_value
using the California Housing training data.

This script:
1. Loads california_housing_train.csv.
2. Randomly samples exactly 65 rows (fixed seed = 42) as few-shot examples.
3. Formats each sampled row as a "features -> target" example.
4. Builds a final prompt template with a placeholder for a new,
   user-provided housing record to predict.

No external API (e.g. Gemini) is called here — this script only
builds the text prompt that would later be sent to a model.

Only Python's standard library is used (csv, random) so the script
runs without any extra dependencies (e.g. pandas).
"""

import csv
import random

CSV_PATH = "california_housing_train.csv"
RANDOM_SEED = 42
NUM_SAMPLES = 65

FEATURE_COLUMNS = [
    "longitude",
    "latitude",
    "housing_median_age",
    "total_rooms",
    "total_bedrooms",
    "population",
    "households",
    "median_income",
]
TARGET_COLUMN = "median_house_value"


def load_data(csv_path: str) -> list:
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def sample_rows(rows: list, n: int, seed: int) -> list:
    rng = random.Random(seed)
    return rng.sample(rows, n)


def format_example(row: dict) -> str:
    feature_lines = "\n".join(
        f"  {col}: {row[col]}" for col in FEATURE_COLUMNS
    )
    return (
        "Input:\n"
        f"{feature_lines}\n"
        f"Output:\n  median_house_value: {row[TARGET_COLUMN]}"
    )


def build_few_shot_examples(sample_rows_: list) -> str:
    examples = [format_example(row) for row in sample_rows_]
    return "\n\n".join(examples)


def build_prompt_template(few_shot_examples: str) -> str:
    return f"""You are a real estate pricing assistant. You will be shown several
examples of California housing records (features) together with their
actual median house value. Study the pattern between the features and
the price, then predict the median_house_value for a new record.

Each record describes a block of houses in California with these features:
- longitude: geographic longitude of the block
- latitude: geographic latitude of the block
- housing_median_age: median age of the houses in the block (years)
- total_rooms: total number of rooms in the block
- total_bedrooms: total number of bedrooms in the block
- population: total population living in the block
- households: total number of households in the block
- median_income: median household income in the block (tens of thousands of USD)

Here are {NUM_SAMPLES} examples:

{few_shot_examples}

Now predict the median_house_value for the following new record.
Respond with only the predicted numeric value.

Input:
  longitude: {{longitude}}
  latitude: {{latitude}}
  housing_median_age: {{housing_median_age}}
  total_rooms: {{total_rooms}}
  total_bedrooms: {{total_bedrooms}}
  population: {{population}}
  households: {{households}}
  median_income: {{median_income}}
Output:
  median_house_value:"""


def main():
    rows = load_data(CSV_PATH)
    sampled = sample_rows(rows, NUM_SAMPLES, RANDOM_SEED)

    few_shot_examples = build_few_shot_examples(sampled)
    prompt_template = build_prompt_template(few_shot_examples)

    print(prompt_template)


if __name__ == "__main__":
    main()
