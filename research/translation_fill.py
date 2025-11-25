import pandas as pd
import json

# ---------- Helpers ----------

def split_nonempty_lines(text: str):
    """Split text into non-empty, stripped lines."""
    return [ln.strip() for ln in str(text).splitlines() if ln.strip()]


# ---------- Load data ----------

# 1) Template with all qid × language rows
df_q = pd.read_csv("questions_all_languages_template.csv")

# 2) All parts for all languages
df_parts = pd.read_csv("all_parts_all_languages.csv")

# 3) Alignment from English
with open("alignment_lines.json", "r", encoding="utf-8") as f:
    align_map = json.load(f)

# ---------- Build a lookup: (unit,page,part,language) -> list of lines ----------

blocks = {}
for _, r in df_parts.iterrows():
    unit = r["unit"]
    page = int(r["page"])
    part = int(r["part"])
    language = r["language"]
    text = r["text"]

    key = (unit, page, part, language)
    blocks[key] = split_nonempty_lines(text)

# We’ll update df_q in place
df_out = df_q.copy()

# For A–D
LETTERS = ["A", "B", "C", "D"]


# ---------- Fill context, question, options for all languages ----------

for qid, alignment in align_map.items():
    ctx_refs = alignment.get("context", [])
    q_refs   = alignment.get("question", [])
    opt_refs = alignment.get("options", [])

    # All rows in template for this qid
    mask = (df_out["qid"] == qid)

    if not mask.any():
        print(f"[WARN] qid {qid} not found in template, skipping.")
        continue

    for idx, row in df_out[mask].iterrows():
        lang = row["language"]

        # ----- CONTEXT -----
        context_lines_lang = []
        # sort by ctx_idx to keep original order
        for ref in sorted(ctx_refs, key=lambda x: x["ctx_idx"]):
            key = (ref["unit"], ref["page"], ref["part"], lang)
            lines = blocks.get(key)
            if lines is None:
                # no block for this language/unit/page/part
                continue
            li = ref["line_idx"]
            if 0 <= li < len(lines):
                context_lines_lang.append(lines[li])

        context_lang = "\n".join(context_lines_lang) if context_lines_lang else row.get("context", "")

        # ----- QUESTION -----
        question_lines_lang = []
        for ref in sorted(q_refs, key=lambda x: x["q_idx"]):
            key = (ref["unit"], ref["page"], ref["part"], lang)
            lines = blocks.get(key)
            if lines is None:
                continue
            li = ref["line_idx"]
            if 0 <= li < len(lines):
                question_lines_lang.append(lines[li])

        question_lang = "\n".join(question_lines_lang) if question_lines_lang else row.get("question", "")

        # ----- OPTIONS (simple 1-line-per-option version) -----
        options_lang = []
        for ref in sorted(opt_refs, key=lambda x: x["opt_idx"]):
            key = (ref["unit"], ref["page"], ref["part"], lang)
            lines = blocks.get(key)
            if lines is None:
                continue
            li = ref["line_idx"]
            if 0 <= li < len(lines):
                txt = lines[li]
                letter = ref.get("letter", LETTERS[ref["opt_idx"]])  # fallback
                options_lang.append(f"{letter}) {txt}")

        options_str = json.dumps(options_lang, ensure_ascii=False)

        # ----- Write back into dataframe -----
        df_out.at[idx, "context"]  = context_lang
        df_out.at[idx, "question"] = question_lang
        df_out.at[idx, "options"]  = options_str

# ---------- Save final table ----------

out_path = "questions_all_languages.csv"
df_out.to_csv(out_path, index=False, encoding="utf-8-sig")
print("Saved:", out_path)
