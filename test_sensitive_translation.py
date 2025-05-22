from deep_translator import GoogleTranslator

problematic_phrase_en = "So the bright light at the end of the tunnel is the light coming through into the female vag…"

try:
    # Initialize translator
    translator = GoogleTranslator(source='en', target='ar')
    
    # Translate the phrase
    translated_phrase_ar = translator.translate(problematic_phrase_en)
    
    print(f"Original English: {problematic_phrase_en}")
    print(f"Translated Arabic: {translated_phrase_ar}")

except Exception as e:
    print(f"An error occurred: {e}")
