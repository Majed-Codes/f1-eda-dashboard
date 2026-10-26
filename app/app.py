import os

import numpy as np
import pandas as pd
import streamlit as st
from sklearn.linear_model import LogisticRegression

import charts
import game
import mascot

# run it with: streamlit run app/app.py

st.set_page_config(page_title='Lights Out · F1 1950–2024', page_icon='🏁', layout='wide')

# colors: one red accent, everything else is grey
RED = '#FF2B17'
INK = '#F5F5F7'
MUTED = '#A1A1A6'
FAINT = '#6E6E73'
GREY = '#3A3A41'
SURFACE = '#141418'
BG = '#0A0A0C'
FONT = "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Helvetica Neue', Arial, sans-serif"

st.markdown(f"""
<style>
[data-testid="stHeader"], [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="stDecoration"] {{ display: none; }}
[data-testid="stMainBlockContainer"], .block-container {{ max-width: 1240px; padding-top: 1rem; padding-bottom: 5rem; }}

/* soft red glow behind the hero */
[data-testid="stMain"]::before {{ content: ''; position: absolute; top: -260px; left: 50%; transform: translateX(-50%);
  width: 1100px; height: 700px; pointer-events: none;
  background: radial-gradient(closest-side, rgba(255,43,23,0.16), rgba(255,43,23,0.04) 55%, transparent); }}

/* frosted filter bar pinned to the top */
[data-testid="stLayoutWrapper"]:has(> .st-key-filterbar) {{ position: sticky; top: 12px; z-index: 999; }}
.st-key-filterbar {{ padding: 12px 18px 6px; margin-bottom: 40px;
  background: rgba(22,22,27,0.72); backdrop-filter: saturate(180%) blur(22px); -webkit-backdrop-filter: saturate(180%) blur(22px);
  border: 1px solid rgba(255,255,255,0.08); border-radius: 20px; box-shadow: 0 10px 40px rgba(0,0,0,0.35); }}
.st-key-filterbar label p {{ color: {FAINT} !important; font-size: 12px !important; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; }}
.brand {{ color: {INK}; font-size: 22px; font-weight: 700; letter-spacing: -0.03em; line-height: 1.1; padding-top: 16px; white-space: nowrap; }}
.brand span {{ color: {RED}; }}
.brand-sub {{ color: {FAINT}; font-size: 12px; margin-top: 2px; white-space: nowrap; }}
.st-key-filterbar [data-testid="stButton"] {{ padding-top: 26px; }}
.st-key-filterbar [data-testid="stButton"] button p {{ white-space: nowrap; }}

/* five start lights: on one by one, then all out */
.lights {{ display: flex; gap: 12px; margin: 30px 0 26px 0; }}
.light {{ width: 20px; height: 20px; border-radius: 50%; background: #1C1C22; box-shadow: inset 0 0 0 1px rgba(255,255,255,0.06);
  animation-name: lamp; animation-fill-mode: both; animation-timing-function: linear; }}
.light:nth-child(1) {{ animation-delay: 0.3s; animation-duration: 3.2s; }}
.light:nth-child(2) {{ animation-delay: 0.8s; animation-duration: 2.7s; }}
.light:nth-child(3) {{ animation-delay: 1.3s; animation-duration: 2.2s; }}
.light:nth-child(4) {{ animation-delay: 1.8s; animation-duration: 1.7s; }}
.light:nth-child(5) {{ animation-delay: 2.3s; animation-duration: 1.2s; }}
@keyframes lamp {{
  0% {{ background: #1C1C22; box-shadow: inset 0 0 0 1px rgba(255,255,255,0.06); }}
  1%, 97% {{ background: {RED}; box-shadow: 0 0 22px rgba(255,43,23,0.75), inset 0 0 0 1px rgba(255,255,255,0.15); }}
  100% {{ background: #1C1C22; box-shadow: inset 0 0 0 1px rgba(255,255,255,0.06); }} }}
@media (prefers-reduced-motion: reduce) {{ .light {{ animation: none; }} }}

.eyebrow {{ color: {RED}; font-size: 13px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 10px; }}
.hero-title {{ color: {INK}; font-size: clamp(40px, 6vw, 72px); font-weight: 700; letter-spacing: -0.035em; line-height: 1.02; margin: 0 0 18px 0; }}
.hero-answer {{ color: {INK}; font-size: clamp(22px, 2.6vw, 30px); font-weight: 600; letter-spacing: -0.02em; margin: 0 0 6px 0; }}
.hero-sub {{ color: {MUTED}; font-size: 19px; line-height: 1.5; max-width: 760px; margin: 0 0 8px 0; }}
.hero-meta {{ color: {FAINT}; font-size: 14px; margin: 14px 0 34px 0; }}

.stat-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 14px; margin-bottom: 44px; }}
.stat {{ background: linear-gradient(180deg, #17171C, {SURFACE}); border: 1px solid rgba(255,255,255,0.07); border-radius: 20px;
  padding: 22px 24px 20px; transition: transform .25s ease, border-color .25s ease; }}
.stat:hover {{ transform: translateY(-3px); border-color: rgba(255,255,255,0.16); }}
.stat.glow {{ border-color: rgba(255,43,23,0.35); box-shadow: 0 0 0 1px rgba(255,43,23,0.08), 0 18px 50px -20px rgba(255,43,23,0.45); }}
.stat-label {{ color: {MUTED}; font-size: 14px; font-weight: 500; margin-bottom: 10px; }}
.stat-value {{ color: {INK}; font-size: 46px; font-weight: 600; letter-spacing: -0.03em; line-height: 1; }}
.stat-value.accent {{ color: {RED}; }}
@property --n {{ syntax: '<integer>'; initial-value: 0; inherits: false; }}
.count {{ --n: var(--to); counter-reset: n var(--n); animation: count-up 1.6s cubic-bezier(.16, 1, .3, 1) backwards; }}
.count::after {{ content: counter(n); }}
@keyframes count-up {{ from {{ --n: 0; }} }}
.stat {{ animation: stat-in .7s cubic-bezier(.2, .8, .2, 1) backwards; }}
.stat:nth-child(2) {{ animation-delay: .07s; }} .stat:nth-child(3) {{ animation-delay: .14s; }}
.stat:nth-child(4) {{ animation-delay: .21s; }} .stat:nth-child(5) {{ animation-delay: .28s; }}
@keyframes stat-in {{ from {{ opacity: 0; transform: translateY(14px); }} }}
@media (prefers-reduced-motion: reduce) {{ .count, .stat {{ animation: none; }} }}
.stat-note {{ color: {FAINT}; font-size: 13px; margin-top: 10px; min-height: 18px; }}

.section-title {{ color: {INK}; font-size: clamp(26px, 3vw, 36px); font-weight: 700; letter-spacing: -0.025em; line-height: 1.15; margin: 8px 0 10px 0; }}
.lede {{ color: {MUTED}; font-size: 17px; line-height: 1.55; max-width: 780px; margin: 0 0 22px 0; }}
.lede b {{ color: {INK}; font-weight: 600; }}
.note {{ color: {FAINT}; font-size: 13px; line-height: 1.5; }}

.insight {{ border-left: 2px solid {RED}; padding: 4px 0 4px 16px; margin: 8px 0 22px 0; color: {MUTED}; font-size: 15px; line-height: 1.55; }}
.insight b {{ color: {INK}; }}

.driver-name {{ font-size: clamp(34px, 4.5vw, 52px); background: linear-gradient(90deg, {INK} 55%, var(--c));
  -webkit-background-clip: text; background-clip: text; color: transparent; animation: name-in .8s cubic-bezier(.2, .8, .2, 1) backwards; }}
@keyframes name-in {{ from {{ opacity: 0; transform: translateX(-16px); letter-spacing: 0.02em; }} }}
.team-chip {{ display: inline-flex; align-items: center; gap: 6px; margin: 0 6px 0 0; padding: 3px 10px; border-radius: 999px;
  background: #16161B; border: 1px solid rgba(255,255,255,0.08); color: {MUTED}; font-size: 13px; }}
.team-chip i {{ width: 9px; height: 9px; border-radius: 50%; }}
.big-prob {{ color: {INK}; font-size: 88px; font-weight: 700; letter-spacing: -0.04em; line-height: 1; }}
.big-prob span {{ color: {RED}; }}

@media (max-width: 640px) {{ .stat {{ padding: 16px 16px 14px; }} .stat-value {{ font-size: 34px; }} .big-prob {{ font-size: 64px; }} }}

/* pill tabs, like a segmented control */
[data-baseweb="tab-list"] {{ gap: 4px; padding: 5px; width: fit-content; max-width: 100%; overflow-x: auto;
  background: {SURFACE}; border: 1px solid rgba(255,255,255,0.07); border-radius: 999px; }}
button[data-baseweb="tab"] {{ padding: 8px 18px; border-radius: 999px; height: auto; }}
button[data-baseweb="tab"] p {{ font-size: 15px; font-weight: 500; color: {MUTED}; }}
button[data-baseweb="tab"][aria-selected="true"] {{ background: #2A2A31; }}
button[data-baseweb="tab"][aria-selected="true"] p {{ color: {INK}; }}
[data-baseweb="tab-border"], [data-baseweb="tab-highlight"] {{ display: none; }}
[data-baseweb="tab-panel"] {{ padding-top: 34px; }}

.footer {{ border-top: 1px solid rgba(255,255,255,0.08); margin-top: 56px; padding-top: 22px; color: {FAINT}; font-size: 13px; line-height: 1.6; }}
.footer b {{ color: {MUTED}; font-weight: 600; }}

@media (max-width: 640px) {{
  [data-testid="stLayoutWrapper"]:has(> .st-key-filterbar) {{ position: static; }}
  .st-key-filterbar {{ padding: 14px 16px 10px; margin-bottom: 24px; }}
  .st-key-filterbar [data-testid="stHorizontalBlock"] {{ gap: 0.4rem; }}
  .st-key-filterbar [data-testid="stButton"] {{ padding-top: 4px; }}
  .brand {{ padding-top: 0; }}
  .brand-sub {{ margin-bottom: 12px; }}
  .lights {{ margin-top: 10px; }} }}
</style>
""", unsafe_allow_html=True)


