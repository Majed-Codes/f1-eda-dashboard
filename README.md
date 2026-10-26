# Is the race decided on Saturday?

Unit 3 final project

- Dashboard: https://f1-eda-dashboard-q4ra9nh4rp59mufhrbpm4r.streamlit.app
- Presentation: https://majed-codes.github.io/f1-eda-dashboard/presentation/

EDA on every F1 race from 1950 to 2024, checking how much qualifying decides the result.

## Findings

1. Since 2010 pole won 51% of races and the front row won 77%.
2. Every era has a top team. Mercedes won 74% of races from 2014 to 2020.
3. Cars break way less. DNFs went from about half the field to 14%.

## Data

[Formula 1 World Championship](https://www.kaggle.com/datasets/rohanrao/formula-1-world-championship-1950-2020) by Rohan Rao on Kaggle.
Put the raw CSVs in `data/raw/`. The clean file is already in `data/clean_data.csv`.

## Run it

```bash
pip install -r requirements.txt
jupyter notebook notebook/f1_eda.ipynb
streamlit run app/app.py
```

The presentation is `presentation/index.html`, open it in a browser.
