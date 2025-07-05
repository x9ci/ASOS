import google.generativeai as genai
import os
import time
import re
import logging # إضافة وحدة التسجيل

# Configuration
# (نفس التكوينات السابقة)
GEMINI_MODEL_NAME = "gemini-1.5-flash-latest"
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5
TARGET_CHUNK_CHAR_LENGTH = 5000
LITERARY_GLOSSARY = {}

# --- إعداد التسجيل ---
# سيتم تكوينه في if __name__ == '__main__'
# logger = logging.getLogger(__name__) # يمكن استخدامه إذا أردنا مسجلًا خاصًا بالوحدة

def get_glossary_prompt_segment():
    # ... (نفس الدالة)
    if not LITERARY_GLOSSARY:
        return ""
    items = []
    for term, translation in LITERARY_GLOSSARY.items():
        items.append(f"  - \"{term}\": \"{translation}\"")
    return "\n7. **Glossary (Translate these terms consistently as shown):**\n" + "\n".join(items)


def translate_text(api_key: str, text_to_translate: str, target_language: str = "ar", attempt: int = 1) -> str:
    try:
        model = genai.GenerativeModel(GEMINI_MODEL_NAME)
        glossary_segment = get_glossary_prompt_segment()
        prompt = f"""You are an expert literary translator specializing in novels. Your task is to translate the following English text, which is part of a novel, into natural, fluent, engaging, and contextually appropriate {target_language}.

Key Objectives:
1.  **Accuracy and Fidelity:** Maintain the original tone, style, character voices, and nuances.
2.  **Readability:** Avoid literal translation. Aim for a translation that reads as if it were originally written in {target_language}.
3.  **Dialogue:** Translate dialogue naturally, using appropriate punctuation and style for {target_language}.
4.  **Proper Nouns & Terms:** Preserve original English proper nouns (names of people, specific places if they are unique and known by their English names). If a common or established {target_language} equivalent exists for a term or place, use it consistently. If unsure, keep it in English or provide a very brief, natural-sounding explanation if essential for understanding and it can be done unobtrusively.{glossary_segment}
5.  **Formatting:** Preserve paragraph breaks (translate blank lines between paragraphs as blank lines).
6.  **Exclusions:** Do NOT translate or include page markers like '=== Page X ==='. Do not add any explanatory notes or translator comments within the translated text itself.

Input Text (English):
---
{text_to_translate}
---
Translated Text ({target_language}):"""

        # logging.debug(f"Attempt {attempt}: Sending text to Gemini: {text_to_translate[:100]}...")
        response = model.generate_content(prompt)

        if response.parts:
            # logging.debug(f"Attempt {attempt}: Received response from Gemini.")
            return response.text.strip()
        else:
            block_reason = response.prompt_feedback.block_reason if response.prompt_feedback else "Unknown"
            safety_ratings = response.prompt_feedback.safety_ratings if response.prompt_feedback else "N/A"
            error_message = f"An error occurred: Translation result was empty. Block reason: {block_reason}. Safety ratings: {safety_ratings}"
            logging.error(error_message)
            return error_message
    except Exception as e:
        error_message = f"An error occurred during translation (attempt {attempt}): {e}"
        logging.error(error_message, exc_info=True) # إضافة تتبع الخطأ
        if "API key not valid" in str(e):
             logging.critical("Critical Error: The provided API key is not valid. Please check your GEMINI_API_KEY environment variable.")
        return error_message

def read_text_file(filepath: str) -> str | None:
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            return file.read()
    except FileNotFoundError:
        logging.error(f"Error: File not found at {filepath}")
        return None
    except Exception as e:
        logging.error(f"Error reading file {filepath}: {e}", exc_info=True)
        return None

