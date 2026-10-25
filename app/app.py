"""F1 EDA dashboard: is the race decided on Saturday?

Run from the repo root with:  streamlit run app/app.py
"""
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

RED = "#FF2B17"
GREY = "#5C5C66"
LIGHT = "#C8C8D0"
BG = "#15151E"

DATA = Path(__file__).parent / "clean_data.csv"

st.set_page_config(page_title="F1 EDA Dashboard", page_icon="🏁", layout="wide")


@st.cache_data
def load_data():
    df = pd.read_csv(DATA)
    for col in ["finished", "starter", "dnf", "podium", "win"]:
        df[col] = df[col].astype(bool)
    return df


@st.cache_resource
def train_podium_model(df):
    """Same logistic regression as the notebook: podium ~ grid + team + year, 2010-2024."""
    data = df[df["year"].between(2010, 2024) & df["starter"] & df["grid_clean"].notna()].copy()
    top_teams = data.groupby("team")["points"].sum().nlargest(6).index.tolist()
    data["team_group"] = data["team"].where(data["team"].isin(top_teams), "Other")

    prep = ColumnTransformer([
        ("num", StandardScaler(), ["grid_clean", "year"]),
        ("team", OneHotEncoder(handle_unknown="ignore"), ["team_group"]),
    ])
    model = Pipeline([("prep", prep), ("clf", LogisticRegression(max_iter=1000))])
    model.fit(data[["grid_clean", "team_group", "year"]], data["podium"])
    return model, top_teams


def style(fig, height=380):
    """Shared dark look for every Plotly chart."""
    fig.update_layout(template="plotly_dark", paper_bgcolor=BG, plot_bgcolor=BG, height=height,
                      margin=dict(l=10, r=10, t=50, b=10), font=dict(color=LIGHT),
                      hoverlabel=dict(bgcolor="#24242E"))
    fig.update_xaxes(gridcolor="#2E2E38", zeroline=False)
    fig.update_yaxes(gridcolor="#2E2E38", zeroline=False)
    return fig


df = load_data()

# ------------------------------------------------------------------ sidebar
st.sidebar.title("🏁 F1 1950–2024")
st.sidebar.markdown(
    "Every Formula 1 World Championship race result from 1950 to 2024, one row per driver per race. "
    "Data: [Kaggle, Rohan Rao](https://www.kaggle.com/datasets/rohanrao/formula-1-world-championship-1950-2020) "
    "(from the Ergast API)."
)

years = st.sidebar.slider("Seasons", 1950, 2024, (2010, 2024))
in_years = df[df["year"].between(*years)]

# teams sorted by wins in the chosen seasons, so the big names come first
team_options = in_years.groupby("team")["win"].sum().sort_values(ascending=False).index.tolist()
teams = st.sidebar.multiselect("Constructors", team_options, placeholder="All constructors",
                               help="Leave empty to include every constructor.")

circuit_options = ["All circuits"] + sorted(in_years["circuit_name"].dropna().unique())
circuit = st.sidebar.selectbox("Circuit", circuit_options)

f = in_years
if teams:
    f = f[f["team"].isin(teams)]
if circuit != "All circuits":
    f = f[f["circuit_name"] == circuit]

st.sidebar.caption(f"{len(f):,} rows match the filters.")

# ------------------------------------------------------------------ header + KPIs
st.title("Is the race decided on Saturday?")
st.markdown("How much does qualifying decide the result in Formula 1? Use the filters on the left.")

if f.empty:
    st.warning("No rows match these filters. Try a wider season range or fewer filters.")
    st.stop()

wins = f[f["win"]]
starters = f[f["starter"]]
pct = lambda x: f"{x:.0%}" if pd.notna(x) else "n/a"

k1, k2, k3, k4 = st.columns(4)
k1.metric("Races", f"{f['raceId'].nunique():,}")
k2.metric("Pole → win", pct((wins["grid_clean"] == 1).mean() if len(wins) else np.nan),
          help="Share of race wins that started from pole position.")
k3.metric("Front row → win", pct((wins["grid_clean"] <= 2).mean() if len(wins) else np.nan),
          help="Share of race wins that started from P1 or P2.")
k4.metric("DNF rate", pct(starters["dnf"].mean() if len(starters) else np.nan),
          help="Share of starters who did not finish.")

# ------------------------------------------------------------------ charts
c1, c2 = st.columns(2)

