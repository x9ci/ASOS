import google.generativeai as genai
import os
import time
import re

# Configuration
GEMINI_MODEL_NAME = "gemini-1.5-flash-latest" # أو "gemini-1.5-pro-latest" لجودة أعلى محتملة
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5
# حجم الجزء التقريبي بالكلمات، يمكن تعديله بناءً على أداء API وسياق النص
# Gemini 1.5 Pro has a context window of up to 1 million tokens. Flash is also large.
# We are more likely to be limited by practical processing time or API rate limits per minute.
# Let's aim for ~5000 characters as a general guideline per chunk, but prioritize semantic breaks.
TARGET_CHUNK_CHAR_LENGTH = 5000

def translate_text(api_key: str, text_to_translate: str, target_language: str = "ar", attempt: int = 1) -> str:
    """
    Translates text to the target language using the Gemini API with improved prompt.

    Args:
        api_key: Your Gemini API key.
        text_to_translate: The text to be translated.
        target_language: The target language code (e.g., "ar" for Arabic).
        attempt: The current retry attempt number (for logging/debugging).

    Returns:
        The translated text, or an error message if translation fails.
    """
    try:
        # Configure API key for each call if not globally configured or if key might change.
        # genai.configure(api_key=api_key) # تم تكوينه مرة واحدة في بداية البرنامج الرئيسي

        model = genai.GenerativeModel(GEMINI_MODEL_NAME)

        # Prompt مصمم لترجمة أدبية شبيهة بالبشر
        prompt = f"""You are an expert literary translator. Your task is to translate the following English text, which is part of a novel, into natural, fluent, and contextually appropriate {target_language}.
Maintain the original tone, style, and nuances. Avoid literal translation and aim for a translation that reads as if it were originally written in {target_language}.
Preserve paragraph breaks (translate blank lines between paragraphs as blank lines).
Do NOT translate or include page markers like '=== Page X ==='.
Input Text:
---
{text_to_translate}
---
Translated Text ({target_language}):"""

        # print(f"Attempt {attempt}: Sending text to Gemini: {text_to_translate[:100]}...") # For debugging
        response = model.generate_content(prompt)

        if response.parts:
            # print(f"Attempt {attempt}: Received response from Gemini.") # For debugging
            return response.text.strip()
        else:
            # Handle cases where the response might be empty or blocked
            block_reason = response.prompt_feedback.block_reason if response.prompt_feedback else "Unknown"
            safety_ratings = response.prompt_feedback.safety_ratings if response.prompt_feedback else "N/A"
            error_message = f"An error occurred: Translation result was empty. Block reason: {block_reason}. Safety ratings: {safety_ratings}"
            print(error_message)
            return error_message

    except Exception as e:
        error_message = f"An error occurred during translation (attempt {attempt}): {e}"
        print(error_message)
        # Check for specific API errors if needed, e.g., quota exceeded, billing issues
        if "API key not valid" in str(e):
             print("Critical Error: The provided API key is not valid. Please check your GEMINI_API_KEY environment variable.")
             # We might want to stop all operations if the API key is invalid.
        return error_message


