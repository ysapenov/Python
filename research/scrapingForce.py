from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import csv
import os

# ===================== CONFIG =====================

# Example unit: 2022 math item
UNIT = "MAT/MA161-ForestedAreas"

# Max inner pages to try; loop stops early when NEXT is gone/disabled
MAX_PAGES = 7

OUT_CSV = f"{UNIT}_parts_all_languages.csv"

# Map of language_name -> PISA lang code
LANG_CODES = {
    "Albanian": "sqi-ALB",
    "Arabic": "ara-ARE",              # depends on country: EGY, SAU, QAT, etc.
    "Azerbaijani / Azeri": "aze-QAZ",
    "Basque": "eus-ESP",
    "Bokmål": "nob-NOR",
    "Bosnian": "bos-BIH",
    "Bulgarian": "bul-BGR",
    "Catalan": "cat-ESP",
    "Chinese": "zho-CHN",
    "Croatian": "hrv-HRV",
    "Czech": "ces-CZE",
    "Danish": "dan-DNK",
    "Dutch": "nld-NLD",
    "English": "eng-CAN",             # depends on country
    "Estonian": "est-EST",
    "Finnish": "fin-FIN",
    "French": "fra-FRA",
    "Galician": "glg-ESP",
    "Georgian": "geo-GEO",
    "German": "deu-DEU",
    "Greek": "ell-GRC",
    "Hebrew": "heb-ISR",
    "Hungarian": "hun-HUN",
    "Icelandic": "isl-ISL",
    "Indonesian": "ind-IDN",
    "Italian": "ita-ITA",
    "Japanese": "jpn-JPN",
    "Kazakh": "kaz-KAZ",
    "Korean": "kor-KOR",
    "Latvian": "lav-LVA",
    "Lithuanian": "lit-LTU",
    "Malay": "msa-MYS",
    "Nynorsk": "nno-NOR",
    "Polish": "pol-POL",
    "Portuguese": "por-PRT",
    "Russian": "rus-KAZ",             # your example
    "Serbian / Serb": "srp-SRB",
    "Slovak": "slo-SVK",
    "Slovenian": "slv-SVN",
    "Spanish": "esp-ESP",
    "Swedish": "swe-SWE",
    "Thai": "tha-THA",
    "Turkish": "tur-TUR"
}

# PISA 2022 base URL (math, reading, etc.)
BASE_URL = (
    "https://pisa2022-questions.oecd.org/platform/index.html"
    "?user=&unit={unit}&lang={lang}"
)

# (unit, page_index) -> list of CSS selectors to click inside content frames
# Example: for MA161 page 2, click the sortable header "Kolona E"
SPECIAL_ACTIONS = {
    ("MAT/MA161-ForestedAreas", 2): [
        {"type": "click", "selector": "#r0th3"},
        {"type": "wait",   "ms": 100},
        {"type": "select", "selector": "#SelectedColumn1", "value": "2"},
        {"type": "wait",   "ms": 100},
        {"type": "select", "selector": "#Operation", "value": "+"},
        {"type": "wait",   "ms": 100},
        {"type": "select", "selector": "#SelectedColumn2", "value": "2"},
        {"type": "wait",   "ms": 100},
        {"type": "click",  "selector": "#runButton1"},
        {"type": "wait",   "ms": 400},  # table will update
        {"type": "select", "selector": "#MeanColumn", "value": "2"},
        {"type": "wait",   "ms": 100},
        {"type": "click",  "selector": "#runButton2"},
        {"type": "wait",   "ms": 400},  # final update before NEXT
    ],
        ("MAT/MA161-ForestedAreas", 3): [
        {"type": "click", "selector": "#aMenu_part1_h3_1"},
        {"type": "wait",   "ms": 100},
    ],
}

# ==================================================


def build_url(unit: str, lang_code: str) -> str:
    return BASE_URL.format(unit=unit, lang=lang_code)


def is_navigation_frame(frame) -> bool:
    url = (frame.url or "").lower()
    return "navigation" in url


def clean_text_block(raw_text: str) -> str:
    """
    Strip spaces on each line, drop empty lines, join with single '\n'.
    """
    if not raw_text:
        return ""

    lines = [line.strip() for line in raw_text.splitlines()]
    lines = [line for line in lines if line]  # keep only non-empty
    return "\n".join(lines)


def extract_parts_from_page(page):
    """
    Return a list of (part_index, text) for the current inner page.
    Each non-navigation frame = one 'part'.
    Parts are ordered by frame order (usually left = part 1, right = part 2).
    """
    parts = []
    part_idx = 1

    for frame in page.frames:
        if is_navigation_frame(frame):
            continue

        try:
            raw = frame.text_content("body")
        except Exception:
            raw = None

        text = clean_text_block(raw or "")

        if text:  # only keep non-empty parts
            parts.append((part_idx, text))
            part_idx += 1

    return parts


def find_navigation_frame(page):
    for f in page.frames:
        if is_navigation_frame(f):
            return f
    return None

def get_unit_frame(page, unit: str, page_idx: int):
    """
    Return the frame that contains the actual unit content for this page.
    For MAT/MA161-ForestedAreas:
      - page 2 uses ModuleId=stimulus (table controls),
      - later pages use ModuleId=question (accordion questions).
    """
    candidates = []
    for f in page.frames:
        url = f.url or ""
        if "/platform/unit/" in url and unit in url:
            candidates.append(f)

    if not candidates:
        return None

    # Prefer specific ModuleId based on page index
    # (works well for MA161 and similar 2022 items)
    if page_idx == 2:
        for f in candidates:
            if "ModuleId=stimulus" in (f.url or ""):
                return f
    else:
        for f in candidates:
            if "ModuleId=question" in (f.url or ""):
                return f

    # Fallback: first candidate
    return candidates[0]