st.markdown('<style>' + mascot.CHIBI_CSS + game.GAME_CSS + '</style>', unsafe_allow_html=True)


@st.cache_data
def load_data():
    path = os.path.join(os.path.dirname(__file__), 'clean_data.csv')
    return pd.read_csv(path)


df = load_data()


def pct(x):
    if pd.isna(x):
        return '–'
    return str(round(x * 100)) + '%'


def counted(value):
    """Whole numbers and percentages count up from zero when they appear."""
    text = str(value)
    digits, suffix = (text[:-1], '%') if text.endswith('%') else (text, '')
    if digits.isdigit() and int(digits) < 100000:
        return f'<span class="count" style="--to:{int(digits)}"></span>{suffix}'
    return text


def stat_card(label, value, note='', accent=False):
    value = counted(value)
    value_class = 'stat-value accent' if accent else 'stat-value'
    card_class = 'stat glow' if accent else 'stat'
    return (f'<div class="{card_class}"><div class="stat-label">{label}</div>'
            f'<div class="{value_class}">{value}</div><div class="stat-note">{note}</div></div>')


def stat_row(cards):
    st.markdown('<div class="stat-grid">' + ''.join(cards) + '</div>', unsafe_allow_html=True)


def section(eyebrow, title, lede):
    st.markdown(f'<div class="eyebrow">{eyebrow}</div><div class="section-title">{title}</div>'
                f'<div class="lede">{lede}</div>', unsafe_allow_html=True)


