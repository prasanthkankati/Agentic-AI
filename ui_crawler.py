"""
ui_crawler.py  (v2)

WHAT CHANGED FROM v1
--------------------
1. Crawls the base URL *and* its sub-pages, not just the landing page.
   Your SRS talks about /login, /checkboxes, /upload... so the Developer
   agent needs locators from those pages, not just homepage links.

2. The uniqueness check actually works now.
   v1 did:  page.locator("getByRole('button', { name: 'x' })")
   Playwright read that string as a CSS selector, threw an error, and the
   bare `except` returned False. So the good strategies never won and
   everything fell through to the href fallback. Now we build the REAL
   Locator object and count it.

3. Emits Python syntax (get_by_role) instead of JS (getByRole), because
   the generated tests are pytest + Playwright Python.

4. Captures content elements too (headings, flash messages, tables).
   Requirements like "displays the heading 'Welcome to the-internet'"
   are untestable without them.

5. Every element records which page it was found on.

OUTPUT: a flat JSON list, so state['locators'] stays a list.
  {"page": "/login", "tag": "input",
   "locator": "page.get_by_label(\"Username\")", "text": ""}
"""

import asyncio
import json
import os
import sys
from urllib.parse import urljoin, urlparse

from playwright.async_api import async_playwright

# ---------------- CONFIG ----------------

# How many pages to visit in total (the landing page counts as 1).
MAX_PAGES = int(os.getenv("MAX_PAGES", "25"))

# Set HEADLESS=false when you want to watch Playwright drive Chromium.
HEADLESS = os.getenv("HEADLESS", "false").lower() not in {"0", "false", "no"}

# Pages that hang, download files, or pop native auth dialogs.
# Playwright will sit on these forever, so we never visit them.
SKIP_SUBSTRINGS = (
    "/basic_auth",
    "/digest_auth",
    # allow /upload pages (we want file-upload tests), but skip downloads
    "/download",
    "/redirector",
    "/status_codes/",
    "/nested_frames",
    ".zip",
    ".pdf",
    "mailto:",
)

# Things a user can interact with.
INTERACTIVE_SELECTOR = "a, button, input, select, textarea"

# Things a test needs to assert against.
CONTENT_SELECTOR = "h1, h2, h3, h4, label, #flash, #result, table, .example > p"

# Don't re-collect the 45-link nav menu on all 25 pages.
MAX_ELEMENTS_PER_PAGE = 40


# ---------------- HELPERS ----------------

def py_str(value: str) -> str:
    """
    Turn a Python string into a safe Python string *literal*.
    json.dumps handles the quoting and escaping correctly, and its
    output is valid Python too. Avoids v1's manual backslash juggling.
    """
    return json.dumps(value)


def clean(text) -> str:
    """Collapse whitespace so 'Login\\n ' and 'Login' compare equal."""
    if not text:
        return ""
    return " ".join(text.split()).strip()


async def is_unique(locator) -> bool:
    """
    THE KEY FIX.
    We receive a real Playwright Locator object, not a string, so
    .count() actually queries the DOM instead of throwing.
    """
    try:
        return await locator.count() == 1
    except Exception:
        return False


async def build_locator(page, el, index):
    """
    Try locator strategies best-first. Return the Python code string for
    the first one that matches exactly one element on the page.

    Priority is the order Playwright itself recommends:
      role > label > placeholder > test-id > text > attribute > positional
    """
    tag = await el.evaluate("el => el.tagName.toLowerCase()")
    text = clean(await el.inner_text())
    aria_label = clean(await el.get_attribute("aria-label"))
    placeholder = clean(await el.get_attribute("placeholder"))
    name_attr = await el.get_attribute("name")
    testid = await el.get_attribute("data-testid")
    role_attr = await el.get_attribute("role")
    href = await el.get_attribute("href")
    input_type = (await el.get_attribute("type")) or ""
    el_id = await el.get_attribute("id")

    # Work out the implicit ARIA role from the tag.
    input_roles = {
        "": "textbox",
        "text": "textbox",
        "email": "textbox",
        "password": "textbox",
        "search": "searchbox",
        "checkbox": "checkbox",
        "radio": "radio",
        "submit": "button",
        "button": "button",
        "file": "button",
    }
    role_map = {
        "a": "link",
        "button": "button",
        "select": "combobox",
        "textarea": "textbox",
        "h1": "heading",
        "h2": "heading",
        "h3": "heading",
        "h4": "heading",
        "table": "table",
        "input": input_roles.get(input_type.lower(), "textbox"),
    }
    role = role_attr or role_map.get(tag)

    # ---- 1. ROLE + NAME (most stable, survives redesigns) ----
    if role and text and len(text) < 60:
        code = f"page.get_by_role({py_str(role)}, name={py_str(text)})"
        if await is_unique(page.get_by_role(role, name=text)):
            return code

    # ---- 2. LABEL (best for form fields) ----
    if aria_label:
        code = f"page.get_by_label({py_str(aria_label)})"
        if await is_unique(page.get_by_label(aria_label)):
            return code

    # An <input> is usually labelled by <label for="...">, which
    # get_by_label finds even with no aria-label attribute.
    if tag == "input" and el_id:
        try:
            label_text = clean(
                await page.locator(f'label[for="{el_id}"]').first.inner_text()
            )
            if label_text:
                code = f"page.get_by_label({py_str(label_text)})"
                if await is_unique(page.get_by_label(label_text)):
                    return code
        except Exception:
            pass

    # ---- 3. PLACEHOLDER ----
    if placeholder:
        code = f"page.get_by_placeholder({py_str(placeholder)})"
        if await is_unique(page.get_by_placeholder(placeholder)):
            return code

    # ---- 4. TEST ID ----
    if testid:
        code = f"page.get_by_test_id({py_str(testid)})"
        if await is_unique(page.get_by_test_id(testid)):
            return code

    # ---- 5. EXACT TEXT ----
    if text and len(text) < 50:
        code = f"page.get_by_text({py_str(text)}, exact=True)"
        if await is_unique(page.get_by_text(text, exact=True)):
            return code

    # ---- 6. ATTRIBUTE FALLBACKS ----
    if el_id:
        code = f"page.locator({py_str('#' + el_id)})"
        if await is_unique(page.locator(f"#{el_id}")):
            return code

    if name_attr:
        sel = f'[name="{name_attr}"]'
        code = f"page.locator({py_str(sel)})"
        if await is_unique(page.locator(sel)):
            return code

    if href and tag == "a":
        sel = f'a[href="{href}"]'
        code = f"page.locator({py_str(sel)})"
        if await is_unique(page.locator(sel)):
            return code

    # ---- 7. LAST RESORT (brittle, but better than nothing) ----
    return f"page.locator({py_str(tag)}).nth({index})"


