import pandas as pd
import ast
import re
import json

# ----------------- Helpers -----------------

def normalize(s: str) -> str:
    """Lowercase, collapse whitespace."""
    return re.sub(r"\s+", " ", str(s).strip().lower())

def split_nonempty_lines(text: str):
    return [ln.strip() for ln in str(text).splitlines() if ln.strip()]


# ----------------- Load Data -----------------

# Your curated English questions table
df_eng = pd.read_csv("text/questions_eng.csv")

# Your scraped texts for all languages
# Must contain: unit,page,part,language,lang_code,text
df_raw = pd.read_csv("text/all_parts_all_languages.csv")   # scraped English + other languages

# Only English scraped rows for alignment
df_raw_eng = df_raw[df_raw["language_name"] == "English"].copy()

# Pre-build English blocks: (unit,page,part) -> {lines, norms}
blocks_eng = {}
for _, r in df_raw_eng.iterrows():
    key = (r["unit"], int(r["page"]), int(r["part"]))
    lines = split_nonempty_lines(r["text"])
    norms = [normalize(ln) for ln in lines]
    blocks_eng[key] = {"lines": lines, "norms": norms}

align_map = {}

# ----------------- BUILD ALIGNMENT (ONE MATCH PER INDEX) -----------------

for _, q in df_eng.iterrows():
    qid = q["qid"]

    # 1) Split English pieces into lines
    context_lines_eng  = split_nonempty_lines(q["context"])
    question_lines_eng = split_nonempty_lines(q["question"])

    # Parse options from '["A) ...","B) ...",...]'
    options_eng = ast.literal_eval(q["options"])
    option_texts_eng = [re.sub(r"^[A-D]\)\s*", "", o).strip() for o in options_eng]
    option_letters    = [o[0] for o in options_eng]  # "A","B","C","D"

    # Normalize English lines
    ctx_norms = [normalize(x) for x in context_lines_eng]
    q_norms   = [normalize(x) for x in question_lines_eng]
    opt_norms = [normalize(x) for x in option_texts_eng]

    # We keep *one* match per index
    align_context_by_idx  = {}  # ctx_idx -> ref dict
    align_question_by_idx = {}  # q_idx   -> ref dict
    align_options_by_idx  = {}  # opt_idx -> ref dict

    # ---------- Context lines ----------
    for ci, ctx_norm in enumerate(ctx_norms):
        if not ctx_norm:
            continue

        found = False
        for (unit, page, part), block in blocks_eng.items():
            norms = block["norms"]
            for line_idx, ln in enumerate(norms):
                if ctx_norm in ln:
                    align_context_by_idx[ci] = {
                        "unit": unit,
                        "page": page,
                        "part": part,
                        "line_idx": line_idx,
                        "ctx_idx": ci,
                    }
                    found = True
                    break
            if found:
                break

        if not found:
            print(f"[WARN] Could not align context line idx={ci} for qid={qid}: {context_lines_eng[ci]}")

    # ---------- Question lines ----------
    for qi, q_norm in enumerate(q_norms):
        if not q_norm:
            continue

        found = False
        for (unit, page, part), block in blocks_eng.items():
            norms = block["norms"]
            for line_idx, ln in enumerate(norms):
                if q_norm in ln:
                    align_question_by_idx[qi] = {
                        "unit": unit,
                        "page": page,
                        "part": part,
                        "line_idx": line_idx,
                        "q_idx": qi,
                    }
                    found = True
                    break
            if found:
                break

        if not found:
            print(f"[WARN] Could not align question line idx={qi} for qid={qid}: {question_lines_eng[qi]}")

    # ---------- Options (A,B,C,D or A,B) ----------
    for oi, opt_norm in enumerate(opt_norms):
        if not opt_norm:
            continue

        found = False
        for (unit, page, part), block in blocks_eng.items():
            norms = block["norms"]
            for line_idx, ln in enumerate(norms):
                if opt_norm in ln:
                    align_options_by_idx[oi] = {
                        "unit": unit,
                        "page": page,
                        "part": part,
                        "line_idx": line_idx,
                        "opt_idx": oi,
                        "letter": option_letters[oi][0],  # "A","B",...
                    }
                    found = True
                    break
            if found:
                break

        if not found:
            print(f"[WARN] Could not align option idx={oi} for qid={qid}: {option_texts_eng[oi]}")

    # ---------- Convert dicts -> sorted lists ----------
    align_context = [align_context_by_idx[i] for i in sorted(align_context_by_idx.keys())]
    align_question = [align_question_by_idx[i] for i in sorted(align_question_by_idx.keys())]
    align_options  = [align_options_by_idx[i]  for i in sorted(align_options_by_idx.keys())]

    align_map[qid] = {
        "context":  align_context,
        "question": align_question,
        "options":  align_options,
    }

# ----------------- Save alignment -----------------

with open("alignment_lines.json", "w", encoding="utf-8") as f:
    json.dump(align_map, f, ensure_ascii=False, indent=2)

print("Saved alignment_lines.json")