def insight(text):
    st.markdown(f'<div class="insight">{text}</div>', unsafe_allow_html=True)


# ---------------- filter bar ----------------
DEFAULTS = {'years': (2010, 2024), 'teams': [], 'circuit': 'All circuits'}
for key in DEFAULTS:
    if key not in st.session_state:
        st.session_state[key] = DEFAULTS[key]


def reset_filters():
    for key in DEFAULTS:
        st.session_state[key] = DEFAULTS[key]


team_options = df.groupby('team')['win'].sum().sort_values(ascending=False).index.tolist()
circuit_options = ['All circuits'] + sorted(df['circuit_name'].unique())

with st.container(key='filterbar'):
    c_brand, c_years, c_teams, c_circuit, c_reset = st.columns([1.15, 2, 2.2, 1.9, 0.8], gap='medium',
                                                               vertical_alignment='top')
    c_brand.markdown('<div class="brand">Lights <span>Out</span></div><div class="brand-sub">F1 · 1950–2024</div>',
                     unsafe_allow_html=True)
    c_years.slider('Seasons', 1950, 2024, key='years')
    c_teams.multiselect('Constructors', team_options, key='teams', placeholder='All constructors')
    c_circuit.selectbox('Circuit', circuit_options, key='circuit')
    c_reset.button('Reset', on_click=reset_filters, width='stretch')

years = st.session_state['years']
teams = st.session_state['teams']
circuit = st.session_state['circuit']

f = df[(df['year'] >= years[0]) & (df['year'] <= years[1])]
if len(teams) > 0:
    f = f[f['team'].isin(teams)]