def read_text_file(filepath: str) -> str | None:
    """Reads content from a .txt file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            return file.read()
    except FileNotFoundError:
        print(f"Error: File not found at {filepath}")
        return None
    except Exception as e:
        print(f"Error reading file {filepath}: {e}")
        return None

def translate_book_file(api_key: str, filepath: str, target_language: str = "ar", chunk_size: int = 2000) -> str | None:
    """
    Reads a text file, translates its content in chunks, and returns the full translated text.

    Args:
        api_key: Your Gemini API key.
        filepath: Path to the text file (.txt).
        target_language: The target language code.
        chunk_size: Approximate target character length for each chunk.
                    The actual chunking will prioritize semantic breaks (paragraphs, page markers).

    Returns:
        The full translated text, or None if an error occurs.
    """
    if not os.path.exists(filepath):
        print(f"Error: Input file not found at {filepath}")
        return None

    file_extension = os.path.splitext(filepath)[1].lower()
    if file_extension != ".txt":
        print(f"Error: Unsupported file type '{file_extension}'. Currently only .txt files are supported.")
        return None

    original_text = read_text_file(filepath)
    if original_text is None: # Error handled in read_text_file
        return None

    if not original_text.strip():
        print(f"Warning: The file {filepath} is empty or contains only whitespace.")
        return "" # Return empty string for empty file content

    # Args:
    #     api_key: Your Gemini API key.
    #     filepath: Path to the text file (.txt).
    #     target_language: The target language code.
    #     chunk_size: Approximate target character length for each chunk.
    #                 The actual chunking will prioritize semantic breaks (paragraphs).

    # Returns:
    #     The full translated text, or None if an error occurs.
    # """
    # if not os.path.exists(filepath):
    #     print(f"Error: Input file not found at {filepath}")
    #     return None

    # file_extension = os.path.splitext(filepath)[1].lower()
    # if file_extension != ".txt":
    #     print(f"Error: Unsupported file type '{file_extension}'. Currently only .txt files are supported.")
    #     return None

    # original_text = read_text_file(filepath)
    # if original_text is None:
    #     return None

    # if not original_text.strip():
    #     print(f"Warning: The file {filepath} is empty or contains only whitespace.")
    #     return ""

    # Split text by page markers first to process page by page
    # (=== Page \d+ ===) is a capturing group to keep the page markers temporarily for page number extraction
    pages_content = re.split(r'(=== Page \d+ ===)', original_text)

    Args:
        api_key: Your Gemini API key.
        filepath: Path to the text file (.txt).
        target_language: The target language code.
        chunk_size: Approximate target character length for each chunk.
                    The actual chunking will prioritize semantic breaks (paragraphs).

    Returns:
        The full translated text, or None if an error occurs.
    """
    if not os.path.exists(filepath):
        print(f"Error: Input file not found at {filepath}")
        return None

    file_extension = os.path.splitext(filepath)[1].lower()
    if file_extension != ".txt":
        print(f"Error: Unsupported file type '{file_extension}'. Currently only .txt files are supported.")
        return None

    original_text = read_text_file(filepath)
    if original_text is None:
        return None

    if not original_text.strip():
        print(f"Warning: The file {filepath} is empty or contains only whitespace.")
        return ""

    # Split text by page markers first to process page by page
    # (=== Page \d+ ===) is a capturing group to keep the page markers temporarily for page number extraction
    pages_content = re.split(r'(=== Page \d+ ===)', original_text)

    full_translated_text = []
    current_page_number = 0

    text_accumulator_for_page = ""

    print(f"Starting translation of {filepath} by pages...")

    for i, part in enumerate(pages_content):
        part_stripped = part.strip()
        is_page_marker = part_stripped.startswith("===") and part_stripped.endswith("===")

        if is_page_marker:
            # If there's accumulated text from the PREVIOUS page, translate and add it
            if text_accumulator_for_page.strip():
                print(f"Translating content for page {current_page_number} (approx {len(text_accumulator_for_page)} chars)...")
                translated_page_content = _translate_page_content_in_chunks(api_key, text_accumulator_for_page, target_language, chunk_size)
                if "Translation failed" in translated_page_content or "An error occurred:" in translated_page_content :
                     return f"Translation failed for page {current_page_number}. Error: {translated_page_content}"
                full_translated_text.append(translated_page_content.strip())
                # Add previous page number
                if current_page_number > 0:
                    full_translated_text.append(f"\n\n{current_page_number}\n\n")

            # Extract new page number
            match = re.search(r'=== Page (\d+) ===', part_stripped)
            if match:
                current_page_number = int(match.group(1))
            print(f"Moving to Page {current_page_number}")
            text_accumulator_for_page = "" # Reset accumulator for the new page
        else:
            # This is content for the current page, add it to accumulator
            text_accumulator_for_page += part

    # Translate any remaining content for the last page
    if text_accumulator_for_page.strip():
        print(f"Translating content for final page {current_page_number} (approx {len(text_accumulator_for_page)} chars)...")
        translated_page_content = _translate_page_content_in_chunks(api_key, text_accumulator_for_page, target_language, chunk_size)
        if "Translation failed" in translated_page_content or "An error occurred:" in translated_page_content:
            return f"Translation failed for final page {current_page_number}. Error: {translated_page_content}"
        full_translated_text.append(translated_page_content.strip())
        # Add the last page number
        if current_page_number > 0:
            full_translated_text.append(f"\n\n{current_page_number}\n\n")

    print("Translation process complete.")
    return "".join(full_translated_text).strip()


def _translate_page_content_in_chunks(api_key: str, page_text: str, target_language: str, chunk_size: int) -> str:
    """
    Helper function to translate the content of a single page, handling chunking by paragraphs.
    """
    if not page_text.strip():
        return ""

    # Split page content by one or more newlines to get paragraphs or text blocks
    paragraphs = re.split(r'(\n\n+)', page_text)
    # Filter out empty strings that might result from split, but keep the newline groups
    paragraphs = [p for p in paragraphs if p]

    translated_paragraphs = []
    current_chunk_to_translate = ""

    for i, para_or_break in enumerate(paragraphs):
        is_break = bool(re.fullmatch(r'\n\n+', para_or_break))

        if is_break:
            # If there's text accumulated, translate it before adding the break
            if current_chunk_to_translate.strip():
                translated_chunk = _translate_with_retries(api_key, current_chunk_to_translate, target_language)
                if "An error occurred:" in translated_chunk: return translated_chunk # Propagate error
                translated_paragraphs.append(translated_chunk)
                current_chunk_to_translate = ""
            translated_paragraphs.append(para_or_break) # Add the paragraph break itself
        else: # It's a text paragraph
            # Check if adding this paragraph exceeds chunk_size (approximate)
            if len(current_chunk_to_translate) + len(para_or_break) > chunk_size and current_chunk_to_translate.strip():
                # Translate the current accumulated chunk
                translated_chunk = _translate_with_retries(api_key, current_chunk_to_translate, target_language)
                if "An error occurred:" in translated_chunk: return translated_chunk
                translated_paragraphs.append(translated_chunk)
                current_chunk_to_translate = para_or_break # Start new chunk with current paragraph
            else:
                # Append paragraph to current chunk, ensure single newline separation if needed
                if current_chunk_to_translate.strip() and para_or_break.strip():
                    current_chunk_to_translate += "\n" + para_or_break # Ensure single newline, not double
                else:
                    current_chunk_to_translate += para_or_break

    # Translate any remaining text in the last chunk
    if current_chunk_to_translate.strip():
        translated_chunk = _translate_with_retries(api_key, current_chunk_to_translate, target_language)
        if "An error occurred:" in translated_chunk: return translated_chunk
        translated_paragraphs.append(translated_chunk)

    return "".join(translated_paragraphs)


def _translate_with_retries(api_key: str, text_chunk: str, target_language: str) -> str:
    """Helper function to handle retries for translate_text."""
    for attempt in range(1, MAX_RETRIES + 1):
        translated_chunk = translate_text(api_key, text_chunk, target_language, attempt=attempt)
        if "An error occurred:" not in translated_chunk:
            return translated_chunk
        if "API key not valid" in translated_chunk: # Critical error, no point retrying
            return translated_chunk
        if attempt < MAX_RETRIES:
            print(f"Retrying in {RETRY_DELAY_SECONDS} seconds...")
            time.sleep(RETRY_DELAY_SECONDS)
    print(f"Failed to translate chunk after {MAX_RETRIES} attempts: {text_chunk[:100]}...")
    return f"An error occurred: Failed to translate after {MAX_RETRIES} retries. Last error: {translated_chunk}"


def save_text_to_file(text: str, output_filepath: str) -> bool:
    """Saves the given text to a file."""
    try:
        with open(output_filepath, 'w', encoding='utf-8') as file:
            file.write(text)
        print(f"Translated text saved to: {output_filepath}")
        return True
    except IOError as e:
        print(f"Error saving file {output_filepath}: {e}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred while saving {output_filepath}: {e}")
        return False

if __name__ == '__main__':
    API_KEY = os.environ.get("GEMINI_API_KEY")

    if not API_KEY:
        print("Error: The GEMINI_API_KEY environment variable is not set.")
        print("Please set it before running the script.")
        print("Example (Linux/macOS): export GEMINI_API_KEY='your_api_key_here'")
        print("Example (Windows CMD): set GEMINI_API_KEY=your_api_key_here")
        print("Example (Windows PowerShell): $env:GEMINI_API_KEY='your_api_key_here'")
    else:
        # --- تكوين Gemini API Key ---
        try:
            genai.configure(api_key=API_KEY)
            print("Gemini API Key configured successfully.")
        except Exception as e:
            print(f"Error configuring Gemini API: {e}")
            print("Please ensure your GEMINI_API_KEY is correct and has the necessary permissions.")
            return # Exit if API key is not configured

        # --- Test 1: Basic Text Translation (Optional, can be commented out) ---
        print(f"\n--- Test 1: Basic Text Translation (Test Prompt) ---")
        sample_text_for_prompt_test = "This is a test paragraph.\n\nThis is another paragraph after a blank line.\n=== Page 1 ==="
        translated_sample_text = translate_text(API_KEY, sample_text_for_prompt_test, target_language="ar")
        print(f"Original Sample:\n{sample_text_for_prompt_test}")
        print(f"Translated Sample (ar):\n{translated_sample_text}")

        # --- Test 2: File Translation using 'document.txt' ---
        print(f"\n--- Test 2: File Translation ('document.txt') ---")

        input_filename_main = "document.txt" # هذا هو الملف الرئيسي الذي سنستخدمه

        if not os.path.exists(input_filename_main):
            print(f"Error: Main test file '{input_filename_main}' not found. Please ensure it exists in the same directory.")
            # Create a dummy document.txt if it doesn't exist for basic testing
            print(f"Creating a dummy '{input_filename_main}' for testing purposes.")
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
            print(f"Dummy '{input_filename_main}' created.")

        target_output_filename_main = f"translated_{os.path.splitext(input_filename_main)[0]}_ar.txt"

        print(f"\nTranslating '{input_filename_main}' to '{target_output_filename_main}'...")
        # Using the global TARGET_CHUNK_CHAR_LENGTH for chunk_size
        translated_book_content = translate_book_file(API_KEY, input_filename_main, target_language="ar", chunk_size=TARGET_CHUNK_CHAR_LENGTH)

        if translated_book_content:
            # Check for known error strings from the translation functions
            if "Translation failed" in translated_book_content or \
               "An error occurred:" in translated_book_content and not translated_book_content.startswith("An error occurred: Translation result was empty"): # Allow empty result error for single small chunks
                print("\n--- Translation Process Encountered an Error ---")
                print(f"Error details: {translated_book_content}")
                print(f"Full content might not be translated or accurate. Check logs/output file for details.")
                # Save whatever was translated, or the error message
                save_text_to_file(translated_book_content, target_output_filename_main)
            elif "Translation result was empty" in translated_book_content:
                print("\n--- Translation Warning ---")
                print(f"Warning details: {translated_book_content}")
                print(f"Some parts might be empty. Check output file.")
                save_text_to_file(translated_book_content, target_output_filename_main)
            else:
                print("\n--- Full Translated Book Content (First 1000 chars) ---")
                print(translated_book_content[:1000] + "..." if len(translated_book_content) > 1000 else translated_book_content)
                if save_text_to_file(translated_book_content, target_output_filename_main):
                    print(f"Successfully saved translated content to '{target_output_filename_main}'")
                else:
                    print(f"Failed to save translated content to '{target_output_filename_main}'")
        else:
            # This case might occur if read_text_file returns None or other pre-translation errors.
            print(f"Failed to translate the book file: {input_filename_main}. No content was returned from translate_book_file.")

        # --- Additional Test Cases (as before, can be enabled/disabled) ---
        run_additional_tests = False # Set to True to run these
        if run_additional_tests:
            print(f"\n--- Test 3: Non-existent input file ---")
            translate_book_file(API_KEY, "non_existent_file.txt")

            print(f"\n--- Test 4: Unsupported file type ---")
            empty_pdf_filename = "dummy.pdf"
            with open(empty_pdf_filename, "w", encoding="utf-8") as f: f.write("")
            translate_book_file(API_KEY, empty_pdf_filename)
            if os.path.exists(empty_pdf_filename): os.remove(empty_pdf_filename)

            print(f"\n--- Test 5: Empty input file ---")
            empty_txt_filename = "empty.txt"
            with open(empty_txt_filename, "w", encoding="utf-8") as f: f.write("")
            translated_empty_content = translate_book_file(API_KEY, empty_txt_filename)
            if translated_empty_content == "":
                 print(f"Translation of empty file '{empty_txt_filename}' handled correctly.")
            else:
                 print(f"Error: Translation of empty file '{empty_txt_filename}' did not return empty string: '{translated_empty_content}'")
            save_text_to_file(translated_empty_content, f"translated_{empty_txt_filename}")
            if os.path.exists(empty_txt_filename): os.remove(empty_txt_filename)
            if os.path.exists(f"translated_{empty_txt_filename}"): os.remove(f"translated_{empty_txt_filename}")

        print(f"\n--- Main test completed. Please check '{target_output_filename_main}' for the translated output. ---")
