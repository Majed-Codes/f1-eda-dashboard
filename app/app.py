import os

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from sklearn.linear_model import LogisticRegression

#run it with: streamlit run app/app.py

st.set_page_config(page_title='F1 EDA Dashboard', page_icon='🏁', layout='wide')

red = '#FF2B17'


#load the data once so the app doesnt read the csv every time a filter changes
@st.cache_data
def load_data():
    path = os.path.join(os.path.dirname(__file__), 'clean_data.csv')
    return pd.read_csv(path)


df = load_data()

# ---------------- sidebar ----------------
st.sidebar.title('🏁 F1 1950–2024')
st.sidebar.header('About the data')
st.sidebar.write('Every Formula 1 race result from 1950 to 2024, one row per driver per race. '
                 'Data: [Kaggle, Rohan Rao](https://www.kaggle.com/datasets/rohanrao/formula-1-world-championship-1950-2020) '
                 '(from the Ergast API).')

st.sidebar.header('Filters')
years = st.sidebar.slider('Seasons', 1950, 2024, (2010, 2024))
df_years = df[(df['year'] >= years[0]) & (df['year'] <= years[1])]

#teams with the most wins come first in the list
team_list = df_years.groupby('team')['win'].sum().sort_values(ascending=False).index.tolist()
teams = st.sidebar.multiselect('Constructors', team_list, placeholder='All constructors',
                               help='Leave empty to include every constructor.')

circuit_list = ['All circuits'] + sorted(df_years['circuit_name'].unique())
circuit = st.sidebar.selectbox('Circuit', circuit_list)

filtered = df_years
if len(teams) > 0:
    filtered = filtered[filtered['team'].isin(teams)]
if circuit != 'All circuits':
    filtered = filtered[filtered['circuit_name'] == circuit]

st.sidebar.caption(str(len(filtered)) + ' rows match the filters.')

# ---------------- title + KPIs ----------------
st.title('Is the race decided on Saturday?')
st.write('How much does qualifying decide the result in Formula 1? Use the filters on the left.')

if len(filtered) == 0:
    st.warning('No rows match these filters. Try a wider season range or fewer filters.')
    st.stop()

wins = filtered[filtered['win'] == True]
starters = filtered[filtered['starter'] == True]

col1, col2, col3, col4 = st.columns(4)
col1.metric('Races', filtered['raceId'].nunique())
if len(wins) > 0:
    col2.metric('Pole → win', str(round((wins['grid_clean'] == 1).mean() * 100)) + '%',
                help='Share of race wins that started from pole position.')
    col3.metric('Front row → win', str(round((wins['grid_clean'] <= 2).mean() * 100)) + '%',
                help='Share of race wins that started from P1 or P2.')
else:
    col2.metric('Pole → win', 'n/a')
    col3.metric('Front row → win', 'n/a')
col4.metric('DNF rate', str(round(starters['dnf'].mean() * 100)) + '%',
            help='Share of starters who did not finish.')

# ---------------- charts ----------------
col1, col2 = st.columns(2)

#grid vs finish scatter with a trend line
finishers = filtered[(filtered['finished'] == True) & (filtered['grid_clean'].notna())].copy()
finishers['grid_jitter'] = finishers['grid_clean'] + np.random.uniform(-0.3, 0.3, len(finishers))
finishers['finish_jitter'] = finishers['positionOrder'] + np.random.uniform(-0.3, 0.3, len(finishers))

title = 'Grid vs finish'
if finishers['grid_clean'].nunique() > 1:
    title = 'Grid vs finish (r = ' + str(round(finishers['grid_clean'].corr(finishers['positionOrder']), 2)) + ')'

fig = px.scatter(finishers, x='grid_jitter', y='finish_jitter', opacity=0.45, title=title,
                 hover_data=['driver', 'race_name', 'year', 'grid', 'positionOrder'],
                 labels={'grid_jitter': 'Grid position', 'finish_jitter': 'Finishing position'})
fig.update_traces(marker=dict(color='grey', size=4))
if finishers['grid_clean'].nunique() > 1:
    slope, intercept = np.polyfit(finishers['grid_clean'], finishers['positionOrder'], 1)
    x_line = [finishers['grid_clean'].min(), finishers['grid_clean'].max()]
    y_line = [intercept + slope * x_line[0], intercept + slope * x_line[1]]
    fig.add_scatter(x=x_line, y=y_line, mode='lines', line=dict(color=red, width=4), name='trend')
fig.update_yaxes(autorange='reversed')
fig.update_layout(template='plotly_dark', showlegend=False)
col1.plotly_chart(fig)

