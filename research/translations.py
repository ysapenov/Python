import pandas as pd

# 1. Load English table
eng_path = "text/questions_eng.csv"  
df_eng = pd.read_csv(eng_path)

# 2. Define language list (name, PISA code)
LANGS = [
    ("Albanian", "sqi-ALB"),
    ("Arabic", "ara-ARE"),
    ("Azerbaijani / Azeri", "aze-QAZ"),
    ("Basque", "eus-ESP"),
    ("Bokmål", "nob-NOR"),
    ("Bosnian", "bos-BIH"),
    ("Bulgarian", "bul-BGR"),
    ("Catalan", "cat-ESP"),
    ("Chinese", "zho-CHN"),
    ("Croatian", "hrv-HRV"),
    ("Czech", "ces-CZE"),
    ("Danish", "dan-DNK"),
    ("Dutch", "nld-NLD"),
    ("English", "eng-CAN"),
    ("Estonian", "est-EST"),
    ("Finnish", "fin-FIN"),
    ("French", "fra-FRA"),
    ("Galician", "glg-ESP"),
    ("Georgian", "geo-GEO"),
    ("German", "deu-DEU"),
    ("Greek", "ell-GRC"),
    ("Hebrew", "heb-ISR"),
    ("Hungarian", "hun-HUN"),
    ("Icelandic", "isl-ISL"),
    ("Indonesian", "ind-IDN"),
    ("Italian", "ita-ITA"),
    ("Japanese", "jpn-JPN"),
    ("Kazakh", "kaz-KAZ"),
    ("Korean", "kor-KOR"),
    ("Latvian", "lav-LVA"),
    ("Lithuanian", "lit-LTU"),
    ("Malay", "msa-MYS"),
    ("Nynorsk", "nno-NOR"),
    ("Polish", "pol-POL"),
    ("Portuguese", "por-PRT"),
    ("Russian", "rus-KAZ"),
    ("Serbian / Serb", "srp-SRB"),
    ("Slovak", "slo-SVK"),
    ("Slovenian", "slv-SVN"),
    ("Spanish", "esp-ESP"),
    ("Swedish", "swe-SWE"),
    ("Thai", "tha-THA"),
    ("Turkish", "tur-TUR"),
]

rows = []

for _, row in df_eng.iterrows():
    for lang_name, lang_code in LANGS:
        if lang_name == "English":
            # copy full English content
            question = row["question"]
            context  = row["context"]
            options  = row["options"]    # already like ["A) ...", ...]
        else:
            # leave text empty for now (to be filled later)
            question = ""
            context  = ""
            options  = ""   # or "[]"

        rows.append({
            "qid":       row["qid"],
            "language":  lang_name,
            "lang_code": lang_code,
            "question":  question,
            "context":   context,
            "options":   options,
            "gold":      row["gold"],
            "answer_type": row["answer_type"],
            "category":    row["category"],
            "difficulty":  row["difficulty"],
            "rationale":   row.get("rationale", ""),
            "source":      row["source"],
        })

df_all = pd.DataFrame(rows)

out_path = "questions_all_Languages_template.csv"
df_all.to_csv(out_path, index=False, encoding="utf-8-sig")
print("Saved:", out_path)