with c1:
    fin = f[f["finished"] & f["grid_clean"].notna()]
    fig = go.Figure()
    if len(fin) > 1:
        rng = np.random.default_rng(0)
        fig.add_trace(go.Scattergl(
            x=fin["grid_clean"] + rng.uniform(-0.3, 0.3, len(fin)),
            y=fin["positionOrder"] + rng.uniform(-0.3, 0.3, len(fin)),
            mode="markers", marker=dict(color=GREY, size=4, opacity=0.45),
            customdata=fin[["driver", "race_name", "year", "grid", "positionOrder"]],
            hovertemplate="%{customdata[0]}<br>%{customdata[2]} %{customdata[1]}"
                          "<br>Grid %{customdata[3]} → P%{customdata[4]}<extra></extra>",
            name="finisher"))
        if fin["grid_clean"].nunique() > 1:
            slope, intercept = np.polyfit(fin["grid_clean"], fin["positionOrder"], 1)
            xs = np.array([fin["grid_clean"].min(), fin["grid_clean"].max()])
            fig.add_trace(go.Scatter(x=xs, y=intercept + slope * xs, mode="lines",
                                     line=dict(color=RED, width=4), name="trend", hoverinfo="skip"))
            r = fin["grid_clean"].corr(fin["positionOrder"])
            title = f"Grid vs finish (r = {r:.2f})"
        else:
            title = "Grid vs finish"
    else:
        title = "Grid vs finish (not enough finishers)"
    fig.update_layout(title=title, showlegend=False, xaxis_title="Grid position", yaxis_title="Finishing position")
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(style(fig), theme=None)

with c2:
    team_wins = wins["team"].value_counts().head(10).sort_values()
    fig = go.Figure(go.Bar(
        x=team_wins.values, y=team_wins.index, orientation="h", text=team_wins.values,
        marker_color=[RED if t == team_wins.idxmax() else GREY for t in team_wins.index] if len(team_wins) else [],
        hovertemplate="%{y}: %{x} wins<extra></extra>"))
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(title="Wins by team (top 10)", xaxis_title="Race wins")
    st.plotly_chart(style(fig), theme=None)

c3, c4 = st.columns(2)

with c3:
    by_year = starters.groupby("year").agg(dnf=("dnf", "mean"),
                                           mech=("dnf_type", lambda s: (s == "Mechanical").mean()))
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=by_year.index, y=by_year["dnf"] * 100, mode="lines+markers", name="All DNFs",
                             line=dict(color=RED, width=2.5), hovertemplate="%{x}: %{y:.0f}%<extra>All DNFs</extra>"))
    fig.add_trace(go.Scatter(x=by_year.index, y=by_year["mech"] * 100, mode="lines+markers", name="Mechanical only",
                             line=dict(color=LIGHT, width=2), hovertemplate="%{x}: %{y:.0f}%<extra>Mechanical</extra>"))
    fig.update_layout(title="DNF rate among starters", xaxis_title="Season", yaxis_title="% of starters",
                      legend=dict(orientation="h", y=-0.28, x=0))
    st.plotly_chart(style(fig), theme=None)

with c4:
    top10 = f[f["grid_clean"].between(1, 10)]
    rate = top10.groupby("grid_clean")["podium"].agg(["mean", "size"]).reindex(range(1, 11))
    fig = go.Figure(go.Bar(
        x=[f"P{g}" for g in rate.index], y=rate["mean"] * 100,
        marker_color=[RED] + [GREY] * 9, customdata=rate["size"],
        text=[f"{v:.0%}" if pd.notna(v) else "" for v in rate["mean"]], textposition="outside", cliponaxis=False,
        hovertemplate="%{x}: %{y:.0f}% podium<br>%{customdata} starts<extra></extra>"))
    fig.update_layout(title="Podium rate by grid slot", xaxis_title="Grid slot", yaxis_title="Podium rate (%)",
                      yaxis_range=[0, 105])
    st.plotly_chart(style(fig), theme=None)

# ------------------------------------------------------------------ insights
st.subheader("Insights (2010–2024, all teams)")
st.markdown(
    "- **Qualifying matters most.** The pole sitter won 51% of races and the front row won 77%. "
    "Only 4 of 305 races were won from outside the top 10.\n"
    "- **Grid predicts the finish.** For classified finishers r = 0.78, and two in three finish within "
    "3 places of where they started.\n"
    "- **One team rules each era.** Mercedes won 102 of 138 races from 2014 to 2020, and Red Bull won 21 of 22 in 2023.\n"
    "- **Cars are far more reliable.** About half of all starters retired until the 1980s. In the 2020s it is 14%."
)

# ------------------------------------------------------------------ model widget
st.subheader("Predict podium chance")
model, top_teams = train_podium_model(df)
m1, m2, m3, m4 = st.columns([1, 1, 1, 1])
grid_in = m1.slider("Grid slot", 1, 20, 3)
team_in = m2.selectbox("Team", top_teams + ["Other"])
year_in = m3.slider("Season", 2010, 2024, 2024)
prob = model.predict_proba(pd.DataFrame({"grid_clean": [grid_in], "team_group": [team_in], "year": [year_in]}))[0, 1]
m4.metric("Podium chance", f"{prob:.0%}")
st.caption("Logistic regression trained on 2010–2024 starters (grid, team, year). "
           "It is a simple model, so treat the number as a rough guide.")

# ------------------------------------------------------------------ data
st.subheader("Data preview")
st.dataframe(f.head(100), hide_index=True)

st.subheader("Summary statistics")
num_cols = ["grid_clean", "positionOrder", "points", "laps", "fastest_lap_sec", "fastestLapSpeed"]
st.dataframe(f[num_cols].describe().round(2))
