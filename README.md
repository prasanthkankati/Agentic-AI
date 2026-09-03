# Agentic AI — Automated UI Test Generation from an SRS

Reads a Software Requirements Specification, crawls the live application it
describes, and writes a runnable Playwright test suite — then validates its own
output and repairs what failed, without a human in the loop.

Built against **The Internet** (`https://the-internet.herokuapp.com`), a public
demo site with 70 documented functional requirements.

---

## 1. What it produces

| Output | What it is |
|---|---|
| `test_generated_<runid>.py` | The Playwright + pytest suite, one test per requirement |
| `full_log_<runid>.json` | Complete machine-readable state of the run |
| `execution_log_<runid>.txt` | Human-readable trail of what each agent did |
| pytest output | Pass/fail of the generated suite against the live site |

---

## 2. Tech stack

| Layer | Technology | Why |
|---|---|---|
| Orchestration | **LangGraph** | Models the pipeline as a graph with a conditional loop-back edge, which is what makes it agentic rather than a linear script |
| LLM | **Google Gemini** via `langchain-google-genai` | Fast, generous free tier; model is auto-detected at runtime |
| Browser automation | **Playwright (Python)** | Auto-waiting removes most timing flakiness; `get_by_role` / `get_by_label` give semantic, redesign-resistant locators |
| Test framework | **pytest** + `pytest-playwright` | Industry standard; the generated suite is ordinary pytest |
| Document parsing | **PyMuPDF** (`fitz`) | Reads both `.pdf` and `.docx` |
| Validation | **Python `ast` + `re`** | Deliberately *not* an LLM — see section 6 |
| Runtime | **Google Colab** | No local install; Playwright headless works out of the box |

---

## 3. Architecture

```
   SRS (.docx / .pdf)
           |
           v
   +---------------+
   |  Extractor    |  LLM  -> requirements as JSON, real SRS IDs preserved
   +---------------+
           |
           v
   +---------------+
   |  Crawler      |  Playwright (no LLM) -> real locators, ~24 pages
   +---------------+
           |
           v
   +---------------+
   |  Developer    |  LLM  -> pytest suite, generated in batches of 10
   +---------------+
           |
           v
   +---------------+
   |  Reviewer     |  Pure Python -> PASSED / FAILED + specific fixes
   +---------------+
           |
      passed? --- yes --> save outputs --> run pytest
           |
           no  --> back to Developer (max 4 attempts)
```

Every agent reads from and writes to one shared `AgentState` dictionary. The
`history` field is declared `Annotated[List[dict], operator.add]`, so each agent
*appends* rather than overwrites — that is what produces the audit log.

---

## 4. How to run

### Prerequisites
- A Google account
- A Gemini API key from <https://aistudio.google.com/apikey> (free tier is enough)
- The SRS file (`Capstone requirements document.docx`)

### Steps

1. Open `agentic_ai_capstone_colab.ipynb` in Google Colab.
2. Click the **key icon** in the left sidebar (Secrets).
   Add a secret named exactly `GOOGLE_API_KEY`, paste your key, and turn on
   **Notebook access**.
3. **Runtime → Run all.**
4. When the upload cell appears, choose your SRS file.
5. Watch the **preflight** cell. Do not continue if it does not print
   `ALL CHECKS PASSED`.

Total runtime: roughly 6–10 minutes, most of it the site crawl.

---

## 5. Demo walkthrough — what you will see

### Stage 0 — Preflight (~30 s)
```
PREFLIGHT
----------------------------------------------
1. API key           : found (39 chars)
2. Models available  : 47
   Selected          : gemini-2.0-flash
3. LLM smoke test    : READY
4. SRS document      : 43650 chars, 70 requirement IDs
5. Playwright        : Version 1.4x.x
6. Target site       : HTTP 200
----------------------------------------------
ALL CHECKS PASSED - safe to run
```
Everything that could fail later is checked here first, cheaply.

### Stage 1 — Extractor (~30 s)
```
--- [Extractor] Reading SRS ---
    document length: 43650 chars
    extracted 70 requirements
    SRS contains 70 functional requirement IDs
    full SRS coverage
```
Requirement IDs are kept **exactly as written in the SRS** (`FR-FA-02`, not
`FR-001`), so every test traces back to its requirement.