def run_special_actions(page, unit: str, page_idx: int):
    actions = SPECIAL_ACTIONS.get((unit, page_idx), [])
    if not actions:
        return

    print(f"  [INFO] Running special actions for {unit} page {page_idx}")

    # Find the frame that actually holds the unit content
    unit_frame = get_unit_frame(page, unit, page_idx)
    if not unit_frame:
        print("    [WARN] Could not find unit frame – no special actions run.")
        return

    print(f"    [FRAME] Using unit frame url={unit_frame.url}")

    # Small wait to ensure DOM is ready
    page.wait_for_timeout(500)

    for action in actions:
        act_type = action.get("type")
        selector = action.get("selector")

        # ----- CLICK -----
        if act_type == "click":
            print(f"    [ACTION] CLICK → {selector}")
            el = unit_frame.query_selector(selector)
            if el:
                try:
                    unit_frame.eval_on_selector(selector, "el => el.click()")
                    print("      [OK] Clicked")
                except Exception as e:
                    print(f"      [WARN] Click failed: {e}")
            else:
                print(f"      [WARN] Element not found for CLICK: {selector}")

        # ----- SELECT -----
        elif act_type == "select":
            value = action.get("value")
            index = action.get("index")

            if index is not None:
                print(f"    [ACTION] SELECT (index) → {selector} index={index}")
            else:
                print(f"    [ACTION] SELECT (value) → {selector} value={value}")

            el = unit_frame.query_selector(selector)
            if el:
                try:
                    if index is not None:
                        unit_frame.select_option(selector, index=index)
                    else:
                        unit_frame.select_option(selector, value=value)
                    print("      [OK] Selected")
                except Exception as e:
                    print(f"      [WARN] Select failed: {e}")
            else:
                print(f"      [WARN] Element not found for SELECT: {selector}")

        # ----- WAIT -----
        elif act_type == "wait":
            delay = action.get("ms", 100)
            print(f"    [ACTION] WAIT → {delay} ms")
            page.wait_for_timeout(delay)

    print("    [ACTION] WAIT (post-actions) → 800 ms")
    page.wait_for_timeout(800)



def click_next(page, unit: str, page_idx: int) -> bool:
    """
    Click <li id='next'> in navigation iframe.

    If disabled:
      1) generic auto-answer of radios/buttons,
      2) run SPECIAL_ACTIONS for this (unit, page),
    then re-check and click if enabled.

    Returns True if we sent a click (expecting page to advance),
    False if there is no usable NEXT.
    """
    nav_frame = find_navigation_frame(page)
    if not nav_frame:
        print("  [WARN] Navigation frame not found")
        return False

    btn = nav_frame.query_selector("li#next")
    if not btn:
        print("  [INFO] li#next not found – no NEXT on this screen")
        return False

    disabled_attr = btn.get_attribute("disabled")

    if disabled_attr is not None:
        print("  [INFO] NEXT disabled – trying auto-answer + special actions.")
        run_special_actions(page, unit, page_idx)

        # re-fetch button after interactions
        nav_frame = find_navigation_frame(page)
        if not nav_frame:
            print("  [WARN] Navigation frame disappeared after answering?")
            return False

        btn = nav_frame.query_selector("li#next")
        if not btn:
            print("  [INFO] li#next gone after answering – stopping.")
            return False

        disabled_attr = btn.get_attribute("disabled")
        if disabled_attr is not None:
            print("  [INFO] NEXT still disabled after special actions – stopping.")
            return False

    # At this point, NEXT should be enabled.
    try:
        # JS click inside nav frame – avoids overlay issues
        nav_frame.eval_on_selector("li#next", "el => el.click()")
    except PlaywrightTimeoutError:
        print("  [WARN] Timeout while clicking NEXT – stopping.")
        return False
    except Exception:
        print("  [WARN] Error while clicking NEXT – stopping.")
        return False

    page.wait_for_timeout(1000)
    return True


def scrape_language(play, language_name: str, lang_code: str):
    url = build_url(UNIT, lang_code)
    print(f"\n=== {language_name} ({lang_code}) → {url}")

    browser = play.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(url, wait_until="networkidle")

    rows = []  # (page_idx, part_idx, text)

    for page_idx in range(1, MAX_PAGES + 1):
        print(f"  Page {page_idx}/{MAX_PAGES} ...", end="", flush=True)

        parts = extract_parts_from_page(page)
        print(f" found {len(parts)} parts")

        for part_idx, text in parts:
            rows.append((page_idx, part_idx, text))

        # try to go to next; if cannot, break
        if not click_next(page, UNIT, page_idx):
            break

    browser.close()
    return rows


def main():
    os.makedirs(os.path.dirname(OUT_CSV) or ".", exist_ok=True)

    # utf-8-sig -> UTF-8 with BOM so Excel reads Cyrillic etc. correctly
    with sync_playwright() as p, open(
        OUT_CSV, "w", encoding="utf-8-sig", newline=""
    ) as f:
        writer = csv.writer(f)
        writer.writerow(
            ["unit", "page", "part", "language_name", "lang_code", "text"]
        )

        for lang_name, lang_code in LANG_CODES.items():
            rows = scrape_language(p, lang_name, lang_code)

            for page_idx, part_idx, text in rows:
                writer.writerow(
                    [UNIT, page_idx, part_idx, lang_name, lang_code, text]
                )

    print(f"\nDone. Saved all parts to: {OUT_CSV}")


if __name__ == "__main__":
    main()
