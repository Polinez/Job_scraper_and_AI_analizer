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

## Configuration (`config.json`)

Before running the script, you need to set up your preferences in the `config.json` file. Open the file and adjust the following parameters:

* **CV Path:** Update `cv_path_win` (if using Windows) or `cv_path_mac` (if using macOS) with the exact path to your PDF CV file.
* **Job Titles (`job_titles`):** A list of roles and keywords you are looking for (e.g., "Data Scientist", "Python Developer").
* **Experience Levels (`experience_levels`):** Keywords defining your desired seniority (e.g., "Junior", "Intern", "Staż").
* **Exclusions (`exclude_keywords`):** Keywords used to filter out unwanted job postings (e.g., "Senior", "B2B").
* **Location (`location`):** Enter the city where you are looking for a job.
* **Time Limit (`max_days_old`):** Decide how old the downloaded job postings can be (in days, e.g., 2).
* **Remote Work (`remote_only`):** Set to `true` or `false` depending on whether you are interested strictly in remote work.

## Running the Project

**Important!!!!!: Before running the script for the very first time, make sure to delete all files inside the `Data` directory to ensure a clean start.**

Once the configuration is complete, simply execute the script from your terminal:

```bash
python main.py
```

The script will fetch the job offers, and the AI will analyze them based on the skills listed in your CV. All results will be processed and saved automatically.