if circuit != 'All circuits':
    f = f[f['circuit_name'] == circuit]

if len(f) == 0:
    st.markdown('<div class="hero-title">No races match.</div>'
                '<div class="hero-sub">Try a wider season range, or clear the constructor and circuit filters.</div>',
                unsafe_allow_html=True)
    st.stop()

wins = f[f['win']]
starters = f[f['starter']]
finishers = f[f['finished'] & f['grid_clean'].notna()]

# the same numbers over every season and team, to compare against
all_wins = df[df['win']]
all_fin = df[df['finished'] & df['grid_clean'].notna()]
base = {
    'pole': (all_wins['grid_clean'] == 1).mean(),
    'front': (all_wins['grid_clean'] <= 2).mean(),
    'within3': ((all_fin['grid_clean'] - all_fin['positionOrder']).abs() <= 3).mean(),
    'dnf': df[df['starter']]['dnf'].mean(),
}


def versus(value, key):
    if pd.isna(value) or (years == (1950, 2024) and not teams and circuit == 'All circuits'):
        return 'across 1950–2024'
    diff = round((value - base[key]) * 100)
    if diff == 0:
        return 'same as 1950–2024'
    sign = '+' if diff > 0 else '−'
    return f'{sign}{abs(diff)} pts vs 1950–2024'


# ---------------- hero ----------------
pole_win = (wins['grid_clean'] == 1).mean() if len(wins) else np.nan
front_win = (wins['grid_clean'] <= 2).mean() if len(wins) else np.nan
within3 = ((finishers['grid_clean'] - finishers['positionOrder']).abs() <= 3).mean() if len(finishers) else np.nan
dnf_rate = starters['dnf'].mean() if len(starters) else np.nan

if pd.isna(front_win):
    answer = 'Not enough wins in this selection to say.'
elif front_win >= 0.6:
    answer = 'Mostly, yes.'
elif front_win >= 0.4:
    answer = 'Partly.'
else:
    answer = 'Not really.'

span = f'{years[0]}' if years[0] == years[1] else f'{years[0]}–{years[1]}'
scope = []
if teams:
    scope.append(', '.join(teams) if len(teams) <= 3 else f'{len(teams)} constructors')
if circuit != 'All circuits':
    scope.append(circuit)
scope_text = ' · '.join([span] + scope)

# kept in its own element so the start lights only play when the page first loads
st.markdown('<div class="lights">' + '<div class="light"></div>' * 5 + '</div>', unsafe_allow_html=True)
st.markdown(f'<div class="eyebrow">Formula 1 · {scope_text}</div>'
            '<div class="hero-title">Is the race decided<br>on Saturday?</div>'
            f'<div class="hero-answer">{answer}</div>', unsafe_allow_html=True)
if not pd.isna(front_win):
    st.markdown(f'<div class="hero-sub">In this selection, <b style="color:{INK}">{pct(pole_win)}</b> of wins came from pole '
                f'and <b style="color:{INK}">{pct(front_win)}</b> from the front row. Sunday mostly shuffles drivers '
                f'by a few places.</div>', unsafe_allow_html=True)
st.markdown(f'<div class="hero-meta">{f["raceId"].nunique():,} races · {f["driverId"].nunique():,} drivers · '
            f'{f["constructorId"].nunique():,} constructors</div>', unsafe_allow_html=True)

stat_row([
    stat_card('Won from pole', pct(pole_win), versus(pole_win, 'pole'), accent=True),
    stat_card('Won from the front row', pct(front_win), versus(front_win, 'front')),
    stat_card('Finish within 3 places of grid', pct(within3), versus(within3, 'within3')),
    stat_card('DNF rate among starters', pct(dnf_rate), versus(dnf_rate, 'dnf')),
])

# a game invite link (?room=CODE) opens straight on the Play tab
tab_q, tab_d, tab_r, tab_driver, tab_p, tab_play, tab_data = st.tabs(
    ['Qualifying', 'Dominance', 'Reliability', 'Drivers', 'Predict', 'Play', 'Data'],
    default='Play' if st.query_params.get('room') else None)