def translate_book_file(api_key: str, filepath: str, target_language: str = "ar", chunk_size: int = TARGET_CHUNK_CHAR_LENGTH) -> str | None:
    if not os.path.exists(filepath):
        logging.error(f"Error: Input file not found at {filepath}")
        return None

    file_extension = os.path.splitext(filepath)[1].lower()
    if file_extension != ".txt":
        logging.error(f"Error: Unsupported file type '{file_extension}'. Currently only .txt files are supported.")
        return None

    original_text = read_text_file(filepath)
    if original_text is None:
        return None

    if not original_text.strip():
        logging.warning(f"Warning: The file {filepath} is empty or contains only whitespace.")
        return ""

    pages_content = re.split(r'(=== Page \d+ ===)', original_text)
    full_translated_text = []
    current_page_number = 0
    text_accumulator_for_page = ""

    logging.info(f"Starting translation of {filepath} by pages...")

    for i, part in enumerate(pages_content):
        part_stripped = part.strip()
        is_page_marker = part_stripped.startswith("===") and part_stripped.endswith("===")

        if is_page_marker:
            if text_accumulator_for_page.strip():
                logging.info(f"Translating content for page {current_page_number} (approx {len(text_accumulator_for_page)} chars)...")
                translated_page_content = _translate_page_content_in_chunks(api_key, text_accumulator_for_page, target_language, chunk_size)
                if "Translation failed" in translated_page_content or "An error occurred:" in translated_page_content:
                     logging.error(f"Translation failed for page {current_page_number}. Error: {translated_page_content}")
                     return f"Translation failed for page {current_page_number}. Error: {translated_page_content}"
                full_translated_text.append(translated_page_content.strip())
                if current_page_number > 0:
                    full_translated_text.append(f"\n\n{current_page_number}\n\n")

            match = re.search(r'=== Page (\d+) ===', part_stripped)
            if match:
                current_page_number = int(match.group(1))
            logging.info(f"Processing Page {current_page_number}")
            text_accumulator_for_page = ""
        else:
            text_accumulator_for_page += part

    if text_accumulator_for_page.strip():
        logging.info(f"Translating content for final page {current_page_number} (approx {len(text_accumulator_for_page)} chars)...")
        translated_page_content = _translate_page_content_in_chunks(api_key, text_accumulator_for_page, target_language, chunk_size)
        if "Translation failed" in translated_page_content or "An error occurred:" in translated_page_content:
            logging.error(f"Translation failed for final page {current_page_number}. Error: {translated_page_content}")
            return f"Translation failed for final page {current_page_number}. Error: {translated_page_content}"
        full_translated_text.append(translated_page_content.strip())
        if current_page_number > 0: # Ensure a page number was actually processed
             full_translated_text.append(f"\n\n{current_page_number}\n\n")


    logging.info("Translation process complete.")
    return "".join(full_translated_text).strip()

def _translate_page_content_in_chunks(api_key: str, page_text: str, target_language: str, chunk_size: int) -> str:
    if not page_text.strip():
        return ""
    paragraphs = re.split(r'(\n\n+)', page_text)
    paragraphs = [p for p in paragraphs if p]
    translated_paragraphs = []
    current_chunk_to_translate = ""

    for i, para_or_break in enumerate(paragraphs):
        is_break = bool(re.fullmatch(r'\n\n+', para_or_break))
        if is_break:
            if current_chunk_to_translate.strip():
                # logging.debug(f"Translating chunk before break: '{current_chunk_to_translate[:50]}...'")
                translated_chunk = _translate_with_retries(api_key, current_chunk_to_translate, target_language)
                if "An error occurred:" in translated_chunk: return translated_chunk
                translated_paragraphs.append(translated_chunk)
                current_chunk_to_translate = ""
            translated_paragraphs.append(para_or_break)
        else:
            if len(current_chunk_to_translate) + len(para_or_break) > chunk_size and current_chunk_to_translate.strip():
                # logging.debug(f"Translating chunk due to size: '{current_chunk_to_translate[:50]}...'")
                translated_chunk = _translate_with_retries(api_key, current_chunk_to_translate, target_language)
                if "An error occurred:" in translated_chunk: return translated_chunk
                translated_paragraphs.append(translated_chunk)
                current_chunk_to_translate = para_or_break
            else:
                if current_chunk_to_translate.strip() and para_or_break.strip():
                    current_chunk_to_translate += "\n" + para_or_break
                else:
                    current_chunk_to_translate += para_or_break
    if current_chunk_to_translate.strip():
        # logging.debug(f"Translating final chunk: '{current_chunk_to_translate[:50]}...'")
        translated_chunk = _translate_with_retries(api_key, current_chunk_to_translate, target_language)
        if "An error occurred:" in translated_chunk: return translated_chunk
        translated_paragraphs.append(translated_chunk)
    return "".join(translated_paragraphs)

