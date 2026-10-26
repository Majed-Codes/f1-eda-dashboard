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

Run all cells from top to bottom. The notebook reads `data/raw/` and writes `data/clean_data.csv`
(plus a copy in `app/`). The styled plots used in the PDF report are in `reports/figures/`.

## Run the dashboard

```bash
streamlit run app/app.py
```

The dashboard has a filter bar at the top (seasons, constructors, circuit) and seven tabs:

- **Qualifying**: win, podium and points rate by grid slot, a grid to result flow, and places gained on Sunday.
- **Dominance**: a bar chart race of wins by team, the leading team's share of wins each season, and the top team
  of each era.
- **Reliability**: DNF rate over time and what ended the race in each decade.
- **Drivers**: pick a driver to see their rates, every race they started (grid against result), how they compare
  with the field, and their career season by season.
- **Predict**: a logistic regression that gives the podium chance for a grid slot, team and season.
- **Play**: the Lights Out Arcade (see below).
- **Data**: the filtered rows and summary statistics.

The charts are animated with [Apache ECharts](https://echarts.apache.org), loaded from the jsDelivr CDN, so the
dashboard needs an internet connection to draw them (everything else works offline).

The dark/red theme is in `app/.streamlit/config.toml`. Streamlit reads the config from the folder
you run the command in, so the same file is also at `.streamlit/config.toml` in the repo root.

### Chibi Max (AI assistant)

Chibi Max is my own chibi drawing of Max Verstappen, and he floats in the corner of the dashboard as the assistant.
He bounces, blinks, follows your mouse with his eyes, and drops the straight face when the mouse gets close. Drag him
anywhere (he remembers where you left him), and double-click him (double-tap on a phone) to open a chat window.
He is a fan drawing, not the real driver, and the assistant is told never to speak for him.

His answers come from Claude (`claude-opus-5-5`), and every number he gives comes from tools that query
`clean_data.csv`, so he does not guess statistics. To turn him on, create `.streamlit/secrets.toml` in the repo root:

```toml
ANTHROPIC_API_KEY = "your-key-here"
```

The file is in `.gitignore`, so the key is never committed. Without a key the rest of the dashboard still works and
Max explains how to add one. Each question costs a few cents of API credit.

The drawing is in `tools/max_drawing.webp`. `python tools/make_max_layers.py` cuts it into the head and body layers
in `app/static/`, which Streamlit serves because `enableStaticServing` is on in the config.

### Lights Out Arcade (mini games)

The **Play** tab has three F1 mini games that use the real grids and results:

- **Lights Out**: react when the five start lights go out. Your reaction turns into places gained or lost from a
  real grid slot, with the real podium chance from your new position.
- **Pit Stop**: change the tyre that lights up, in order, then release the car.
- **Grid Dash**: take a real driver's seat on a real 2000-2024 grid and race the field in their team colours, then
  see what that driver really did.

Play alone, 2 players on one device (shared keyboard or split screen), or an **online championship**: the host
creates a room, friends on the same Wi-Fi scan the QR code, every round is played at the same moment on every phone,
and F1 points (10, 8, 6...) decide the champion.

## Build the PDF report

```bash
python reports/build_report.py
```

This writes `reports/F1_EDA_Report.pdf` from the figures and the dashboard screenshots in
`reports/screenshots/` (`dashboard_1.png`, `dashboard_2.png`, `dashboard_3.png`). To use new
screenshots, replace those files and run the script again.

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
│   ├── app.py               # the dashboard
│   ├── charts.py            # animated ECharts charts
│   ├── game.py              # Lights Out Arcade and online rooms
│   ├── mascot.py            # Chibi Max, the AI assistant
│   ├── static/              # Max's drawing layers
│   ├── arcade/index.html    # the canvas mini games
│   ├── clean_data.csv
│   └── .streamlit/config.toml
├── reports/
│   ├── figures/
│   ├── screenshots/
│   ├── build_report.py
│   └── F1_EDA_Report.pdf
├── tools/
│   ├── max_drawing.webp     # my chibi Max drawing
│   └── make_max_layers.py
├── presentation/
│   └── index.html
├── Final_Project___Unit_3.pdf
├── requirements.txt
└── README.md
```
