import os
import re
import pdfplumber

def clean_text(text: str) -> str:
    if not text:
        return ""

    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'(?<=\b[A-Za-z]) (?=[A-Za-z]\b)', '', text)

    return text.strip()

def load_cv_text(cv_path: str) -> str:
    # check if file exists
    if not os.path.exists(cv_path):
        raise FileNotFoundError(f"❌ Error: file do not exist {cv_path}")

    full_text = ""

    try:
        with pdfplumber.open(cv_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text(x_tolerance=2, layout=True) # tolerate 2 pixel spacing between characters

                if text:
                    full_text += text + "\n"

        # Additional cleaning
        cleaned_text = clean_text(full_text)

        # clean up text form extra spaces
        if not cleaned_text:
            print("⚠️ Warning: No text found in the PDF file.")
            return ""

        # save to txt file
        txt_path = cv_path.rsplit('.', 1)[0] + '.txt'
        with open(txt_path, 'w', encoding='utf-8') as txt_file:
            txt_file.write(full_text)
        print(f"✅ CV text saved to '{txt_path}'")

        return full_text

    except Exception as e:
        print(f"❌ Błąd podczas odczytu pliku PDF: {e}")
        return ""