# ---------------- qualifying ----------------
with tab_q:
    grid_starts = starters[starters['grid_clean'].between(1, 20)]
    p1 = grid_starts[grid_starts['grid_clean'] == 1]['podium'].mean()
    p5 = grid_starts[grid_starts['grid_clean'] == 5]['podium'].mean()
    section('Sector 1 · Qualifying', 'The grid sets the order.',
            f'From pole, a driver reached the podium <b>{pct(p1)}</b> of the time. From fifth it falls to '
            f'<b>{pct(p5)}</b>. Pick an outcome to see how fast the chance drops.')

    outcome = st.segmented_control('Outcome', ['Win', 'Podium', 'Points'], default='Podium', key='outcome',
                                   label_visibility='collapsed')
    if outcome is None:
        outcome = 'Podium'
    if outcome == 'Win':
        hit = grid_starts['win']
    elif outcome == 'Podium':
        hit = grid_starts['podium']
    else:
        hit = grid_starts['points'] > 0
    rate = hit.groupby(grid_starts['grid_clean']).agg(['mean', 'size']).reindex(range(1, 21))
    charts.rate_by_slot([None if pd.isna(v) else v * 100 for v in rate['mean']],
                        [0 if pd.isna(n) else int(n) for n in rate['size']], outcome)

    # grid groups to Sunday results
    g = grid_starts.copy()
    g['from'] = pd.cut(g['grid_clean'], [0, 1, 3, 6, 10, 99], labels=['P1', 'P2–3', 'P4–6', 'P7–10', 'P11+'])
    g['to'] = np.select([g['win'], g['podium'], g['points'] > 0, g['finished']],
                        ['Win', 'Podium', 'Points', 'No points'], 'DNF')
    flows = g.groupby(['from', 'to'], observed=True).size().to_dict()
    charts.grid_to_result(flows)

    col1, col2 = st.columns([1.35, 1], gap='large')
    with col1:
        g['result'] = np.where(g['finished'], g['positionOrder'].clip(upper=21), 22)
        table = pd.crosstab(g['grid_clean'].astype(int), g['result']).reindex(
            index=range(1, 21), columns=range(1, 23), fill_value=0)
        share = table.div(table.sum(axis=1).replace(0, np.nan), axis=0) * 100
        share = share.drop(columns=21)  # finishing 21st or lower is rare, so it is left out of the picture
        matrix = [[None if pd.isna(v) else float(v) for v in row] for row in share.values]
        charts.heatmap(matrix, [str(i) for i in range(1, 21)] + ['DNF'])
    with col2:
        gained = (finishers['grid_clean'] - finishers['positionOrder']).clip(-15, 15)
        charts.places_gained(gained.value_counts().reindex(range(-15, 16), fill_value=0))

    insight(f'<b>{pct(within3)}</b> of classified finishers end within three places of where they started (red bars). '
            f'Follow the flows: almost every win comes from the front, and the back of the grid mostly feeds '
            f'"no points" and DNF.')

# ---------------- dominance ----------------
with tab_d:
    if len(wins) == 0:
        section('Sector 2 · Dominance', 'No wins in this selection.', 'Widen the filters to compare constructors.')
    else:
        season = wins.groupby(['year', 'team']).size().reset_index(name='wins')
        totals = wins.groupby('year').size()
        leaders = season.sort_values('wins', ascending=False).drop_duplicates('year').set_index('year').sort_index()
        leaders['share'] = leaders['wins'] / totals * 100
        top_team = wins['team'].value_counts().index[0]
        top_seasons = (leaders['team'] == top_team).sum()

        section('Sector 2 · Dominance', 'Every era has an owner.',
                f'<b>{top_team}</b> won the most races in this selection and led <b>{top_seasons}</b> of '
                f'{len(leaders)} seasons. Watch the wins pile up, season by season.')

        # bar chart race: running total of wins for the ten most successful teams in the selection
        race_teams = wins['team'].value_counts().head(10).index.tolist()
        running = season[season['team'].isin(race_teams)].pivot(index='year', columns='team', values='wins') \
            .reindex(index=range(int(leaders.index.min()), int(leaders.index.max()) + 1), columns=race_teams) \
            .fillna(0).cumsum()
        frames = [{'year': int(y), 'values': [int(v) for v in row]} for y, row in running.iterrows()]
        charts.bar_race(frames, race_teams, [game.TEAM_COLORS.get(t, '#8E8E93') for t in race_teams])

        col1, col2 = st.columns([1.4, 1], gap='large')
        with col1:
            charts.leader_share(leaders.index.tolist(), leaders['team'].tolist(), leaders['wins'].tolist(),
                                totals.reindex(leaders.index).tolist(), leaders['share'].tolist(),
                                [game.TEAM_COLORS.get(t, '#8E8E93') for t in leaders['team']])
        with col2:
            eras = [('1950s', 1950, 1959), ('1960s', 1960, 1969), ('1970s', 1970, 1979), ('1980s', 1980, 1989),
                    ('1990s', 1990, 1999), ('2000s', 2000, 2009), ('2010–13', 2010, 2013),
                    ('2014–20', 2014, 2020), ('2021–24', 2021, 2024)]
            rows = []
            for name, start, end in eras:
                era_wins = wins[(wins['year'] >= start) & (wins['year'] <= end)]
                if len(era_wins) == 0:
                    continue
                counts = era_wins['team'].value_counts()
                rows.append({'Era': name, 'Top team': counts.index[0], 'Wins': f'{counts.iloc[0]} of {counts.sum()}',
                             'Share': counts.iloc[0] / counts.sum() * 100})
            st.markdown(f'<div style="color:{INK};font-size:16px;font-weight:600;margin:4px 0 12px 0">Top team by era'
                        '</div>', unsafe_allow_html=True)
            st.dataframe(pd.DataFrame(rows), hide_index=True, height=35 * (len(rows) + 1) + 3,
                         column_config={'Share': st.column_config.ProgressColumn(
                             'Share of wins', format='%.0f%%', min_value=0, max_value=100)})

        best = leaders['share'].idxmax()
        insight(f'The most one-sided season here is <b>{best}</b>: {leaders.loc[best, "team"]} won '
                f'{leaders.loc[best, "wins"]} of {totals[best]} races. Better reliability means the fastest car '
                f'almost always reaches the flag, so dominance has grown in the modern era.')

