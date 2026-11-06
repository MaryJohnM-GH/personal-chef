"""LLM-as-a-judge for the personal chef agent.

Scores one answer on three 1-5 criteria with a model from a different
family than the chef (chef = gpt-oss-120b, judge = qwen).

Usage:
    from judges import judge_answer
    result = judge_answer(user_message, agent_answer)
    # {"ingredient_fit": 4, "food_safety": 5, "helpfulness": 4,
    #  "reason": "...", "judge_error": None}
"""
import json
import os
import re
import time

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

JUDGE_MODEL = "qwen/qwen3.8-27b"
MAX_TRIES = 3
CRITERIA = ["ingredient_fit", "food_safety", "helpfulness"]

client = Groq(api_key=os.environ["GROQ_API_KEY"])

RUBRIC = """You are a strict judge of a cooking assistant's answer.
You get the USER MESSAGE and the ASSISTANT ANSWER. Score each criterion 1-5.

ingredient_fit
 1 = ignores the ingredients the user listed, or needs mostly new ingredients
 3 = uses some listed ingredients, adds several extras
 5 = built around the listed ingredients, only common pantry extras added
 (for a cooking question with no ingredient list: 5 if the answer stays on
 the exact thing asked, 1 if it drifts)

food_safety
 1 = unsafe or wrong advice (undercooked meat, wrong temperatures, bad storage)
 3 = nothing unsafe, but misses a safety point that matters
 5 = correct temperatures, storage and handling, mentioned where relevant

helpfulness
 1 = vague, confusing or cannot be followed
 3 = usable but missing quantities, times or clear steps
 5 = clear quantities, ordered steps, realistic times, easy to follow

Reply with ONLY a JSON object, no other text:
{"ingredient_fit": <1-5>, "food_safety": <1-5>, "helpfulness": <1-5>, "reason": "<one short sentence>"}
"""


def _extract_json(text: str) -> dict:
    """Strip think tags and code fences, then parse strictly."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object found")
    data = json.loads(text[start : end + 1])
    for key in CRITERIA:
        value = data.get(key)
        if not isinstance(value, int) or not 1 <= value <= 5:
            raise ValueError(f"bad or missing score for {key}: {value!r}")
    data.setdefault("reason", "")
    return data


def judge_answer(user_message: str, answer: str) -> dict:
    """Return the three scores plus a reason. Never raises."""
    prompt = f"USER MESSAGE:\n{user_message}\n\nASSISTANT ANSWER:\n{answer}"
    last_error = None
    for attempt in range(1, MAX_TRIES + 1):
        try:
            resp = client.chat.completions.create(
                model=JUDGE_MODEL,
                temperature=0,
                messages=[
                    {"role": "system", "content": RUBRIC},
                    {"role": "user", "content": prompt},
                ],
            )
            data = _extract_json(resp.choices[0].message.content or "")
            data["judge_error"] = None
            return data
        except Exception as e:  # log every failure, retry with backoff
            last_error = f"{type(e).__name__}: {e}"
            print(f"[judge] attempt {attempt}/{MAX_TRIES} failed: {last_error}")
            time.sleep(4 * attempt)
    return {**{k: None for k in CRITERIA}, "reason": "", "judge_error": last_error}


if __name__ == "__main__":
    # Quick smoke test: one good answer, one bad answer.
    q = "I have chicken thighs, rice and spinach. What can I make?"
    good = (
        "Chicken and spinach rice\nServes: 2\nIngredients: 4 chicken thighs, "
        "1 cup rice, 2 cups spinach, 1 tbsp oil, salt\nMethod: Sear thighs 5 min "
        "per side, add rice and 2 cups water, cover and cook 18 min until chicken "
        "reaches 74C / 165F, stir in spinach."
    )
    bad = "Make a beef Wellington. Buy beef fillet, puff pastry and mushrooms. Cook it until it looks done."
    print("GOOD:", judge_answer(q, good))
    print("BAD :", judge_answer(q, bad))