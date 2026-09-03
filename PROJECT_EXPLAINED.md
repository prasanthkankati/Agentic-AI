# Agentic AI for Automated UI Test Generation
### A plain-English guide to what this project does and how

---

## 1. The one-sentence version

**This project reads a requirements document, looks at a live website, and
writes a working automated test suite by itself — then checks its own work and
fixes its own mistakes.**

If you only remember one sentence, remember that one.

---

## 2. The problem it solves

Today, a QA engineer does this by hand:

1. Read the requirements document (35 pages).
2. Open the website and find each button, field, and link.
3. Write a test script for every requirement.
4. Run it, find the broken bits, fix them, repeat.

For 70 requirements, that is days of work. And when the website changes, much
of it must be redone.

This project automates all four steps. The human's job shifts from *writing*
tests to *reviewing* them.

---

## 3. The four agents

An "agent" here just means: an LLM given one specific job, one clear prompt,
and one clear output. Four small specialists, not one big do-everything prompt.

| Agent | Reads | Produces |
|---|---|---|
| **Extractor** | The SRS document | A list of testable requirements as JSON |
| **Crawler** | The live website | Real locators for the real elements |
| **Developer** | Requirements + locators | A Playwright pytest test suite |
| **Reviewer** | The generated suite | Pass/fail plus a list of what to fix |

**The useful analogy:** it is a small QA team. A business analyst reads the
spec. A site surveyor maps the building. A developer writes the code. A
reviewer checks it and sends it back with comments. The reviewer's comments go
back to the developer, and round it goes until the work is accepted.

> The Crawler is the only one that is **not** an LLM. It is ordinary Python
> driving a real browser. If an examiner asks "where does the AI actually sit?",
> the answer is: Extractor, Developer, Reviewer are LLM calls; the Crawler is
> deterministic automation.

---

## 4. How the data flows

```
  SRS document (.docx)
          |
          v
   [ Extractor ]  --> 70 requirements, each with an ID like FR-FA-02
          |
          v
   [ Crawler ]    --> ~300 locators across ~24 pages of the live site
          |
          v
   [ Developer ]  --> test_generated.py  (one test per requirement)
          |
          v
   [ Reviewer ]   --> PASSED?  --> yes --> save the file, done
          |                 |
          |                 no
          |                 |
          +<-- feedback -----+     (loop, up to 4 attempts)
```

Every agent writes its result into one shared dictionary called **state**. The
next agent reads from that same dictionary. That is the whole mechanism — there
is no magic.

---

## 5. The five ideas you should be able to explain

### 5.1 What LangGraph is doing

LangGraph is a library for connecting steps into a **graph** — boxes with
arrows. Most of our arrows are straight lines (Extractor → Crawler →
Developer). One arrow is a **conditional edge**: after the Reviewer, the graph
asks a small function called the `router` whether to finish or to loop back to
the Developer.

That loop-back arrow is the entire reason this is called "agentic" rather than
just "a script that calls an LLM four times". The system decides its own next
step based on its own output.

### 5.2 Why state is "annotated"

```python
history: Annotated[List[dict], operator.add]
```

Normally, when a step writes to state, it *overwrites* what was there. That
`operator.add` tells LangGraph to **append instead of overwrite**, so `history`
collects every agent's report across every loop. That is what produces the
audit log at the end — proof of what the system did and when.

### 5.3 Why the Crawler matters so much

An LLM asked to write a Playwright test will happily invent a locator like
`page.locator("#login-button")` — a plausible guess that may not exist. The
test then fails for a silly reason.

So before the Developer writes anything, we visit the real site and record what
is genuinely there. Feeding real locators into the prompt is what keeps the
generated tests grounded in reality instead of in the model's imagination.

**Locator strategy, in priority order:** role → label → placeholder → test-id →
text → attribute → position. Role and label come first because they survive a
redesign; position (`.nth(3)`) comes last because it breaks the moment anyone
adds a row.

### 5.4 Why the Reviewer is Python, not an LLM

This is the strongest design decision in the project, and the one most worth
explaining.

