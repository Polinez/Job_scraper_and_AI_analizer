# Job Scraper & AI Analyzer

This project automatically scrapes job offers and analyzes them against your CV using Artificial Intelligence to find the best matches.

## Prerequisites
Before you begin, ensure you have the following ready:
* Python 3.13 installed on your machine.
* Your CV saved as a PDF file.
* A free Google AI Studio API key.

## Installation

1. Download this repository as a ZIP file and extract it to a convenient folder.
2. Go to [Google AI Studio](https://aistudio.google.com/api-keys), log in, and generate your API key.
3. In the main project directory (where `main.py` is located), create a new file named `.env`.
4. Open the `.env` file and paste your generated key in the exact format below:

```env
GOOGLE_API_KEY=AIz...
```

5. Install all required dependencies by running the following command in your terminal:

```bash
pip install -r requirements.txt
```

## Configuration (`main.py`)

Before running the script for the first time, you need to adjust `main.py` to fit your needs. Open the file and modify the following parameters:

* **CV Path (`cv_path`):** Locate the conditional statements checking your operating system (Windows or macOS) and change the file path. It must point exactly to your PDF CV file.
* **Search Query (`search`):** Modify this variable to include your desired job titles, keywords (like *Python*, *Data Scientist*), and exclusions (like avoiding *B2B* or *Senior* roles).
* **Location (`location`):** In the `find_jobs` function call, enter the city where you are looking for a job.
* **Time Limit (`h_old`):** Decide how old the downloaded job postings can be (the default is 48 hours).
* **Remote Work (`remote`):** Set to `True` or `False` depending on whether you are interested in remote work.

## Running the Project

**Important!!!!!: Before running the script for the very first time, make sure to delete all files inside the `Data` directory to ensure a clean start.**

Once the configuration is complete, simply execute the script from your terminal:

```bash
python main.py
```

The script will fetch the job offers, and the AI will analyze them based on the skills listed in your CV. All results will be processed and saved automatically.