#wins by team
team_wins = wins['team'].value_counts().head(10).sort_values()
colors = ['grey'] * len(team_wins)
if len(team_wins) > 0:
    colors[-1] = red
fig = px.bar(x=team_wins.values, y=team_wins.index, orientation='h', text=team_wins.values,
             title='Wins by team (top 10)', labels={'x': 'Race wins', 'y': ''})
fig.update_traces(marker_color=colors)
fig.update_layout(template='plotly_dark')
col2.plotly_chart(fig)

col1, col2 = st.columns(2)

#DNF rate per season
dnf_year = starters.groupby('year')['dnf'].mean() * 100
mech_year = starters.groupby('year')['dnf_type'].apply(lambda x: (x == 'Mechanical').mean()) * 100
dnf_df = pd.DataFrame({'All DNFs': dnf_year, 'Mechanical only': mech_year})

fig = px.line(dnf_df, markers=True, title='DNF rate among starters',
              labels={'year': 'Season', 'value': '% of starters', 'variable': ''},
              color_discrete_sequence=[red, 'white'])
fig.update_layout(template='plotly_dark', legend=dict(orientation='h', y=-0.25))
col1.plotly_chart(fig)

#podium rate by grid slot
top10_grid = filtered[(filtered['grid_clean'] >= 1) & (filtered['grid_clean'] <= 10)]
podium_rate = top10_grid.groupby('grid_clean')['podium'].mean() * 100
podium_rate = podium_rate.reindex(range(1, 11)).fillna(0)

fig = px.bar(x=['P' + str(i) for i in range(1, 11)], y=podium_rate.values,
             text=[str(round(v)) + '%' for v in podium_rate],
             title='Podium rate by grid slot', labels={'x': 'Grid slot', 'y': 'Podium rate (%)'})
fig.update_traces(marker_color=[red] + ['grey'] * 9, textposition='outside')
fig.update_layout(template='plotly_dark', yaxis_range=[0, 105])
col2.plotly_chart(fig)

# ---------------- insights ----------------
st.subheader('Insights (2010–2024, all teams)')
st.markdown('''
- **Qualifying matters most.** The pole sitter won 51% of races and the front row won 77%. Only 4 of 305 races were won from outside the top 10.
- **Grid predicts the finish.** For classified finishers r = 0.78, and two in three finish within 3 places of where they started.
- **One team rules each era.** Mercedes won 102 of 138 races from 2014 to 2020, and Red Bull won 21 of 22 in 2023.
- **Cars are far more reliable.** About half of all starters retired until the 1980s. In the 2020s it is 14%.
''')


# ---------------- predict podium chance ----------------
#same model as the notebook: podium from grid, team and year (2010-2024)
@st.cache_resource
def train_model():
    model_df = df[(df['year'] >= 2010) & (df['starter'] == True) & (df['grid_clean'].notna())].copy()
    top_teams = model_df.groupby('team')['points'].sum().sort_values(ascending=False).head(6).index.tolist()
    model_df['team_group'] = model_df['team']
    model_df.loc[~model_df['team'].isin(top_teams), 'team_group'] = 'Other'

    X = pd.get_dummies(model_df[['grid_clean', 'team_group', 'year']])
    y = model_df['podium']
    model = LogisticRegression(max_iter=1000)
    model.fit(X, y)
    return model, top_teams, X.columns


model, top_teams, model_columns = train_model()

st.subheader('Predict podium chance')
col1, col2, col3, col4 = st.columns(4)
grid_in = col1.slider('Grid slot', 1, 20, 3)
team_in = col2.selectbox('Team', top_teams + ['Other'])
year_in = col3.slider('Season', 2010, 2024, 2024)

new_row = pd.DataFrame({'grid_clean': [grid_in], 'team_group': [team_in], 'year': [year_in]})
new_row = pd.get_dummies(new_row).reindex(columns=model_columns, fill_value=0)
chance = model.predict_proba(new_row)[0, 1]
col4.metric('Podium chance', str(round(chance * 100)) + '%')
st.caption('Logistic regression trained on 2010–2024 starters (grid, team, year). '
           'It is a simple model, so treat the number as a rough guide.')

# ---------------- data ----------------
st.subheader('Data preview')
st.dataframe(filtered.head(100), hide_index=True)

st.subheader('Summary statistics')
st.dataframe(filtered[['grid_clean', 'positionOrder', 'points', 'laps', 'fastest_lap_sec', 'fastestLapSpeed']].describe().round(2))