def _translate_with_retries(api_key: str, text_chunk: str, target_language: str) -> str:
    for attempt in range(1, MAX_RETRIES + 1):
        # logging.info(f"Translation attempt {attempt}/{MAX_RETRIES} for chunk: '{text_chunk[:50]}...'")
        translated_chunk = translate_text(api_key, text_chunk, target_language, attempt=attempt)
        if "An error occurred:" not in translated_chunk:
            return translated_chunk
        if "API key not valid" in translated_chunk:
            return translated_chunk # Critical error
        if attempt < MAX_RETRIES:
            logging.warning(f"Retrying translation for chunk in {RETRY_DELAY_SECONDS} seconds...")
            time.sleep(RETRY_DELAY_SECONDS)
    logging.error(f"Failed to translate chunk after {MAX_RETRIES} attempts: {text_chunk[:100]}...")
    return f"An error occurred: Failed to translate after {MAX_RETRIES} retries. Last error: {translated_chunk}"

def save_text_to_file(text: str, output_filepath: str) -> bool:
    try:
        with open(output_filepath, 'w', encoding='utf-8') as file:
            file.write(text)
        logging.info(f"Translated text saved to: {output_filepath}")
        return True
    except IOError as e:
        logging.error(f"Error saving file {output_filepath}: {e}", exc_info=True)
        return False
    except Exception as e:
        logging.error(f"An unexpected error occurred while saving {output_filepath}: {e}", exc_info=True)
        return False

