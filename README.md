# Python Book Translator using Gemini API (Advanced)

This script translates text files (currently `.txt`) from English to Arabic using Google's Gemini API, with a focus on producing high-quality, human-like translations while preserving book structure.

## Features

*   **High-Quality Translation:** Utilizes a detailed prompt engineered for literary translation to achieve natural-sounding Arabic that maintains the original tone and nuances.
*   **Structure Preservation:**
    *   Identifies page markers in the format `=== Page X ===` in the input file.
    *   Removes these markers from the translated output.
    *   Appends the page number at the end of each translated page's content, followed by double newlines for separation.
    *   Preserves paragraph breaks from the source text.
*   **Input/Output:** Takes a `.txt` file as input and produces a `.txt` file with the translated content.
*   **Smart Chunking:**
    *   Processes the book page by page based on `=== Page X ===` markers.
    *   Within each page, if the content is large, it's further chunked by paragraphs to stay within API limits while maintaining context.
*   **Error Handling:**
    *   Includes a retry mechanism for API calls in case of intermittent failures.
    *   Checks for API key validity and other common errors.
*   **Configurable:**
    *   Gemini model (`GEMINI_MODEL_NAME`) can be easily changed (e.g., to `gemini-1.5-pro-latest` for potentially higher quality).
    *   Retry attempts (`MAX_RETRIES`) and delay (`RETRY_DELAY_SECONDS`) are configurable.
    *   Target chunk character length (`TARGET_CHUNK_CHAR_LENGTH`) for intra-page content is configurable.

## Prerequisites

*   Python 3.8+ (due to type hinting like `str | None`, adjust if using older Python)
*   `google-generativeai` Python library. Install it using pip:
    ```bash
    pip install google-generativeai
    ```
*   A Google Gemini API Key.

## Setup

1.  **Clone the repository or download the `translator.py` script.**
2.  **Install the required library:**
    ```bash
    pip install google-generativeai
    ```
3.  **Set your Gemini API Key as an environment variable:**
    This is the most secure way to handle your API key.

    *   **Linux/macOS (bash/zsh):**
        ```bash
        export GEMINI_API_KEY='YOUR_API_KEY_HERE'
        ```
    *   **Windows (Command Prompt):**
        ```bash
        set GEMINI_API_KEY=YOUR_API_KEY_HERE
        ```
    *   **Windows (PowerShell):**
        ```bash
        $env:GEMINI_API_KEY='YOUR_API_KEY_HERE'
        ```
    Replace `YOUR_API_KEY_HERE` with your actual Gemini API key. You might want to add this line to your shell's startup file (e.g., `.bashrc`, `.zshrc`, or PowerShell profile) to set it automatically.

## Usage

The script is designed to be run from the command line. The primary file for translation is expected to be `document.txt` located in the same directory as `translator.py`.

1.  **Prepare your input file:**
    *   Ensure your input text file (e.g., `document.txt`) is in plain text (`.txt`) format.
    *   If your book has page demarcations, use the format `=== Page X ===` (e.g., `=== Page 1 ===`, `=== Page 2 ===`) on their own lines to indicate page breaks. These markers will be used to number pages in the output but will not appear in the translated text itself.
2.  **Run the script:**
    ```bash
    python translator.py
    ```
3.  **Output:**
    *   The script will process `document.txt` (or the file specified in `input_filename_main` within the script).
    *   A translated file named `translated_document_ar.txt` (or similar, based on the input filename) will be created in the same directory. This file will contain the Arabic translation, with page numbers appended at the end of each respective page's content.

### Customizing Input/Output Files

If you wish to use a different input file:
1.  Open `translator.py`.
2.  Locate the `if __name__ == '__main__':` block.
3.  Change the `input_filename_main` variable:
    ```python
    input_filename_main = "your_book_file.txt"
    ```
The output filename will be generated automatically based on this input filename (e.g., `translated_your_book_file_ar.txt`).

### Functions Overview

*   `translate_text(api_key: str, text_to_translate: str, target_language: str = "ar", attempt: int = 1) -> str`:
    Translates a given string of text using a specialized prompt for literary quality.
*   `read_text_file(filepath: str) -> str | None`:
    Reads content from a `.txt` file.
*   `translate_book_file(api_key: str, filepath: str, target_language: str = "ar", chunk_size: int = TARGET_CHUNK_CHAR_LENGTH) -> str | None`:
    The main function that orchestrates reading the book file, processing it page by page, translating content in chunks, and assembling the final translated text with page numbering.
*   `_translate_page_content_in_chunks(api_key: str, page_text: str, target_language: str, chunk_size: int) -> str`:
    A helper function to manage chunking and translation for the content of a single page.
*   `_translate_with_retries(api_key: str, text_chunk: str, target_language: str) -> str`:
    A helper function that wraps `translate_text` to implement a retry mechanism.
*   `save_text_to_file(text: str, output_filepath: str) -> bool`:
    Saves the given text to a specified file.

## Error Handling and Logging

*   The script checks for the `GEMINI_API_KEY` environment variable.
*   It handles `FileNotFoundError` if the input file doesn't exist and provides basic support for unsupported file types (currently only `.txt` is processed).
*   API errors during translation are caught, and retries are attempted. If failures persist, an error message is included in the output or returned.
*   Progress and errors are printed to the console during execution.

## Future Improvements Ideas

*   Support for more input file types (e.g., PDF, DOCX, ePub).
*   More sophisticated UI (e.g., a simple web interface or a desktop GUI) for easier file selection and option configuration.
*   Advanced logging to a file.
*   Batch processing for multiple files.
*   Option to choose target language via command-line arguments.
*   More granular control over API parameters (e.g., temperature, top_p) if needed for fine-tuning translation style.
```