# ---------------- reliability ----------------
with tab_r:
    by_year = starters.groupby('year').agg(dnf=('dnf', 'mean'),
                                           mech=('dnf_type', lambda s: (s == 'Mechanical').mean())) * 100
    first, last = by_year.index.min(), by_year.index.max()
    section('Sector 3 · Reliability', 'Cars stopped breaking.',
            f'In {first}, <b>{by_year.loc[first, "dnf"]:.0f}%</b> of starters failed to finish. By {last} it was '
            f'<b>{by_year.loc[last, "dnf"]:.0f}%</b>. Widen the season range to 1950 to see the full change.')
    charts.dnf_lines(by_year.index.tolist(), by_year['dnf'].tolist(), by_year['mech'].tolist())

    causes = starters[starters['dnf']].groupby('decade')['dnf_type'].value_counts(normalize=True).unstack().fillna(0) * 100
    charts.causes_by_decade([f'{d}s' for d in causes.index],
                            {c: causes[c].tolist() for c in ['Mechanical', 'Crash/collision', 'Other'] if c in causes})

    mech_now = causes['Mechanical'].iloc[-1] if 'Mechanical' in causes.columns else np.nan
    insight(f'Mechanical failures still cause <b>{mech_now:.0f}%</b> of retirements in the {causes.index[-1]}s, '
            f'but far fewer cars retire at all. Status labels changed over the decades, so treat the split as approximate.')

# ---------------- drivers ----------------
def _quick_pick():
    if st.session_state.get('driver_pick'):
        st.session_state['driver'] = st.session_state['driver_pick']
    st.session_state['driver_pick'] = None


def driver_metrics(rows):
    """Percentages used by the radar, for one driver or for the whole field."""
    s = rows[rows['starter']]
    fin = s[s['finished'] & s['grid_clean'].notna()]
    return [s['win'].mean() * 100, s['podium'].mean() * 100, (s['points'] > 0).mean() * 100,
            (s['grid_clean'] <= 2).mean() * 100, s['finished'].mean() * 100,
            (fin['positionOrder'] < fin['grid_clean']).mean() * 100 if len(fin) else 0]


