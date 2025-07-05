import google.generativeai as genai

def translate_text(api_key: str, text_to_translate: str, target_language: str = "ar") -> str:
    """
    Translates text to the target language using the Gemini API.

    Args:
        api_key: Your Gemini API key.
        text_to_translate: The text to be translated.
        target_language: The target language code (e.g., "ar" for Arabic).

    Returns:
        The translated text, or an error message if translation fails.
    """
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro')
        prompt = f"Translate the following text to {target_language}: {text_to_translate}"
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"An error occurred: {e}"

import os

# --- وظيفة الترجمة الأساسية (موجودة بالفعل) ---
# def translate_text(api_key: str, text_to_translate: str, target_language: str = "ar") -> str:
# ... (الكود السابق لدالة translate_text)


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
        chunk_size: Max number of characters to send per API request.
                     Adjust based on API limits and typical paragraph sizes.

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

    translated_parts = []
    current_position = 0
    total_length = len(original_text)
    chunk_number = 0

    print(f"Starting translation of {filepath} ({total_length} characters)...")
    while current_position < total_length:
        chunk_number += 1
        end_of_chunk = min(current_position + chunk_size, total_length)

        actual_end = original_text.rfind('\n', current_position, end_of_chunk) + 1
        if actual_end <= current_position:
             actual_end = original_text.rfind('.', current_position, end_of_chunk) + 1
             if actual_end <= current_position:
                 actual_end = end_of_chunk

        text_chunk = original_text[current_position:actual_end].strip()

        if not text_chunk:
            current_position = actual_end
            continue

        print(f"Translating chunk {chunk_number} (characters {current_position}-{actual_end-1}/{total_length})...")

        try:
            translated_chunk = translate_text(api_key, text_chunk, target_language)
            if "An error occurred:" in translated_chunk:
                # This check is based on the current error string from translate_text
                # It might be better for translate_text to raise an exception
                print(f"API Error translating chunk {chunk_number}: {translated_chunk}")
                # Option: retry logic here?
                # For now, we append the error or a placeholder and continue
                # translated_parts.append(f"[--ERROR IN CHUNK {chunk_number}--]")
                return f"Translation failed due to an API error in chunk {chunk_number}: {translated_chunk}" # Stop all translation
            translated_parts.append(translated_chunk)
        except Exception as e:
            print(f"Critical error during translation of chunk {chunk_number}: {e}")
            # return f"Translation failed due to a critical error in chunk {chunk_number}." # Stop all translation
            translated_parts.append(f"[--CRITICAL ERROR IN CHUNK {chunk_number}--]") # Or try to continue

        current_position = actual_end
        # import time # Add at the top of the file
        # time.sleep(1) # Basic rate limiting if needed

    print("Translation process complete.")
    return "\n".join(translated_parts)

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
        # --- Test 1: Basic Text Translation ---
        print(f"\n--- Test 1: Basic Text Translation ---")
        text_to_translate = "Hello, world! This is a test of the translation function. This should be translated to Arabic."
        translated_text = translate_text(API_KEY, text_to_translate, target_language="ar")
        print(f"Original: {text_to_translate}")
        print(f"Translated (ar): {translated_text}")

        # --- Test 2: File Translation ---
        print(f"\n--- Test 2: File Translation ---")
        test_file_content = """First paragraph.
This is a sample text that will be used to test the file translation functionality.
It includes multiple lines and paragraphs.

Second paragraph.
The purpose is to ensure that the text is read correctly, chunked if necessary,
translated by the Gemini API, and then reassembled accurately.
We are also checking if newlines are preserved.

Let's add a very long sentence to see how chunking might behave or if the API handles it well within a reasonable chunk size: The quick brown fox jumps over the lazy dog near the bank of the river, and this event, while seemingly trivial, is often used in typography and font testing to display all the letters of the alphabet, ensuring that each character is rendered correctly and legibly across various display mediums.

Final paragraph.
End of test content.
"""
        test_input_filename = "sample_book_to_translate.txt"
        with open(test_input_filename, "w", encoding="utf-8") as f:
            f.write(test_file_content)
        print(f"Created a sample input file: {test_input_filename}")

        target_output_filename = "translated_sample_book.txt"

        print(f"\nTranslating '{test_input_filename}' to '{target_output_filename}'...")
        translated_book_content = translate_book_file(API_KEY, test_input_filename, target_language="ar", chunk_size=1500) # Smaller chunk size for testing

        if translated_book_content:
            if "Translation failed due to an API error" in translated_book_content or \
               "CRITICAL ERROR IN CHUNK" in translated_book_content:
                print("\n--- Partial or Failed Translation Output ---")
                print(translated_book_content)
                print(f"There was an error during translation. Full content might not be saved or accurate.")
            else:
                print("\n--- Full Translated Book Content (First 500 chars) ---")
                print(translated_book_content[:500] + "..." if len(translated_book_content) > 500 else translated_book_content)

            save_text_to_file(translated_book_content, target_output_filename)
        else:
            # This case might occur if read_text_file returns None or other pre-translation errors.
            print(f"Failed to translate the book file: {test_input_filename}. No content was returned.")

        # --- Test 3: Non-existent file ---
        print(f"\n--- Test 3: Non-existent input file ---")
        translate_book_file(API_KEY, "non_existent_file.txt")

        # --- Test 4: Unsupported file type ---
        print(f"\n--- Test 4: Unsupported file type ---")
        empty_pdf_filename = "dummy.pdf"
        with open(empty_pdf_filename, "w") as f: # Create dummy pdf for test
            f.write("")
        translate_book_file(API_KEY, empty_pdf_filename)
        os.remove(empty_pdf_filename) # Clean up dummy pdf

        # --- Test 5: Empty input file ---
        print(f"\n--- Test 5: Empty input file ---")
        empty_txt_filename = "empty.txt"
        with open(empty_txt_filename, "w") as f:
            f.write("")
        translated_empty_content = translate_book_file(API_KEY, empty_txt_filename)
        if translated_empty_content == "":
             print(f"Translation of empty file '{empty_txt_filename}' handled correctly (returned empty string).")
        else:
             print(f"Error: Translation of empty file '{empty_txt_filename}' did not return empty string.")
        save_text_to_file(translated_empty_content, f"translated_{empty_txt_filename}")
        os.remove(empty_txt_filename)


        # To keep the main sample files for review:
        # print(f"\nInput file '{test_input_filename}' and output file '{target_output_filename}' (if successful) are kept for review.")
        # If you want to automatically clean them up:
        # if os.path.exists(test_input_filename):
        #     os.remove(test_input_filename)
        # if os.path.exists(target_output_filename):
        #     os.remove(target_output_filename)
