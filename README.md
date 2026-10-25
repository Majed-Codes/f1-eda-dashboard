# Is the Race Decided on Saturday? F1 EDA + Dashboard

Unit 3 Final Project by **Majed Alotaibi** (AI undergraduate, University of Hail).

An exploratory data analysis of every Formula 1 World Championship race from 1950 to 2024.
The main question is how much qualifying (grid position) decides the result on Sunday.
The project has a cleaning and EDA notebook, an interactive Streamlit dashboard, a PDF report
and an HTML presentation.

## Key findings

1. **Qualifying decides most of the race.** Since 2010 the pole sitter won 51% of races, the front
   row won 77%, and only 4 of 305 races were won from outside the top 10. Grid vs finish correlation
   for classified finishers is 0.78.
2. **One team rules each era.** Mercedes won 102 of 138 races (74%) from 2014 to 2020, and Red Bull
   won 21 of 22 races in 2023.
3. **Cars are far more reliable.** About half of all starters retired until the 1980s. In the 2020s
   it is 14%, and mechanical failures dropped from 38% of starters in the 1950s to 6%.

## Dataset

[Formula 1 World Championship (1950-2020)](https://www.kaggle.com/datasets/rohanrao/formula-1-world-championship-1950-2020)
by Rohan Rao, built from the Ergast API. It is updated past 2020. I use `results`, `races`,
`drivers`, `constructors`, `status` and `circuits`, and keep the 1950-2024 seasons.

The raw CSVs (about 21 MB) are not in the repo. Download them into `data/raw/`:

```bash
kaggle datasets download -d rohanrao/formula-1-world-championship-1950-2020 -p data/raw --unzip
```

Or download the zip from the Kaggle page and unzip it into `data/raw/`.
The cleaned file `data/clean_data.csv` is in the repo, so the dashboard works without the raw data.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Tested with Python 3.11.

## Run the notebook

```bash
jupyter notebook notebook/f1_eda.ipynb
```

Run all cells from top to bottom. The notebook reads `data/raw/`, writes `data/clean_data.csv`
(plus a copy in `app/`), and saves every plot to `reports/figures/`.

## Run the dashboard

```bash
streamlit run app/app.py
```

The dark/red theme is in `app/.streamlit/config.toml`. Streamlit reads the config from the folder
you run the command in, so the same file is also at `.streamlit/config.toml` in the repo root.

## Build the PDF report

```bash
python reports/build_report.py
```

This writes `reports/F1_EDA_Report.pdf` from the figures. To add the dashboard screenshots, save
them as `reports/screenshots/dashboard_1.png`, `dashboard_2.png` and `dashboard_3.png` and run the
script again. Until then the report shows marked placeholders.

## Presentation

Open `presentation/index.html` in a web browser (double-click it). Use the arrow keys to move between slides.

## Project structure

```
f1-eda-dashboard/
├── data/
│   ├── raw/                 # Kaggle CSVs (not in git, see above)
│   └── clean_data.csv
├── notebook/
│   └── f1_eda.ipynb
├── app/
│   ├── app.py
│   ├── clean_data.csv
│   └── .streamlit/config.toml
├── reports/
│   ├── figures/
│   ├── build_report.py
│   └── F1_EDA_Report.pdf
├── presentation/
│   └── index.html
├── Final_Project___Unit_3.pdf
├── requirements.txt
└── README.md
```