with tab_driver:
    driver_options = f[f['starter']].groupby('driver')['win'].sum().sort_values(ascending=False).index.tolist()
    if len(driver_options) == 0:
        section('Driver', 'No drivers in this selection.', 'Widen the filters.')
    else:
        pick, chips = st.columns([1, 2.2], gap='medium', vertical_alignment='bottom')
        driver = pick.selectbox('Driver', driver_options, key='driver', help='Sorted by wins in the current selection.')
        chips.pills('Quick pick', driver_options[:6], key='driver_pick', on_change=_quick_pick,
                    label_visibility='collapsed')
        d = f[f['driver'] == driver]
        d_start = d[d['starter']]
        d_fin = d[d['finished'] & d['grid_clean'].notna()]
        team_list = d['team'].value_counts().index.tolist()
        color = game.TEAM_COLORS.get(team_list[0], RED) if team_list else RED
        chips_html = ''.join(f'<span class="team-chip"><i style="background:{game.TEAM_COLORS.get(t, "#8E8E93")}"></i>'
                             f'{t}</span>' for t in team_list[:4])
        st.markdown(f'<div class="eyebrow">Driver</div><div class="section-title driver-name" style="--c:{color}">'
                    f'{driver}</div><div class="lede">{d["year"].min()}–{d["year"].max()} · {len(d_start)} starts '
                    f'&nbsp;{chips_html}</div>', unsafe_allow_html=True)

        gain = (d_fin['grid_clean'] - d_fin['positionOrder']).mean() if len(d_fin) else np.nan
        poles = d[d['grid_clean'] == 1]
        stat_row([
            stat_card('Starts', f'{len(d_start):,}'),
            stat_card('Wins', f'{int(d["win"].sum())}', pct(d['win'].sum() / len(d_start)) + ' of starts' if len(d_start) else '', accent=True),
            stat_card('Podiums', f'{int(d["podium"].sum())}'),
            stat_card('Pole starts', f'{len(poles)}'),
            stat_card('Places gained', '–' if pd.isna(gain) else f'{gain:+.1f}', 'avg per classified finish'),
        ])

        n = max(len(d_start), 1)
        charts.rings([('Win rate', d_start['win'].sum() / n * 100, '#FFD60A'),
                      ('Podium rate', d_start['podium'].sum() / n * 100, RED),
                      ('Poles turned into wins', poles['win'].mean() * 100 if len(poles) else 0, color),
                      ('Races finished', d_start['finished'].mean() * 100 if len(d_start) else 0, INK)])

        col1, col2 = st.columns([1.5, 1], gap='large')
        with col1:
            pts = []
            rng = np.random.default_rng(len(d_start))
            for _, r in d_start[d_start['grid_clean'].notna()].iterrows():
                kind = ('Win' if r['win'] else 'Podium' if r['podium'] else 'Points' if r['points'] > 0
                        else 'No points' if r['finished'] else 'DNF')
                y = r['positionOrder'] if r['finished'] else 24
                pts.append({'x': round(float(r['grid_clean'] + rng.uniform(-0.25, 0.25)), 2),
                            'y': round(float(y + rng.uniform(-0.25, 0.25)), 2), 'kind': kind,
                            'race': f'{int(r["year"])} {r["race_name"]}'})
            charts.race_scatter(pts)
        with col2:
            # each radar axis is scaled to the best driver in the selection with at least 20 starts
            labels = ['Wins', 'Podiums', 'Points finishes', 'Front-row starts', 'Finished', 'Gained places']
            field = driver_metrics(f)
            regulars = f[f['starter']].groupby('driver').filter(lambda g: len(g) >= 20)
            best = [max(v) for v in zip(*[driver_metrics(g) for _, g in regulars.groupby('driver')])] \
                if len(regulars) else [100] * 6
            mine = driver_metrics(d)
            maxes = [max(5, round(max(b, m) * 1.05, 1)) for b, m in zip(best, mine)]
            charts.radar(labels, maxes, mine, field, driver, color)

        per_year = d.groupby('year').agg(wins=('win', 'sum'), podiums=('podium', 'sum'),
                                         team=('team', lambda t: t.value_counts().index[0]))
        charts.career(per_year.index.tolist(), per_year['wins'].tolist(),
                      (per_year['podiums'] - per_year['wins']).tolist(), per_year['team'].tolist(),
                      [game.TEAM_COLORS.get(t, '#8E8E93') for t in per_year['team']])

        if len(poles) > 0:
            insight(f'{driver} turned <b>{pct(poles["win"].mean())}</b> of pole starts into wins here. '
                    f'Across all drivers in this selection the figure is '
                    f'{pct(starters[starters["grid_clean"] == 1]["win"].mean())}. Dots above the dashed line are races '
                    f'where they finished higher than they started.')

# ---------------- predict ----------------
@st.cache_resource
def train_model():
    # same model as the notebook: podium from grid, team and year, trained on 2010-2024
    model_df = df[(df['year'] >= 2010) & df['starter'] & df['grid_clean'].notna()].copy()
    top_teams = model_df.groupby('team')['points'].sum().sort_values(ascending=False).head(6).index.tolist()
    model_df['team_group'] = model_df['team'].where(model_df['team'].isin(top_teams), 'Other')
    X = pd.get_dummies(model_df[['grid_clean', 'team_group', 'year']])
    model = LogisticRegression(max_iter=1000)
    model.fit(X, model_df['podium'])
    observed = model_df.groupby('grid_clean')['podium'].mean()
    return model, top_teams, X.columns, observed