### Stage 2 — Crawler (~3–5 min)
```
--- [Crawler] Scanning https://the-internet.herokuapp.com ---
[1] Crawling https://the-internet.herokuapp.com
    found 24 sub-pages to visit
[2] /abtest
[3] /add_remove_elements/
...
DONE: 312 elements across 24 pages
```
No LLM here. A real browser visits each page and records what is genuinely
present, so the Developer works from facts rather than guesses.

### Stage 3 — Developer (~1–2 min)
```
--- [Developer] attempt 1 ---
    batch 1: 10 requirements ok
    batch 2: 10 requirements ok
    ...
    suite is now 21400 chars
```
Batches of 10. A single request for 70 tests would exceed the response limit
and get truncated mid-function.

### Stage 4 — Reviewer (instant)
```
--- [Reviewer] Validating ---
    tests: 70
    syntax: OK
    uncovered requirements: 2
    tests missing assertions: 1
    hardcoded URLs: 0
    RESULT: FAILED
Sending failures back to the Developer.
```
Then the Developer repairs only the named tests and the Reviewer re-checks.
Typically converges in 2–3 attempts.

### Stage 5 — pytest
```
55 passed, 15 failed in 92.31s
```
**Failures here are expected and are a finding, not a bug.** Some are genuine
site behaviour the generated assertion got wrong; some are requirements that
cannot be asserted deterministically. Report the pass rate honestly — it is a
real measurement, and a plausible number is more credible than a perfect one.

---

## 6. Design decisions worth defending

**The Reviewer is Python, not an LLM.**
Checking syntax, counting tests, and confirming coverage are exact questions.
Python answers them exactly and instantly. An earlier LLM reviewer *guessed* —
reporting hardcoded URLs in code that had none and rejecting 50 valid locators
— so the loop could never terminate. **Use an LLM for judgement; use code for
facts.**

**The Developer repairs instead of regenerating.**
Regenerating the whole suite each round made fixing the last requirements break
the earlier ones; output oscillated between 8,437 and 2,474 characters and never
settled. Repair mode edits only the named failing tests.

**The Crawler visits sub-pages, not just the landing page.**
Requirements reference `/login`, `/upload`, `/tables`. Crawling only the home
page yielded 45 navigation links and nothing else, so every sub-page test had
to invent its locators.

**The model name is discovered at runtime.**
Hardcoded model names get retired and fail on the first call. The preflight
asks the API which models exist and picks a suitable one.

---

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `SecretNotFoundError` | Secret missing or notebook access off | Re-add `GOOGLE_API_KEY` and enable notebook access |
| Preflight step 2 fails | Invalid or unactivated key | Regenerate at aistudio.google.com/apikey |
| `429 ResourceExhausted` | Free-tier rate limit | Wait 60 s and re-run the failed cell; raise `BATCH_SIZE` to cut call count |
| Crawler returns 0 elements | Browser not installed | Re-run the install cell, then Runtime → Restart |
| `asyncio.run() cannot be called...` | Crawler run inline | The crawler must run via `ui_runner.py` as a subprocess |
| Extractor returns 0 requirements | Model wrapped JSON in prose | Re-run the cell; the parser slices between the first `[` and last `]` |
| Suite fails after 4 attempts | Loop hit `MAX_ATTEMPTS` | Read the report in the log; usually a couple of uncovered requirements |

---

## 8. Limitations

1. Only public, unauthenticated pages are crawled — no multi-step flows behind a login.
2. Non-functional requirements (`NFR-P-01` performance, `NFR-UX-01` visual appeal) cannot be verified by UI automation and are out of scope.
3. Randomised behaviours described in SRS section 5.1 cannot be asserted deterministically.
4. LLM output varies between runs even at `temperature=0.1`; two runs may differ.
5. The repair loop caps at 4 attempts and does not guarantee a pass.
6. Crawl depth is 1 — sub-pages of sub-pages are not visited.

---

## 9. Repository layout

```
.
├── agentic_ai_capstone_colab.ipynb   # the whole pipeline, run this
├── ui_crawler.py                     # written to disk by the notebook
├── ui_runner.py                      # subprocess entry point for the crawler
├── PROJECT_EXPLAINED.md              # plain-English guide to how it works
├── README.md                         # this file
├── pdf/
│   └── Capstone requirements document.docx
└── agent_outputs/                    # generated per run
```

> **Security note:** never commit `.env` or an API key. Add `.env` to
> `.gitignore`. If a key has ever been shared or zipped, rotate it.