if __name__ == '__main__':
    # --- إعداد التسجيل ---
    log_format = '%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    logging.basicConfig(level=logging.INFO, format=log_format, handlers=[
        logging.FileHandler("translator.log", encoding='utf-8'),
        logging.StreamHandler() # لعرض السجلات على الشاشة أيضًا
    ])
    # لإظهار رسائل debug، قم بتغيير level=logging.DEBUG

    API_KEY = os.environ.get("GEMINI_API_KEY")

    if not API_KEY:
        logging.critical("Error: The GEMINI_API_KEY environment variable is not set.")
        # (رسائل print الأصلية كانت جيدة هنا لأن التسجيل قد لا يكون مهيأ بالكامل)
        print("Error: The GEMINI_API_KEY environment variable is not set.")
        print("Please set it before running the script.")
        print("Example (Linux/macOS): export GEMINI_API_KEY='your_api_key_here'")
        print("Example (Windows CMD): set GEMINI_API_KEY=your_api_key_here")
        print("Example (Windows PowerShell): $env:GEMINI_API_KEY='your_api_key_here'")
    else:
        try:
            genai.configure(api_key=API_KEY)
            logging.info("Gemini API Key configured successfully.")
        except Exception as e:
            logging.critical(f"Error configuring Gemini API: {e}", exc_info=True)
            # (رسائل print الأصلية كانت جيدة هنا)
            print(f"Error configuring Gemini API: {e}")
            print("Please ensure your GEMINI_API_KEY is correct and has the necessary permissions.")
            # return بدلاً من sys.exit(1) إذا كانت هذه دالة
            exit() # استخدام exit() هنا لأننا في __main__

        logging.info(f"\n--- Test 1: Basic Text Translation (Test Prompt) ---")
        sample_text_for_prompt_test = "This is a test paragraph.\n\nThis is another paragraph after a blank line.\n=== Page 1 ==="
        translated_sample_text = translate_text(API_KEY, sample_text_for_prompt_test, target_language="ar")
        logging.info(f"Original Sample:\n{sample_text_for_prompt_test}")
        logging.info(f"Translated Sample (ar):\n{translated_sample_text}")

        logging.info(f"\n--- Test 2: File Translation ('document.txt') ---")

        input_filename_main = "document.txt" # هذا هو الملف الرئيسي الذي سنستخدمه

        if not os.path.exists(input_filename_main):
            logging.error(f"Error: Main test file '{input_filename_main}' not found. Creating a dummy file.")
            dummy_content = """=== Page 1 ===
This is the first line of the first paragraph.
This is the second line of the first paragraph.

This is the first line of the second paragraph.
This is a very long sentence to test how chunking behaves when it encounters sentences that might be longer than the ideal chunk size, pushing the boundaries of our segmentation logic and ensuring that the system can gracefully handle such edge cases without losing context or breaking the narrative flow.

=== Page 2 ===
This is a paragraph on the second page.
It has some more text.

Another paragraph to conclude the dummy file.
"""
            with open(input_filename_main, "w", encoding="utf-8") as f:
                f.write(dummy_content)
            logging.info(f"Dummy '{input_filename_main}' created.")

        target_output_filename_main = f"translated_{os.path.splitext(input_filename_main)[0]}_ar.txt"

        logging.info(f"\nTranslating '{input_filename_main}' to '{target_output_filename_main}'...")
        # Using the global TARGET_CHUNK_CHAR_LENGTH for chunk_size
        translated_book_content = translate_book_file(API_KEY, input_filename_main, target_language="ar", chunk_size=TARGET_CHUNK_CHAR_LENGTH)

        if translated_book_content is not None: # Check for None explicitly
            # Check for known error strings from the translation functions
            if "Translation failed" in translated_book_content or \
               ("An error occurred:" in translated_book_content and not translated_book_content.startswith("An error occurred: Translation result was empty")): # Allow empty result error for single small chunks
                logging.error("\n--- Translation Process Encountered an Error ---")
                logging.error(f"Error details: {translated_book_content}")
            elif "Translation result was empty" in translated_book_content:
                logging.warning("\n--- Translation Warning ---")
                logging.warning(f"Warning details: {translated_book_content}")
            else:
                logging.info("\n--- Full Translated Book Content (First 1000 chars) ---")
                logging.info(translated_book_content[:1000] + "..." if len(translated_book_content) > 1000 else translated_book_content)

            if save_text_to_file(translated_book_content, target_output_filename_main):
                logging.info(f"Successfully saved content (or error message) to '{target_output_filename_main}'")
            else:
                logging.error(f"Failed to save content to '{target_output_filename_main}'")
        else:
            # This case primarily occurs if translate_book_file itself returns None (e.g., file not found, unsupported type before translation starts)
            logging.error(f"Failed to translate the book file: {input_filename_main}. No content was returned.")

        # --- Additional Test Cases (as before, can be enabled/disabled) ---
        run_additional_tests = False # Set to True to run these
        if run_additional_tests:
            logging.info(f"\n--- Test 3: Non-existent input file ---")
            translate_book_file(API_KEY, "non_existent_file.txt") # This should print an error and return None

            logging.info(f"\n--- Test 4: Unsupported file type ---")
            empty_pdf_filename = "dummy.pdf"
            with open(empty_pdf_filename, "w", encoding="utf-8") as f: f.write("")
            translate_book_file(API_KEY, empty_pdf_filename) # This should print an error and return None
            if os.path.exists(empty_pdf_filename): os.remove(empty_pdf_filename)

            logging.info(f"\n--- Test 5: Empty input file ---")
            empty_txt_filename = "empty.txt"
            target_empty_translated_filename = f"translated_{empty_txt_filename}"
            with open(empty_txt_filename, "w", encoding="utf-8") as f: f.write("")
            translated_empty_content = translate_book_file(API_KEY, empty_txt_filename) # Should return ""
            if translated_empty_content == "":
                 logging.info(f"Translation of empty file '{empty_txt_filename}' handled correctly.")
            else:
                 logging.error(f"Error: Translation of empty file '{empty_txt_filename}' did not return empty string: '{translated_empty_content}'")
            save_text_to_file(translated_empty_content, target_empty_translated_filename) # Save empty string or error
            if os.path.exists(empty_txt_filename): os.remove(empty_txt_filename)
            if os.path.exists(target_empty_translated_filename): os.remove(target_empty_translated_filename)

        logging.info(f"\n--- Main test completed. Please check '{target_output_filename_main}' and 'translator.log'. ---")
