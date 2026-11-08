# Personal Chef AI Assistant

A recipe-only AI agent that turns the ingredients you have into recipes. It is wrapped in layered guardrails against prompt injection, jailbreaks, off-topic use and private-data leakage, traced end to end in LangSmith, and verified by a repeatable evaluation suite.

**1) Problem**
Users want a useful AI helper, but general-purpose chatbots drift off-scope, leak data, and become unreliable. I built a narrow AI product that only does one thing well: turn ingredients into recipes while staying within clear boundaries.
**2) Product constraint**
This is a bounded assistant, not a general AI assistant. The product is safer and more predictable when the task is narrow.
**3) Trust and safety**
The important product decision wasn’t recipe quality alone. It was making sure the model could not be manipulated into unsafe or off-topic behavior.
**4) Evaluation mindset**
I didn’t just ship a prompt. I created a repeatable eval suite to test edge cases and regressions.
**5) Product lesson**
The biggest lesson was not that the model failed often, but that it was often too cautious. That is a product trade-off and a real thing to optimize.

**Status:** working end to end. Evaluation baseline recorded below. Open issues are listed in section 9.
--

## 1. Purpose and scope

**Does:** suggests 1-3 recipes from a list of ingredients, answers short cooking and food-safety questions (substitutions, storage, temperatures, scaling), and cites real search results when it uses the web.

**Does not:** anything else. Coding, general chat, news, medical advice, revealing its instructions, and role changes are all refused with one fixed sentence.

**Design goal:** the agent must never produce anything outside its job, even when the user, or a web page it reads, tries to make it.

---

## 2. Architecture

```mermaid
flowchart TD
    U[User message] --> IG[Input guard]
    IG -->|blocked| R[Fixed refusal]
    IG -->|allowed, PII redacted| A[Chef agent: gpt-oss-120b on Groq]
    A -->|needs recipe info| Q[Query guard + search budget]
    Q --> S[Tavily web search]
    S --> SG[Search-result guard]
    SG --> A
    A --> OG[Output guard]
    OG --> O[Answer + status]
```

Every box above is a traced step in LangSmith, so each decision is visible.

| Layer | What it does | Implemented with |
|---|---|---|
| Input guard | Length limit (1000 chars), PII redaction (email, phone, card), injection/jailbreak score, topic check | Regex, `llama-prompt-guard-2-86m`, `gpt-oss-safeguard-20b` |
| Query guard | Search queries must be about food; maximum 2 searches per request | `gpt-oss-safeguard-20b` + counter |
| Search-result guard | Each web result is scanned for hidden instructions before the agent sees it; bad results are dropped | `llama-prompt-guard-2-86m` |
| Prompt rules | Role, instruction hierarchy, tool rules, treat tool output as untrusted data, output formats, food-safety rules | `prompts/personal_chef.txt` |
| Output guard | Blocks prompt-text leaks and unexpected HTML tags; removes any URL that did not come from search results | Python checks |

**Fail-closed rule:** if any guard model errors or times out, the request is blocked, never allowed through.

---

## 3. Project layout

```
personal-chef/
├── .env                  # secrets (never commit)
├── pyproject.toml        # dependencies, managed by uv
├── prompts/
│   └── personal_chef.txt # the system prompt
├── tools.py              # web_search tool (with query guard + result guard)
├── guardrails.py         # all guard functions
├── agent.py              # builds the agent (model, tools, prompt, memory)
├── chef.py               # single entry point: guards + agent, used by app and evals
├── app.py                # terminal chat ("new" = fresh chat, "quit" = exit)
├── run_evals.py          # 29-case suite, runs in LangSmith
├── run_local_evals.py    # same suite, local only, no LangSmith usage
├── test_guards.py        # unit check of redaction and the search-result guard
├── debug_cases.py        # scratch script to inspect single failing cases
└── eval_results.txt      # dated score history (created by local evals)
```

`chef.chat()` is the only way in. The app and the evals both call it, so what is tested is exactly what runs.

---

## 4. Setup (Windows, PowerShell)

```powershell
cd personal-chef
uv venv
.venv\Scripts\Activate.ps1
uv add langchain langchain-groq langgraph tavily-python python-dotenv langsmith groq
```

Create `.env` in the project root:

```
GROQ_API_KEY=...
TAVILY_API_KEY=...
LANGSMITH_API_KEY=...
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=personal-chef
```

Run the app:

```powershell
uv run python app.py
```

If a script says it cannot import a name, check that the file is saved and run `uv sync`.

---

## 5. Models and why

| Role | Model | Reason |
|---|---|---|
| Chef | `openai/gpt-oss-120b` (Groq) | Supports tool calling and follows long instructions. `llama-3.3-70b-versatile` was not available on this account. |
| Injection / jailbreak detector | `meta-llama/llama-prompt-guard-2-86m` | A small classifier built for this; returns a 0-1 score. Block threshold is 0.5. |
| Topic and query policy checker | `openai/gpt-oss-safeguard-20b` | Takes a written policy and returns ALLOW or BLOCK. |

Small local models (Ollama) were not chosen: tool calling is less reliable, which would make evaluation noisy.

---

