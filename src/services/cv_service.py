import re
import pdfplumber
from pathlib import Path
from src.utils.logger import logger

class CVService:
    def __init__(self, data_dir: str = "Data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)

    def clean_text(self, text: str) -> str:
        if not text:
            return ""
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        # Fix split words (example: "P y t h o n")
        text = re.sub(r'(?<=\b[A-Za-z]) (?=[A-Za-z]\b)', '', text)
        return text.strip()

    def load_cv_text(self, cv_path: Path) -> str:
        if not cv_path.exists():
            logger.error(f"Plik CV nie istnieje: {cv_path}")
            raise FileNotFoundError(f"Nie znaleziono pliku CV: {cv_path}")

        full_text = ""
        try:
            with pdfplumber.open(cv_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text(x_tolerance=2, layout=True)
                    if text:
                        full_text += text + "\n"

            cleaned_text = self.clean_text(full_text)
            if not cleaned_text:
                logger.warning(f"Nie znaleziono tekstu w pliku PDF: {cv_path}")
                return ""

            # Save processed text for debugging/reference
            txt_path = self.data_dir / "cvText.txt"
            with open(txt_path, 'w', encoding='utf-8') as txt_file:
                txt_file.write(full_text)
            
            logger.info(f"Tekst CV zapisany do '{txt_path}'")
            return full_text

        except Exception as e:
            logger.exception(f"Błąd podczas odczytu pliku PDF: {e}")
            return ""
