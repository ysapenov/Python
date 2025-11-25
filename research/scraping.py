from playwright.sync_api import sync_playwright
import csv
import os

# ------------ CONFIG ---------------

UNIT = "MAT/MA161-ForestedAreas"          
# or , etc. "R551-RapaNui" R548-ChickenForum R557-CowsMilk R548-ChickenForum
MAX_PAGES = 1                 # upper bound; loop stops when NEXT disappears
OUT_CSV = f"{UNIT}_parts_all_languages.csv"

# Fill with your real language codes
LANG_CODES = {
    "Albanian": "sqi-ALB",
    "Arabic": "ara-ARE",              
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
    "English": "eng-CAN",             
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
    "Russian": "rus-KAZ",             
    "Serbian / Serb": "srp-SRB",
    "Slovak": "slo-SVK",
    "Slovenian": "slv-SVN",
    "Spanish": "esp-ESP",
    "Swedish": "swe-SWE",
    "Thai": "tha-THA",
    "Turkish": "tur-TUR"
}
# -----------------------------------

# BASE_URL = (
#     "https://pisa2018-questions.oecd.org/platform/index.html"
#     "?user=&domain=REA&unit={unit}&lang={lang}"
# )

BASE_URL = (
    "https://pisa2022-questions.oecd.org/platform/index.html"
    "?user=&unit={unit}&lang={lang}"
)

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


def click_next(page) -> bool:
    """
    Click <li id='next' title='NEXT'> inside navigation iframe.
    Returns True if clicked, False if not found (last page).
    """
    nav_frame = find_navigation_frame(page)
    if not nav_frame:
        print("  [WARN] Navigation frame not found")
        return False

    btn = nav_frame.query_selector("li#next")
    if not btn:
        print("  [INFO] NEXT button (li#next) not found – probably last page")
        return False
    
    disabled = btn.get_attribute("disabled")
    if disabled is not None:
        print("  [INFO] NEXT button is disabled – last page")
        return False

    try:
        # JS click inside the frame – bypasses overlay intercepting pointer events
        nav_frame.eval_on_selector("li#next", "el => el.click()")
    except PlaywrightTimeoutError:
        # if something weird happens, treat it as last page to avoid crash
        print("  [WARN] Timeout while clicking NEXT – stopping here.")
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

        if not click_next(page):
            break

    browser.close()
    return rows


def main():
    os.makedirs(os.path.dirname(OUT_CSV) or ".", exist_ok=True)

    # utf-8-sig = UTF-8 with BOM so Excel shows Cyrillic correctly
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
