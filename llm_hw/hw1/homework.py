import argparse
import re
import requests
import json
from utils import  read_warc_file, read_wet_file
from datasets import load_dataset
from typing import Set, Dict
import string

from bs4 import BeautifulSoup

def retrieve_bad_words() -> set[str]:
    """Helper function - that reads a list of bad words from a file and returns them as a set.
    Returns:
        Set[str]: A set containing lowercase bad words.
    """
    with open('./bad_word_list.txt', 'r') as file:
        records = file.read().strip().split('\n')
        bad_words = [record.lower() for record in records]
        return set(bad_words)


def html_to_text(html: str) -> str:
    """Converts HTML content to plain text..
    Args:
        html (bytes): HTML content as bytes.
    Returns:
        str: Plain text extracted from HTML.
    """
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    # Remove noise
    for t in soup(["script", "style", "noscript"]):
        t.decompose()

    result = soup.get_text()

    global count_pages, count_tables, count_codes, count_images, count_headers, table_example, code_example, image_example, header_example
    # Count elements
    count_tables += len(soup.find_all("table"))
    count_codes += len(soup.find_all("code"))
    count_images += len(soup.find_all("img"))
    # headers: all h1–h6
    count_headers += sum(len(soup.find_all(f"h{i}")) for i in range(1, 7))

    try:
        table_example = soup.find("table").get_text()
    except:
        print("Table 'NoneType' object has no attribute 'get_text'")

    try:
        code_example = soup.find("code").get_text()
    except:
        print("Code 'NoneType' object has no attribute 'get_text'")

    try:
        image_example = soup.find("img").get_text()
    except:
        print("Image 'NoneType' object has no attribute 'get_text'")

    try:
        header_example = soup.find("h1").get_text()
    except:
        print("Header 'NoneType' object has no attribute 'get_text'")

    # Increment page counter
    count_pages += 1
    
    return result

def replace_pii(text: str) -> str:
    """Masks personally identifiable information (PII) from text with the specified masking formats.
    Args: 
        text (str): Candidate text.
    Returns:
        str: Text with PII obfuscated.
    """
    pass 
    

def clean_text(text: str) -> str:
    """Removes substrings identified as low-quality according to alphanumeric, whitespace and valid document checks.  
    Args:
        text (str): document to process.
    Returns:
        str: cleaned document
    """
    pass


def heuristic_quality_filter(text: str) -> bool:
    """Rejects documents based on the presence of bad words and punctuation.
    Args:
        text (str): document to check
    Returns:
        bool: returns True if the document passes the filters, False otherwise.
    """
    pass 
    

def deduplicate_texts(texts: list[str]) -> list[str]:
    """Deduplicates text by removing duplicate sentences.
    Args:
        text (str): Text to deduplicate.
    Returns:
        str: Deduplicated text. Implemented a simple Jacard similarity based deduplication. 
    """
    pass


if __name__ == '__main__' :
    count_pages = 0
    count_tables = 0
    count_codes = 0
    count_images = 0
    count_headers = 0

    parser = argparse.ArgumentParser()
    parser.add_argument('--fname', type = str,  default = '', help = 'Specify the path for your warc file.')
    parser.add_argument('--dfname', type = str,  default = '', help = 'Specify the path where you stored topic_dataset.json')
    parser.add_argument('--num_records', type = int,  default=30, help = 'Specify the number of records you want to parse (only used for debugging with smaller sets)')
    # parser.add_argument('--wet_name', type = str, default = '', help = 'Specify the path for your wet file.')
    args = parser.parse_args()

    if args.fname:
        seen = 0
        passes = 0
        for url, html_text in read_warc_file(args.fname, args.num_records):
            seen += 1
            # print("Before HTML to text: ", str(html_text))
            text = html_to_text(str(html_text))
            # print("\n\n\nAfter HTML to text: ", text)
            cleaned_text = clean_text(text)
            # print("After cleaning: ", cleaned_text)
            cleaned_nopii_text = replace_pii(cleaned_text)
            # print("After PII removal: ", cleaned_nopii_text)
            passes_check = heuristic_quality_filter(cleaned_nopii_text)
            print(url)
            print("Passes heuristic quality filter:", passes_check)
            if passes_check:
                passes += 1
                print(cleaned_nopii_text)
                print("\n\n")
        print(f"{passes} passed out of {seen} records processed.")

        print("Total pages parsed:", count_pages)
        print("Total tables found:", count_tables)
        print("Total code blocks found:", count_codes)
        print("Total embedded images found:", count_images)
        print("Total headers found:", count_headers)

        print("Table example:", table_example)
        print("Code example:", code_example)
        print("Image example:", image_example)
        print("Header example:", header_example)

    if args.dfname:
        with open(args.dfname, 'r') as f:
            raw_texts = json.load(f)
        raw_texts = [item['text'] for item in raw_texts['data']]
        deduplicated_texts = deduplicate_texts(raw_texts)
        
    else:
        print("Usage: python homework.py --fname data.warc")