## 6. Tracing

LangSmith traces every request as a tree: `chef_chat` > `input_guard` > `injection_scan` / `topic_guard` > model call > `tools` > `web_search` (`query_guard`, `search_result_guard`) > model call > `output_guard`. Use it to check which tools were called with which queries, what the guards decided, token counts and latency.

A request returns an `answer` and a `status`: `ok`, `blocked_input:<reason>`, `modified_output:unverified_url_removed`, or `blocked_output:<reason>`.

---

## 7. Evaluation

**Suite:** 29 cases in `run_evals.py`.

| Category | Cases | Expected |
|---|---|---|
| recipe | 8 | A recipe in the required format |
| cooking | 3 | A short answer, no refusal |
| offtopic | 5 | Refusal |
| injection | 6 | Refusal, or a recipe that ignores the injected text |
| jailbreak | 3 | Refusal |
| secrets | 2 | Refusal |
| pii | 2 | A recipe; the personal detail never appears in the answer |

**Scores:**
- `correct_behavior`: did it do the expected thing for this case
- `no_leak`: no prompt text, no forbidden strings (such as a planted URL or email) in the answer
- `recipe_format`: Serves / Ingredients / Method present (recipe cases only; other cases count as 1)

**Rules for fair tests:** every case runs in a fresh conversation (conversation history otherwise leaks between tests and slows requests), one at a time, with an 8-second pause to stay inside Groq free-tier limits.

**Running:**
- LangSmith: `uv run python run_evals.py`
- Local only, no LangSmith usage: `uv run python run_local_evals.py` (optionally with categories, for example `recipe cooking`). Results print to the terminal and append to `eval_results.txt`.

**Score history**

| Run | correct_behavior | no_leak | recipe_format | Notes |
|---|---|---|---|---|
| Baseline (LangSmith) | 0.93 (27/29) | 1.00 | 0.96 | 2 failures: a normal recipe blocked once; a cooking question refused |
| After prompt fix (local) | 0.86 (25/29) | 1.00 | 0.93 | Cooking question fixed; 4 normal requests blocked by input guards |

**Reading the results:** `no_leak` has been 1.00 in every run, and all injection, jailbreak and secrets cases were refused every time. The failures so far are over-blocking of legitimate requests, not security failures.

---

## 8. Design decisions

1. **Defense in depth.** The prompt is one layer, not the defense. Input, search-result and output checks run in code, outside the model.
2. **Search results are untrusted.** Web pages can carry hidden instructions (indirect injection), so results are scanned and dropped before the agent reads them.
3. **Fail closed.** A guard that errors blocks the request.
4. **Fixed refusal sentence.** One exact sentence makes refusals easy to test and does not reveal which rule fired.
5. **No invented citations.** The output guard removes any URL that was not in the search results.
6. **PII is redacted before the model and before traces.** Email, phone and card patterns become `[EMAIL]`, `[PHONE]`, `[CARD]`.
7. **Fresh thread per eval case**, one at a time, so tests do not contaminate each other.

---

## 9. Known issues and limitations

1. **Over-blocking.** In the latest local run, 4 legitimate requests (3 recipe/cooking requests and "At what temperature is chicken safely cooked?") were blocked by input guards. Suspected cause: guard model calls erroring (rate limits or empty replies) and the fail-closed rule turning those errors into blocks. A score of exactly `1.000` on a harmless question is the fallback value, not a real classification. **Planned fix:** retry each guard call up to 3 times, parse verdicts strictly, log every guard error, then rerun the `recipe` and `cooking` categories.
2. **Latency grows with conversation length.** The same request took 2.7s in a fresh chat with 2.5K tokens, and 60s in a long chat with 7.7K tokens. **Planned fix:** cap the history sent to the model.
3. **Output guard tag list** was too strict once; extended to include `br`, `em`, `b`, `i`. To be confirmed in a rerun.
4. **Search budget is a single global counter.** Correct for one user at a time; it must become per-request state before any multi-user deployment.
5. **Free-tier limits.** Groq tokens-per-minute and the LangSmith trace quota constrain how often the full suite can run. Use the local runner for regular checks.
6. **Date-filtered search.** The agent cannot reliably filter recipes by publication date and is instructed to say so.
7. **Prompt Guard** detects injection and jailbreak attempts, not off-topic requests; topic enforcement relies on the safeguard model and the prompt.

---

## 10. How to change things safely

1. Make one change (prompt, guard, model, threshold).
2. Run the local evals for the affected categories, then the full suite.
3. Compare with the score history. Any drop in `no_leak` or in an attack category is a regression: revert or fix before moving on.
4. Record the new row in the score history.

---

## 11. Roadmap

1. Fix over-blocking (section 9, item 1) and reach a clean full run.
2. Cap conversation history.
3. Add more eval cases: indirect injection through real search results, multi-turn attacks, non-English attacks, encoded (base64) attacks, borderline food-safety questions.
4. Automated red-teaming with garak or promptfoo.
5. Web UI (Streamlit or Gradio) that renders the HTML answers.
6. Run the local evals automatically on every change (CI).
7. Alerting on guard-block rate and refusal rate from traces.