async def scrape_page(page, path, collect_links):
    """Pull every visible, testable element off ONE page."""
    elements = []
    seen = set()

    selector = INTERACTIVE_SELECTOR + ", " + CONTENT_SELECTOR
    if not collect_links:
        # On sub-pages, skip the nav menu; we already captured it.
        selector = selector.replace("a, ", "", 1)

    try:
        found = await page.query_selector_all(selector)
    except Exception as e:
        print(f"  ! query failed on {path}: {e}", file=sys.stderr)
        return elements

    for i, el in enumerate(found):
        if len(elements) >= MAX_ELEMENTS_PER_PAGE:
            break
        try:
            if not await el.is_visible():
                continue

            locator = await build_locator(page, el, i)
            # Helpful debug: flag file inputs so generated tests can include
            # the automatic dummy file path (test_assets/upload_dummy.txt).
            try:
                el_type = await el.get_attribute("type")
                if el_type and el_type.lower() == "file":
                    print(f"    found file input on {path}: {locator}", file=sys.stderr)
            except Exception:
                pass
            if locator in seen:
                continue
            seen.add(locator)

            tag = await el.evaluate("el => el.tagName.toLowerCase()")
            elements.append({
                "page": path,
                "tag": tag,
                "locator": locator,
                "text": clean(await el.inner_text())[:80],
            })
        except Exception:
            # One bad element shouldn't kill the whole crawl.
            continue

    return elements


async def discover_links(page, base_url):
    """Collect same-site sub-page paths from the landing page."""
    base_host = urlparse(base_url).netloc
    paths = []

    hrefs = await page.eval_on_selector_all(
        "a[href]", "els => els.map(e => e.getAttribute('href'))"
    )

    for href in hrefs:
        if not href or href.startswith("#"):
            continue
        if any(s in href for s in SKIP_SUBSTRINGS):
            continue

        parsed = urlparse(urljoin(base_url, href))

        # Same site only — never wander off to github.com etc.
        if parsed.netloc != base_host:
            continue
        if parsed.path in ("", "/"):
            continue
        if parsed.path not in paths:
            paths.append(parsed.path)

    return paths


# ---------------- MAIN CRAWL ----------------

async def crawl_ui_elements_async(base_url: str):
    all_elements = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=HEADLESS,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context()
        page = await context.new_page()

        # --- Landing page ---
        print(f"[1] Crawling {base_url}", file=sys.stderr)
        await page.goto(base_url, timeout=60000)
        await page.wait_for_load_state("domcontentloaded")
        all_elements += await scrape_page(page, "/", collect_links=True)

        # --- Discover sub-pages ---
        paths = await discover_links(page, base_url)
        paths = paths[: MAX_PAGES - 1]
        print(f"    found {len(paths)} sub-pages to visit", file=sys.stderr)

        # --- Visit each sub-page ---
        for n, path in enumerate(paths, start=2):
            target = urljoin(base_url, path)
            try:
                print(f"[{n}] {path}", file=sys.stderr)
                await page.goto(target, timeout=20000)
                await page.wait_for_load_state("domcontentloaded")
                await page.wait_for_timeout(300)
                all_elements += await scrape_page(page, path, collect_links=False)
            except Exception as e:
                print(f"    ! skipped {path}: {type(e).__name__}", file=sys.stderr)
                continue

        await browser.close()

    pages_hit = len(set(e["page"] for e in all_elements))
    print(
        f"DONE: {len(all_elements)} elements across {pages_hit} pages",
        file=sys.stderr,
    )
    return all_elements


# ---------------- CLI ENTRY ----------------

if __name__ == "__main__":
    if len(sys.argv) > 1:
        result = asyncio.run(crawl_ui_elements_async(sys.argv[1]))
        print(json.dumps(result, indent=2))
