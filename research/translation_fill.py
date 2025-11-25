import pandas as pd
import json

def split_nonempty_lines(text: str):
    """Split text into non-empty, stripped lines."""
    return [ln.strip() for ln in str(text).splitlines() if ln.strip()]


# ---------- Load data ----------

# 1) Template with all qid × language rows
df_q = pd.read_csv("text/questions_all_languages_template.csv")

# 2) All parts for all languages (scraped)
# expected columns: unit,page,part,language,lang_code,text
df_parts = pd.read_csv("text/all_parts_all_languages.csv")

# 3) Alignment from English (line-level)
with open("alignment_lines.json", "r", encoding="utf-8") as f:
    align_map = json.load(f)


# ---------- Build block lookup: (unit,page,part,language) -> list of lines ----------

blocks = {}
for _, r in df_parts.iterrows():
    unit = r["unit"]
    page = int(r["page"])
    part = int(r["part"])
    language = r["language_name"]
    text = r["text"]

    key = (unit, page, part, language)
    blocks[key] = split_nonempty_lines(text)


# ---------- Helper: get line with fallback to English ----------

def get_line_with_fallback(unit, page, part, line_idx, language):
    """
    Try to get lines[line_idx] for (unit,page,part,language).
    If not available or out of range, fall back to English.
    Returns "" if nothing found.
    """
    # Try target language
    key_lang = (unit, page, part, language)
    lines = blocks.get(key_lang)
    if lines is not None and 0 <= line_idx < len(lines):
        return lines[line_idx]

    # Fallback → English
    key_en = (unit, page, part, "English")
    lines_en = blocks.get(key_en)
    if lines_en is not None and 0 <= line_idx < len(lines_en):
        return lines_en[line_idx]

    return ""


# ---------- Build output ----------

df_out = df_q.copy()
LETTERS = ["A", "B", "C", "D"]  # just in case

for qid, alignment in align_map.items():
    ctx_refs = alignment.get("context", [])
    q_refs   = alignment.get("question", [])
    opt_refs = alignment.get("options", [])

    # All rows in template for this qid
    mask_q = (df_out["qid"] == qid)
    if not mask_q.any():
        print(f"[WARN] qid {qid} not found in template, skipping.")
        continue

    # ---------- Determine English options structure for this qid ----------
    try:
        english_row = df_out[(df_out["qid"] == qid) & (df_out["language"] == "English")].iloc[0]
        english_options_raw = english_row["options"]
    except IndexError:
        english_options_raw = "[]"
        print(f"[WARN] No English options found for qid={qid}, using empty list.")

    # Try to parse English options
    options_type = "unknown"
    parsed_en_opts = None
    try:
        parsed_en_opts = json.loads(english_options_raw)
        if isinstance(parsed_en_opts, list) and parsed_en_opts and isinstance(parsed_en_opts[0], dict):
            options_type = "dict_list"   # [{ "A": [...] }, { "B": [...] }, ...]
        elif isinstance(parsed_en_opts, list) and (not parsed_en_opts or isinstance(parsed_en_opts[0], str)):
            options_type = "string_list" # ["A) ...", "B) ...", ...]
        else:
            options_type = "other"
    except Exception as e:
        print(f"[WARN] Could not parse English options for qid={qid}: {e}")
        options_type = "parse_error"

    for idx, row in df_out[mask_q].iterrows():
        lang = row["language"]

        # ----- CONTEXT -----
        context_lines_lang = []
        for ref in sorted(ctx_refs, key=lambda x: x["ctx_idx"]):
            unit = ref["unit"]
            page = ref["page"]
            part = ref["part"]
            li   = ref["line_idx"]

            line_text = get_line_with_fallback(unit, page, part, li, lang)
            if line_text:
                context_lines_lang.append(line_text)

        if context_lines_lang:
            context_lang = "\n".join(context_lines_lang)
        else:
            context_lang = row.get("context", "")

        # ----- QUESTION -----
        question_lines_lang = []
        for ref in sorted(q_refs, key=lambda x: x["q_idx"]):
            unit = ref["unit"]
            page = ref["page"]
            part = ref["part"]
            li   = ref["line_idx"]

            line_text = get_line_with_fallback(unit, page, part, li, lang)
            if line_text:
                question_lines_lang.append(line_text)

        if question_lines_lang:
            question_lang = "\n".join(question_lines_lang)
        else:
            question_lang = row.get("question", "")

        # ----- OPTIONS -----
        if options_type == "dict_list":
            # Special structure (e.g. Fact/Opinion, Yes/No grids):
            # just copy English JSON string to all languages unchanged.
            options_lang = english_options_raw

        elif options_type == "string_list" and opt_refs:
            # Normal MCQ: build per-language options from aligned lines.
            options_list = []
            for ref in sorted(opt_refs, key=lambda x: x["opt_idx"]):
                unit = ref["unit"]
                page = ref["page"]
                part = ref["part"]
                li   = ref["line_idx"]
                letter = ref.get("letter", LETTERS[ref["opt_idx"]])

                line_text = get_line_with_fallback(unit, page, part, li, lang)
                if line_text:
                    options_list.append(f"{letter}) {line_text}")

            options_lang = json.dumps(options_list, ensure_ascii=False)

        else:
            # Fallback: just copy English options as-is
            options_lang = english_options_raw

        # ----- Write back into dataframe -----
        df_out.at[idx, "context"]  = context_lang
        df_out.at[idx, "question"] = question_lang
        df_out.at[idx, "options"]  = options_lang


# ---------- Save final table ----------

out_path = "questions_all_languages.csv"
df_out.to_csv(out_path, index=False, encoding="utf-8-sig")
print("Saved:", out_path)
