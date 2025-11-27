import pandas as pd
import json

def split_nonempty_lines(text: str):
    """Split text into non-empty, stripped lines."""
    return [ln.strip() for ln in str(text).splitlines() if ln.strip()]


# ---------- Load data ----------

# 1) Template with all qid × language rows
df_q = pd.read_csv("text/questions_all_languages_template.csv")

# 2) All parts for all languages (scraped)
# expected columns: unit,page,part,language_name,lang_code,text
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


# ---------- Helper: get line with fallback to English scraped text ----------

def get_line_with_fallback(unit, page, part, line_idx, language):
    """
    Try to get lines[line_idx] for (unit,page,part,language).
    If not available or out of range, fall back to English scraped text.
    Returns "" if nothing found.
    """
    # If unit/page/part are None → this came from a "fallback" entry,
    # we should not try to look into blocks at all.
    if unit is None or page is None or part is None or line_idx is None:
        return ""

    # Try target language
    key_lang = (unit, page, part, language)
    lines = blocks.get(key_lang)
    if lines is not None and 0 <= line_idx < len(lines):
        return lines[line_idx]

    # Fallback → English scraped block
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

    # Make quick lookup by index
    ctx_by_idx = {ref["ctx_idx"]: ref for ref in ctx_refs if "ctx_idx" in ref}
    q_by_idx   = {ref["q_idx"]:  ref for ref in q_refs   if "q_idx"  in ref}
    opt_by_idx = {ref["opt_idx"]: ref for ref in opt_refs if "opt_idx" in ref}

    # All rows in template for this qid
    mask_q = (df_out["qid"] == qid)
    if not mask_q.any():
        print(f"[WARN] qid {qid} not found in template, skipping.")
        continue

    # ---------- English base row for this qid ----------
    try:
        english_row = df_out[(df_out["qid"] == qid) & (df_out["language"] == "English")].iloc[0]
        english_context_raw  = english_row.get("context", "") or ""
        english_question_raw = english_row.get("question", "") or ""
        english_options_raw  = english_row.get("options", "") or "[]"
    except IndexError:
        print(f"[WARN] No English row found for qid={qid}, skipping.")
        continue

    english_context_lines  = split_nonempty_lines(english_context_raw)
    english_question_lines = split_nonempty_lines(english_question_raw)

    # ---------- Parse English options to know structure & base texts ----------
    options_type = "unknown"
    parsed_en_opts = None
    english_opt_letters = []
    english_opt_texts   = []

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

    if options_type == "string_list":
        # Extract letter + text from "A) foo"
        import re
        for opt in parsed_en_opts:
            if not isinstance(opt, str):
                continue
            m = re.match(r"^([A-Z])\)\s*(.*)$", opt.strip())
            if m:
                letter, text = m.group(1), m.group(2)
            else:
                # Fallback: best effort
                letter = opt[0] if opt else "?"
                text   = opt[2:].strip() if len(opt) > 2 else ""
            english_opt_letters.append(letter)
            english_opt_texts.append(text)

    # ---------- Fill all languages for this qid ----------
    for idx, row in df_out[mask_q].iterrows():
        lang = row["language"]

        # ----- CONTEXT -----
        context_lines_lang = []
        for i, base_line in enumerate(english_context_lines):
            ref = ctx_by_idx.get(i)

            if ref is None:
                # no alignment → keep English base line
                context_lines_lang.append(base_line)
            else:
                # if ref has explicit fallback flag → use original English line from alignment (if provided)
                if ref.get("fallback"):
                    # if you stored text_eng in alignment_lines.json:
                    text_eng = ref.get("text_eng", base_line)
                    context_lines_lang.append(text_eng)
                else:
                    unit = ref["unit"]
                    page = ref["page"]
                    part = ref["part"]
                    li   = ref["line_idx"]

                    line_text = get_line_with_fallback(unit, page, part, li, lang)
                    # if even this fails, keep English base line
                    context_lines_lang.append(line_text if line_text else base_line)

        context_lang = "\n".join(context_lines_lang) if context_lines_lang else row.get("context", "")

        # ----- QUESTION -----
        question_lines_lang = []
        for i, base_line in enumerate(english_question_lines):
            ref = q_by_idx.get(i)

            if ref is None:
                question_lines_lang.append(base_line)
            else:
                if ref.get("fallback"):
                    text_eng = ref.get("text_eng", base_line)
                    question_lines_lang.append(text_eng)
                else:
                    unit = ref["unit"]
                    page = ref["page"]
                    part = ref["part"]
                    li   = ref["line_idx"]

                    line_text = get_line_with_fallback(unit, page, part, li, lang)
                    question_lines_lang.append(line_text if line_text else base_line)

        question_lang = "\n".join(question_lines_lang) if question_lines_lang else row.get("question", "")

        # ----- OPTIONS -----
        if options_type == "dict_list":
            # Special structure (e.g. grids): just copy English JSON string to all languages unchanged.
            options_lang = english_options_raw

        elif options_type == "string_list" and english_opt_texts:
            # Normal MCQ with A), B), C) ...
            options_list = []
            for i, (letter_base, base_text) in enumerate(zip(english_opt_letters, english_opt_texts)):
                ref = opt_by_idx.get(i)

                if ref is None:
                    # No alignment for this option → keep English option text
                    final_text = base_text
                    letter = letter_base
                else:
                    letter = ref.get("letter", letter_base)

                    if ref.get("fallback"):
                        text_eng = ref.get("text_eng", base_text)
                        final_text = text_eng
                    else:
                        unit = ref["unit"]
                        page = ref["page"]
                        part = ref["part"]
                        li   = ref["line_idx"]

                        line_text = get_line_with_fallback(unit, page, part, li, lang)
                        final_text = line_text if line_text else base_text

                options_list.append(f"{letter}) {final_text}")

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