@st.fragment
def predictor():
    model, top_teams, model_columns, observed = train_model()
    section('Predict', 'What are the odds from here?',
            'A logistic regression trained on every 2010–2024 start. Choose a grid slot, a team and a season.')

    col1, col2 = st.columns([1, 1.4], gap='large')
    with col1:
        grid_in = st.slider('Grid slot', 1, 20, 3, key='p_grid')
        team_in = st.selectbox('Team', top_teams + ['Other'], key='p_team', help='Teams outside the top six are grouped as Other.')
        year_in = st.slider('Season', 2010, 2024, 2024, key='p_year')

    rows = pd.DataFrame({'grid_clean': range(1, 21), 'team_group': team_in, 'year': year_in})
    rows = pd.get_dummies(rows).reindex(columns=model_columns, fill_value=0)
    curve = model.predict_proba(rows)[:, 1] * 100
    chance = curve[grid_in - 1]

    with col2:
        charts.gauge(chance, f'P{grid_in} · {team_in} · {year_in}')
        st.markdown(f'<div class="note" style="text-align:center">Across all teams, P{grid_in} reached the podium '
                    f'{observed.get(grid_in, np.nan) * 100:.0f}% of the time.</div>', unsafe_allow_html=True)

    charts.chance_curve(curve, grid_in, subtitle=f' · {team_in}, {year_in}')
    st.markdown('<div class="note">Precision 0.71 · recall 0.53 · ROC-AUC 0.92 on a held-out 20% test set. '
                'A rough guide, not a forecast: it knows nothing about weather, strategy or upgrades.</div>',
                unsafe_allow_html=True)


with tab_p:
    predictor()

with tab_play:
    game.play(df, train_model())


# ---------------- data ----------------
with tab_data:
    section('Data', 'The rows behind every chart.',
            f'{len(f):,} entries match the filters. The preview shows the first 100.')
    view_cols = ['year', 'round', 'race_name', 'circuit_name', 'driver', 'team', 'grid', 'positionOrder',
                 'points', 'laps', 'status', 'finished']
    st.dataframe(f[view_cols].head(100), hide_index=True, height=420, column_config={
        'year': st.column_config.NumberColumn('Season', format='%d'),
        'round': 'Round', 'race_name': 'Race', 'circuit_name': 'Circuit', 'driver': 'Driver', 'team': 'Team',
        'grid': 'Grid', 'positionOrder': 'Finish', 'points': 'Points', 'laps': 'Laps', 'status': 'Status',
        'finished': st.column_config.CheckboxColumn('Classified')})

    st.markdown(f'<div style="color:{INK};font-size:16px;margin:26px 0 10px 0">Summary statistics</div>',
                unsafe_allow_html=True)
    num_cols = ['grid_clean', 'positionOrder', 'points', 'laps', 'fastest_lap_sec', 'fastestLapSpeed']
    st.dataframe(f[num_cols].describe().round(2), column_config={
        'grid_clean': 'Grid', 'positionOrder': 'Finish', 'points': 'Points', 'laps': 'Laps',
        'fastest_lap_sec': 'Fastest lap (s)', 'fastestLapSpeed': 'Fastest lap (km/h)'})

    st.download_button('Download these rows as CSV', f.to_csv(index=False).encode('utf-8'),
                       file_name='f1_filtered.csv', mime='text/csv')

# ---------------- footer ----------------
st.markdown('<div class="footer"><b>About the data.</b> Every Formula 1 World Championship result from 1950 to 2024: '
            'one row per driver per race, 26,759 rows from five joined tables. Source: '
            '<a href="https://www.kaggle.com/datasets/rohanrao/formula-1-world-championship-1950-2020">Formula 1 World '
            'Championship (1950–2020), Rohan Rao on Kaggle</a>, built from the Ergast API. '
            'Unit 3 Final Project · Majed Alotaibi · University of Hail.</div>', unsafe_allow_html=True)

# ---------------- Chibi Max ----------------
filters_text = (f'Dashboard filters: seasons {years[0]}-{years[1]}; constructors: '
                f'{", ".join(teams) if teams else "all"}; circuit: {circuit}')
mascot.widget(df, train_model(), filters_text)
