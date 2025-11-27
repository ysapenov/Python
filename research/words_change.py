import pandas as pd
import re

# ---------- Load data ----------

df = pd.read_csv("questions_all_languages.csv")  # your big table
words = pd.read_csv("text/words.csv")                 # table with Opinion/Fact/Yes/No translations

# ---------- Build translation map ----------
# translation_map[language][EnglishWord] -> translated_word

translation_map = {}

# Group by qid (e.g., q000opinion, q000fact etc.)
for qid, group in words.groupby("qid"):
    # Find the English base row for this qid
    base = group[group["language"] == "English"]
    if base.empty:
        # If there is no English row for this qid, skip
        continue
    
    english_word = base["question"].iloc[0]  # e.g., "Opinion", "Fact", "Yes", "No"

    # For each language row under this qid, store the translation
    for _, row in group.iterrows():
        lang = row["language"]
        translated = row["question"]
        translation_map.setdefault(lang, {})[english_word] = translated

# Just to be safe, explicitly restrict to the 4 target words we care about
TARGET_WORDS = ["Opinion", "Fact", "Yes", "No"]
pattern = re.compile(r'\b(' + "|".join(TARGET_WORDS) + r')\b')

def replace_keywords(text: str, lang: str) -> str:
    """Replace Opinion/Fact/Yes/No with translations for the given language."""
    if lang == "English":
        return text  # do nothing for English

    if lang not in translation_map:
        return text  # no translations known for this language

    def repl(match):
        eng_word = match.group(1)  # e.g. "Opinion"
        # If we have a translation, use it; otherwise keep the original word
        return translation_map[lang].get(eng_word, eng_word)

    return pattern.sub(repl, text)

# ---------- Apply to text columns in the main table ----------

text_columns = ["question", "context", "options", "rationale"]  # adjust if needed

for col in text_columns:
    if col in df.columns:
        df[col] = df.apply(
            lambda row: replace_keywords(str(row[col]), row["language"]),
            axis=1
        )

# ---------- Save result ----------

df.to_csv("questions_all_languages_words.csv", index=False)
print("Done! Saved to questions_all_languages_translated.csv")