The Reviewer's job is checking facts: does the file parse, are there 30+ tests,
does every requirement have one, does every test assert something. Those are
**exact** questions. Python answers them exactly, in milliseconds, for free.

An LLM asked the same questions *guesses*, and it guessed wrong — in the
earlier version it reported "hardcoded URLs: YES" about code that had none, and
flagged 50 perfectly valid locators as forbidden. Because the LLM reviewer kept
inventing failures, the loop could never finish.

**The principle: use an LLM for judgement, use code for facts.** Writing a test
is judgement. Counting tests is a fact.

### 5.5 Why repair mode beats regeneration

When the Reviewer rejects the suite, the Developer is shown its own previous
file plus the specific complaints, and told to change *only* those parts.

The earlier version regenerated everything from scratch each round. The output
oscillated — 8437 characters, then 6741, then 2474, then 6555 — because fixing
the last nine requirements broke the first thirty. Repair mode converges;
regeneration thrashes.

---

## 6. Traceability: the point examiners care about

The SRS numbers its requirements `FR-<area>-<sequence>`: **FR-G-01**,
**FR-CB-02**, **FR-FA-02**. There are **70 functional requirements** in the
document.

Each generated test is named after its requirement:

| SRS requirement | Generated test |
|---|---|
| FR-FA-02 — Successful login with valid credentials | `def test_fr_fa_02(page: Page)` |
| FR-CB-02 — Checkbox state toggle | `def test_fr_cb_02(page: Page)` |

So anyone can pick any requirement in the document and find its test in one
search. That is **requirement traceability**, and it is the thing that makes
this a QA engineering project rather than a code-generation demo.

The pipeline verifies this itself: it regex-scans the SRS for requirement IDs
and reports any that got no test. That check does not rely on the LLM being
honest about its own coverage.

---

## 7. Questions you will be asked, and honest answers

**"Is this just ChatGPT writing tests?"**
No. A single prompt gives you an unverified guess. This adds three things a
prompt cannot: real locators crawled from the live site, deterministic
validation of the output, and an automatic repair loop. The verification is the
contribution.

**"What if the LLM writes a bad test?"**
Two nets catch it. The validator checks structure — syntax, coverage,
assertions. Then pytest actually runs the suite against the real site, and a
wrong assertion fails there. A test that passes both is a test that genuinely ran
against real HTML.

**"Why Playwright and not Selenium?"**
Playwright has auto-waiting built in, so most timing flakiness disappears
without writing explicit waits. Its locator API (`get_by_role`, `get_by_label`)
is also semantic, which makes generated locators more stable than XPath.

**"Why not let the LLM crawl the page itself?"**
Cost and reliability. A page's HTML is tens of thousands of tokens, most of it
irrelevant. The crawler distils it to a few hundred verified locators, which is
cheaper and more accurate.

**"What's the weakest part?"**
Honestly: the site must be publicly reachable and unauthenticated, the crawler
does not handle multi-step flows behind a login, and non-functional
requirements (NFR-P-01 performance, NFR-UX-01 "feels appealing") cannot be
tested by UI automation at all. Those are scoped out deliberately.

**"How do you measure success?"**
Not "the Reviewer approved it". The real number is the pytest pass rate against
the live site, plus SRS coverage — how many of the 70 requirements got a test.
Quote both.

---

## 8. Known limitations — say these before you are asked

1. Only public, unauthenticated pages are crawled.
2. Non-functional and subjective requirements are out of scope.
3. Randomised behaviours in the SRS (section 5.1) cannot be asserted
   deterministically.
4. LLM output varies between runs even at temperature 0.1, so two runs may
   produce slightly different suites.
5. The repair loop stops after 4 attempts; it does not guarantee a pass.

Stating your limits yourself reads as engineering maturity. Being caught out on
them does not.

---

## 9. Two things to do before you submit

1. **Run it once, end to end,** and keep the output files — the generated
   suite, the execution log, and the pytest result. A demo with real numbers is
   far stronger than a description.
2. **Read section 5 until you can say it in your own words.** Examiners follow
   up, and follow-ups are where a memorised script falls apart. The ideas here
   are not difficult — the loop, real locators, and code-checks-facts are the
   whole story, and once they click you will not need notes.
