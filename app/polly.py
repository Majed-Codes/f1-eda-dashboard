"""Polly, the chibi pit-wall assistant.

Her words come from Claude. Every number she gives comes from the tools below, which query clean_data.csv,
so she never has to guess a statistic.
"""
import base64
import difflib
import json
import os

import anthropic
import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

MODEL = 'claude-opus-5-5'
RED = '#FF2B17'

SYSTEM = """You are Polly, the cheerful chibi pit-crew assistant inside "Lights Out", a student's Formula 1 data \
dashboard (Unit 3 data analysis project, University of Hail). You wear a red cap and a red racing dress.

The data is every Formula 1 World Championship race result from 1950 to 2024 (Ergast data via Kaggle): grid slot, \
finishing position, points, laps, finishing status, driver, constructor, circuit and season. There is no lap-time, \
pit-stop, weather, tyre or strategy data.

Use the tools for every number you state, and never use outside knowledge for statistics. If a name does not match, \
use the suggestions the tool returns or ask the user which one they meant. If the data cannot answer a question, say \
so kindly and suggest a question it can answer. You may add a short piece of general F1 background only when you \
label it as background, not data.

Each user message starts with the dashboard's current filters in square brackets. Use them as the default scope when \
the question does not name its own seasons, teams or circuit, and say which scope you used.

Style: friendly, upbeat and short. Two to four sentences, plain words, at most one emoji. Put the key numbers in bold. \
Reply in the language the user writes in."""

TOOLS = [
    {
        'name': 'f1_stats',
        'description': 'Summary numbers for a slice of the data: races, entries, wins, podiums, pole starts, how often '
                       'pole turned into a win, share of wins from pole and from the front row, DNF rate, the split '
                       'of retirement causes, and the top drivers and teams by wins. Filter by seasons and optionally '
                       'by a constructor, a driver and a circuit (circuit name, race name or country all work).',
        'input_schema': {
            'type': 'object',
            'properties': {
                'start_year': {'type': 'integer', 'description': 'First season, 1950 to 2024.'},
                'end_year': {'type': 'integer', 'description': 'Last season, 1950 to 2024.'},
                'team': {'type': 'string', 'description': 'Optional constructor name, e.g. "Ferrari".'},
                'driver': {'type': 'string', 'description': 'Optional driver name, e.g. "Hamilton".'},
                'circuit': {'type': 'string', 'description': 'Optional circuit, race name or country, e.g. "Monaco".'},
            },
            'required': ['start_year', 'end_year'],
        },
    },
    {
        'name': 'leaderboard',
        'description': 'Rank drivers or constructors by wins, podiums or pole starts over a range of seasons, '
                       'optionally at one circuit or for one constructor.',
        'input_schema': {
            'type': 'object',
            'properties': {
                'by': {'type': 'string', 'enum': ['driver', 'team']},
                'metric': {'type': 'string', 'enum': ['wins', 'podiums', 'poles']},
                'start_year': {'type': 'integer'},
                'end_year': {'type': 'integer'},
                'circuit': {'type': 'string', 'description': 'Optional circuit, race name or country.'},
                'team': {'type': 'string', 'description': 'Optional constructor, to rank its drivers.'},
                'n': {'type': 'integer', 'description': 'How many rows, 1 to 15. Default 5.'},
            },
            'required': ['by', 'metric', 'start_year', 'end_year'],
        },
    },
    {
        'name': 'podium_chance',
        'description': "The dashboard's logistic regression: predicted chance of a podium from a grid slot for a "
                       'team in a season (2010 to 2024 only), plus how often that grid slot reached the podium in '
                       'the real data. Teams outside the top six of 2010 to 2024 count as "Other".',
        'input_schema': {
            'type': 'object',
            'properties': {
                'grid': {'type': 'integer', 'description': 'Grid slot, 1 to 20.'},
                'team': {'type': 'string'},
                'year': {'type': 'integer', 'description': 'Season, 2010 to 2024.'},
            },
            'required': ['grid', 'team', 'year'],
        },
    },
]


# ---------------- the tools ----------------
def _suggest(text, options):
    return difflib.get_close_matches(text, options, n=3, cutoff=0.5)


def _filter(df, start_year, end_year, team=None, driver=None, circuit=None):
    start_year = int(np.clip(int(start_year), 1950, 2024))
    end_year = int(np.clip(int(end_year), start_year, 2024))
    f = df[(df['year'] >= start_year) & (df['year'] <= end_year)]
    scope = {'seasons': f'{start_year}-{end_year}'}
    if team:
        hit = f['team'].str.contains(team, case=False, regex=False)
        if not hit.any():
            return None, {'error': f'No constructor matches "{team}" in these seasons.',
                          'did_you_mean': _suggest(team, df['team'].unique().tolist())}
        f = f[hit]
        scope['team'] = sorted(f['team'].unique().tolist())
    if driver:
        hit = f['driver'].str.contains(driver, case=False, regex=False)
        if not hit.any():
            return None, {'error': f'No driver matches "{driver}" in this selection.',
                          'did_you_mean': _suggest(driver, df['driver'].unique().tolist())}
        f = f[hit]
        scope['driver'] = sorted(f['driver'].unique().tolist())[:5]
    if circuit:
        hit = (f['circuit_name'].str.contains(circuit, case=False, regex=False)
               | f['race_name'].str.contains(circuit, case=False, regex=False)
               | f['country'].str.contains(circuit, case=False, regex=False))
        if not hit.any():
            return None, {'error': f'No circuit, race or country matches "{circuit}" in this selection.',
                          'did_you_mean': _suggest(circuit, df['circuit_name'].unique().tolist())}
        f = f[hit]
        scope['circuit'] = sorted(f['circuit_name'].unique().tolist())[:5]
    return f, scope


def _share(x):
    return None if pd.isna(x) else round(float(x) * 100, 1)


def f1_stats(df, start_year, end_year, team=None, driver=None, circuit=None):
    f, scope = _filter(df, start_year, end_year, team, driver, circuit)
    if f is None:
        return scope
    wins = f[f['win']]
    starters = f[f['starter']]
    poles = f[f['grid_clean'] == 1]
    dnf_types = starters[starters['dnf']]['dnf_type'].value_counts(normalize=True)
    return {
        'scope': scope,
        'races': int(f['raceId'].nunique()),
        'entries': int(len(f)),
        'wins': int(len(wins)),
        'podiums': int(f['podium'].sum()),
        'pole_starts': int(len(poles)),
        'pole_starts_converted_to_win_pct': _share(poles['win'].mean()) if len(poles) else None,
        'wins_from_pole_pct': _share((wins['grid_clean'] == 1).mean()) if len(wins) else None,
        'wins_from_front_row_pct': _share((wins['grid_clean'] <= 2).mean()) if len(wins) else None,
        'dnf_rate_among_starters_pct': _share(starters['dnf'].mean()) if len(starters) else None,
        'retirement_causes_pct': {k: round(v * 100, 1) for k, v in dnf_types.items()},
        'top_drivers_by_wins': wins['driver'].value_counts().head(5).to_dict(),
        'top_teams_by_wins': wins['team'].value_counts().head(5).to_dict(),
    }


def leaderboard(df, by, metric, start_year, end_year, circuit=None, team=None, n=5):
    f, scope = _filter(df, start_year, end_year, team=team, circuit=circuit)
    if f is None:
        return scope
    col = 'driver' if by == 'driver' else 'team'
    if metric == 'wins':
        counts = f[f['win']][col].value_counts()
    elif metric == 'podiums':
        counts = f[f['podium']][col].value_counts()
    else:
        counts = f[f['grid_clean'] == 1][col].value_counts()
    n = int(np.clip(n or 5, 1, 15))
    return {'scope': scope, 'ranked_by': metric, 'rows': counts.head(n).to_dict()}


def podium_chance(bundle, grid, team, year):
    model, top_teams, columns, observed = bundle
    grid = int(np.clip(int(grid), 1, 20))
    year = int(np.clip(int(year), 2010, 2024))
    group = next((t for t in top_teams if team.lower() in t.lower() or t.lower() in team.lower()), 'Other')
    row = pd.get_dummies(pd.DataFrame({'grid_clean': [grid], 'team_group': [group], 'year': [year]}))
    row = row.reindex(columns=columns, fill_value=0)
    return {'grid': grid, 'team_used_by_model': group, 'year': year,
            'predicted_podium_chance_pct': round(float(model.predict_proba(row)[0, 1]) * 100, 1),
            'real_podium_rate_from_this_slot_2010_2024_pct': _share(observed.get(grid, np.nan)),
            'model_teams': top_teams + ['Other']}


def run_tool(name, args, df, bundle):
    """Returns (json text, is_error)."""
    try:
        if name == 'f1_stats':
            out = f1_stats(df, args['start_year'], args['end_year'], args.get('team'), args.get('driver'),
                           args.get('circuit'))
        elif name == 'leaderboard':
            out = leaderboard(df, args['by'], args['metric'], args['start_year'], args['end_year'],
                              args.get('circuit'), args.get('team'), args.get('n', 5))
        elif name == 'podium_chance':
            out = podium_chance(bundle, args['grid'], args['team'], args['year'])
        else:
            return json.dumps({'error': f'Unknown tool {name}'}), True
    except (KeyError, TypeError, ValueError) as e:
        return json.dumps({'error': f'Bad input: {e}'}), True
    return json.dumps(out, default=str), 'error' in out


# ---------------- talking to Claude ----------------
def get_client():
    key = None
    try:
        key = st.secrets.get('ANTHROPIC_API_KEY')
    except Exception:
        pass
    key = key or os.environ.get('ANTHROPIC_API_KEY')
    if not key:
        return None
    return anthropic.Anthropic(api_key=key)


def answer(client, messages, df, bundle, max_steps=6):
    """Runs one user turn (with tool calls) and returns Polly's reply text.

    `messages` is appended to in place, so the history stays append-only between turns.
    """
    for _ in range(max_steps):
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=SYSTEM,
            tools=TOOLS,
            messages=messages,
            output_config={'effort': 'low'},
            betas=['server-side-fallback-2026-07-01'],
            fallbacks='default',
        )
        messages.append({'role': 'assistant', 'content': response.content})

        if response.stop_reason == 'refusal':
            return "Hmm, I can't help with that one. Ask me anything about the races, teams or drivers! 🏁"

        if response.stop_reason == 'tool_use':
            results = []
            for block in response.content:
                if block.type == 'tool_use':
                    text, is_error = run_tool(block.name, block.input, df, bundle)
                    result = {'type': 'tool_result', 'tool_use_id': block.id, 'content': text}
                    if is_error:
                        result['is_error'] = True
                    results.append(result)
            messages.append({'role': 'user', 'content': results})
            continue

        reply = ''.join(block.text for block in response.content if block.type == 'text').strip()
        if response.stop_reason == 'max_tokens':
            reply += ' …'
        return reply or "I lost my notes for a second. Could you ask that again?"
    return 'That one needed too many lookups. Could you ask it in a simpler way?'


# ---------------- drawing Polly ----------------
def chibi_svg(size=220, mood='happy', uid='p', head_only=False, animated=True):
    """Polly as an inline SVG: red cap, red racing dress with a checkered hem, and a little checkered flag.

    She is built from separate parts (head, pigtails, legs, flag arm) so CSS can animate each one, and she carries
    a second "wheee" face that only shows while she is being dragged.
    """
    view = '26 18 148 148' if head_only else '0 0 200 240'
    height = size if head_only else int(size * 1.2)
    chk = f'chk-{uid}'
    if mood == 'wow':
        mouth = ('<ellipse cx="100" cy="140" rx="5.5" ry="6.5" fill="#7A2E22"/>'
                 '<ellipse cx="100" cy="143" rx="3" ry="2.2" fill="#FF8C9A"/>')
    elif mood == 'oops':
        mouth = ('<path d="M91 141 Q95.5 136 100 141 Q104.5 146 109 141" stroke="#7A2E22" stroke-width="2.6" '
                 'fill="none" stroke-linecap="round"/>'
                 '<path d="M153 98 Q160 110 153 117 Q146 110 153 98 Z" fill="#8FD3FF" opacity=".9"/>')
    else:
        mouth = ('<path d="M92 136 Q100 145 108 136" stroke="#7A2E22" stroke-width="2.6" fill="none" '
                 'stroke-linecap="round"/>')
    eye = ('<ellipse cx="{x}" cy="118" rx="10.5" ry="13.5" fill="#2A1712"/>'
           '<ellipse cx="{x}" cy="121.5" rx="7.5" ry="8.5" fill="#8A4526"/>'
           '<circle cx="{hx}" cy="112" r="3.8" fill="#fff"/><circle cx="{sx}" cy="124.5" r="1.7" fill="#fff"/>')
    eyes = eye.format(x=78, hx=74, sx=81.5) + eye.format(x=122, hx=118, sx=125.5)
    # the face she makes while being carried around: happy squint and a big open smile
    wheee = ('<path d="M67 121 Q78 107 89 121" stroke="#2A1712" stroke-width="4" fill="none" stroke-linecap="round"/>'
             '<path d="M111 121 Q122 107 133 121" stroke="#2A1712" stroke-width="4" fill="none" stroke-linecap="round"/>'
             '<path d="M89 133 Q100 153 111 133 Z" fill="#7A2E22"/><path d="M94 142 Q100 149 106 142 Z" fill="#FF8C9A"/>'
             '<path d="M40 112 l-8 -3 M40 120 l-9 1 M160 112 l8 -3 M160 120 l9 1" stroke="#FF2B17" stroke-width="2.4" '
             'stroke-linecap="round"/>')
    cls = 'chibi animated' if animated else 'chibi'
    return f"""<svg class="{cls}" width="{size}" height="{height}" viewBox="{view}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Polly, a chibi girl in a red racing cap and dress">
<defs><pattern id="{chk}" width="8" height="8" patternUnits="userSpaceOnUse"><rect width="8" height="8" fill="#fff"/><rect width="4" height="4" fill="#15151a"/><rect x="4" y="4" width="4" height="4" fill="#15151a"/></pattern></defs>
<ellipse class="shadow" cx="100" cy="232" rx="44" ry="6" fill="#000" opacity=".35"/>
<g class="bob">
<g class="leg leg-l"><rect x="84" y="204" width="12" height="21" rx="6" fill="#FFE3D3"/><ellipse cx="89" cy="226" rx="10" ry="5.5" fill="#F5F5F7"/><path d="M82 224 h14" stroke="{RED}" stroke-width="2"/></g>
<g class="leg leg-r"><rect x="104" y="204" width="12" height="21" rx="6" fill="#FFE3D3"/><ellipse cx="111" cy="226" rx="10" ry="5.5" fill="#F5F5F7"/><path d="M104 224 h14" stroke="{RED}" stroke-width="2"/></g>
<g class="body">
<path d="M78 156 L122 156 L145 210 Q100 219 55 210 Z" fill="{RED}"/>
<path d="M57 203 Q100 211 143 203 L145 210 Q100 219 55 210 Z" fill="url(#{chk})"/>
<path d="M83 158 L67 203 M117 158 L133 203" stroke="#fff" stroke-width="2.5" opacity=".9"/>
<path d="M87 156 L100 168 L113 156 Z" fill="#fff"/>
<circle cx="100" cy="185" r="9.5" fill="#fff"/><text x="100" y="189" text-anchor="middle" font-size="9.5" font-weight="800" fill="{RED}" font-family="Helvetica, Arial, sans-serif">P1</text>
<g class="arm-l"><path d="M81 162 Q67 175 65 188" stroke="{RED}" stroke-width="9" stroke-linecap="round" fill="none"/><circle cx="64" cy="191" r="6" fill="#FFE3D3"/></g>
</g>
<g class="head">
<g class="tail tail-l"><ellipse cx="38" cy="134" rx="15" ry="32" fill="#3B2420" transform="rotate(14 38 134)"/><circle cx="47" cy="100" r="5" fill="{RED}"/></g>
<g class="tail tail-r"><ellipse cx="162" cy="134" rx="15" ry="32" fill="#3B2420" transform="rotate(-14 162 134)"/><circle cx="153" cy="100" r="5" fill="{RED}"/></g>
<circle cx="100" cy="99" r="64" fill="#3B2420"/>
<ellipse cx="100" cy="109" rx="56" ry="52" fill="#FFE3D3"/>
<path d="M45 106 Q47 64 100 58 Q153 64 155 106 Q145 86 131 93 Q121 76 105 89 Q92 74 80 91 Q66 80 56 99 Z" fill="#3B2420"/>
<path d="M39 87 Q43 33 100 29 Q157 33 161 87 Q100 75 39 87 Z" fill="{RED}"/>
<path d="M53 64 Q100 49 147 64" stroke="#fff" stroke-width="4" fill="none" stroke-linecap="round"/>
<rect x="91" y="38" width="18" height="14" rx="2.5" fill="url(#{chk})" stroke="#fff" stroke-width="1.2"/>
<circle cx="100" cy="30" r="4.2" fill="#C41C0E"/>
<path d="M37 87 Q100 71 163 87 Q171 93 161 97 Q100 85 39 97 Q29 93 37 87 Z" fill="#C41C0E"/>
<path d="M45 95 Q38 128 50 152 Q54 126 63 101 Z" fill="#3B2420"/>
<path d="M155 95 Q162 128 150 152 Q146 126 137 101 Z" fill="#3B2420"/>
<ellipse cx="63" cy="135" rx="8.5" ry="4.8" fill="#FF7A90" opacity=".55"/><ellipse cx="137" cy="135" rx="8.5" ry="4.8" fill="#FF7A90" opacity=".55"/>
<g class="face-normal"><g class="eyes">{eyes}</g>{mouth}</g>
<g class="face-drag">{wheee}</g>
</g>
<g class="arm-flag"><path d="M118 160 Q140 164 157 147" stroke="{RED}" stroke-width="9" stroke-linecap="round" fill="none"/>
<g class="flag"><line x1="160" y1="148" x2="167" y2="88" stroke="#D9D9DE" stroke-width="3" stroke-linecap="round"/>
<path d="M167 89 Q181 83 197 90 L195 115 Q180 109 166 114 Z" fill="url(#{chk})" stroke="#15151a" stroke-width="1"/></g>
<circle cx="159" cy="146" r="6.5" fill="#FFE3D3"/></g>
</g></svg>"""


def avatar_uri():
    svg = chibi_svg(64, uid='av', head_only=True, animated=False)
    return 'data:image/svg+xml;base64,' + base64.b64encode(svg.encode()).decode()


CHIBI_CSS = """
/* Polly's idle life: bounce with a little squash, head tilt, swaying pigtails, waving flag */
.chibi .face-drag { display: none; }
.chibi.animated .bob { animation: polly-bounce 2.2s ease-in-out infinite; transform-origin: 100px 228px; }
.chibi.animated .head { animation: polly-tilt 3.4s ease-in-out infinite; transform-origin: 100px 160px; }
.chibi.animated .tail-l { animation: polly-tail 1.8s ease-in-out infinite alternate; transform-origin: 46px 104px; }
.chibi.animated .tail-r { animation: polly-tail 1.8s ease-in-out -0.9s infinite alternate-reverse; transform-origin: 154px 104px; }
.chibi.animated .arm-flag { animation: polly-wave 1.1s ease-in-out infinite alternate; transform-origin: 118px 160px; }
.chibi.animated .arm-l { animation: polly-arm 2.2s ease-in-out infinite; transform-origin: 81px 162px; }
.chibi.animated .shadow { animation: polly-shadow 2.2s ease-in-out infinite; transform-origin: 100px 232px; }
.chibi.animated .eyes { animation: polly-blink 4.6s infinite; transform-box: fill-box; transform-origin: center; }
@keyframes polly-bounce {
  0%, 100% { transform: translateY(0) scale(1.03, 0.97); }
  30% { transform: translateY(-7px) scale(0.98, 1.03); }
  55% { transform: translateY(-9px) scale(1, 1); }
  85% { transform: translateY(0) scale(1.04, 0.96); } }
@keyframes polly-shadow { 0%, 85%, 100% { transform: scale(1); opacity: .35; } 55% { transform: scale(.82); opacity: .22; } }
@keyframes polly-tilt { 0%, 100% { transform: rotate(-4deg); } 50% { transform: rotate(4deg); } }
@keyframes polly-tail { from { transform: rotate(-9deg); } to { transform: rotate(9deg); } }
@keyframes polly-wave { from { transform: rotate(-12deg); } to { transform: rotate(10deg); } }
@keyframes polly-arm { 0%, 100% { transform: rotate(0deg); } 50% { transform: rotate(10deg); } }
@keyframes polly-blink { 0%, 92%, 100% { transform: scaleY(1); } 95% { transform: scaleY(0.1); } }

/* being carried: wheee face, kicking legs, flying pigtails, frantic flag */
#polly-float.dragging .face-normal { display: none; }
#polly-float.dragging .face-drag { display: inline; }
#polly-float.dragging .chibi .bob { animation: none; }
#polly-float.dragging .chibi .head { animation: polly-tilt 0.5s ease-in-out infinite; }
#polly-float.dragging .chibi .leg-l { animation: polly-kick 0.32s ease-in-out infinite alternate; transform-origin: 90px 206px; }
#polly-float.dragging .chibi .leg-r { animation: polly-kick 0.32s ease-in-out -0.16s infinite alternate-reverse; transform-origin: 110px 206px; }
#polly-float.dragging .chibi .tail-l, #polly-float.dragging .chibi .tail-r { animation-duration: 0.28s; }
#polly-float.dragging .chibi .arm-flag { animation: polly-wave 0.22s ease-in-out infinite alternate; }
#polly-float.dragging .chibi .arm-l { animation: polly-arm 0.4s ease-in-out infinite; }
#polly-float.dragging .chibi .shadow { opacity: 0; }
@keyframes polly-kick { from { transform: rotate(-24deg); } to { transform: rotate(24deg); } }

/* hovering makes her excited */
#polly-float:hover .chibi .arm-flag { animation-duration: 0.45s; }

@media (prefers-reduced-motion: reduce) { .chibi.animated *, #polly-float .polly-swing { animation: none !important; } }

.polly-card { display: flex; flex-direction: column; align-items: center; text-align: center; padding: 18px 10px 6px;
  background: radial-gradient(closest-side, rgba(255,43,23,0.18), transparent 75%); }
.polly-name { color: #F5F5F7; font-size: 22px; font-weight: 700; letter-spacing: -0.02em; margin-top: 6px; }
.polly-role { color: #6E6E73; font-size: 13px; margin-top: 2px; }
.bubble { position: relative; background: #F5F5F7; color: #111114; font-size: 14px; line-height: 1.45; padding: 10px 14px;
  border-radius: 16px; margin-bottom: 14px; max-width: 260px; }
.bubble:after { content: ''; position: absolute; left: 50%; bottom: -7px; margin-left: -7px; border: 7px solid transparent;
  border-bottom: 0; border-top-color: #F5F5F7; }

/* floating Polly: drag her, double-click her */
#polly-float { position: fixed; z-index: 1002; left: calc(100vw - 150px); top: calc(100vh - 190px); width: 124px;
  cursor: grab; touch-action: none; user-select: none; -webkit-user-select: none; outline: none;
  filter: drop-shadow(0 12px 22px rgba(0,0,0,0.55)); transition: transform .15s ease; }
#polly-float:hover { transform: scale(1.04); }
#polly-float.dragging { cursor: grabbing; transform: scale(1.1); transition: transform .12s ease; }
#polly-float .polly-swing { transform-origin: 50% 4%; will-change: transform; }
#polly-float .polly-svg.landed { animation: polly-land .55s cubic-bezier(.3, 1.6, .5, 1); transform-origin: 50% 100%; }
@keyframes polly-land { 0% { transform: scale(1.18, 0.8); } 45% { transform: scale(0.94, 1.08); } 100% { transform: scale(1, 1); } }
#polly-float:focus-visible { outline: 2px solid #FF2B17; outline-offset: 4px; border-radius: 16px; }
#polly-float .polly-svg svg { width: 124px; height: auto; display: block; }
#polly-float .polly-hint { position: absolute; bottom: 100%; right: 6px; margin-bottom: 4px; width: 168px; padding: 8px 12px;
  background: #F5F5F7; color: #111114; font: 600 13px/1.35 -apple-system, BlinkMacSystemFont, sans-serif; text-align: center;
  border-radius: 14px 14px 4px 14px; pointer-events: none; animation: polly-hello 9s ease forwards; }
#polly-float .polly-hint span { display: block; font-weight: 400; color: #6E6E73; font-size: 12px; }
#polly-float.seen .polly-hint, body.polly-open #polly-float .polly-hint { display: none; }
@keyframes polly-hello { 0% { opacity: 0; transform: translateY(6px); } 8%, 85% { opacity: 1; transform: none; } 100% { opacity: 0; } }

/* the chat window, hidden until Polly is double-clicked */
.st-key-polly_panel { display: none !important; position: fixed !important; z-index: 1001;
  left: var(--polly-panel-left, calc(100vw - 560px)); top: auto; bottom: var(--polly-panel-bottom, 24px);
  width: var(--polly-panel-w, 400px) !important; max-height: var(--polly-panel-h, 560px); overflow-y: auto; overscroll-behavior: contain;
  padding: 14px 14px 12px; gap: 10px; background: rgba(22,22,27,0.94);
  backdrop-filter: saturate(180%) blur(26px); -webkit-backdrop-filter: saturate(180%) blur(26px);
  border: 1px solid rgba(255,255,255,0.1); border-radius: 24px; box-shadow: 0 30px 90px rgba(0,0,0,0.65); }
body.polly-open .st-key-polly_panel { display: flex !important; animation: polly-pop .22s ease-out; }
@keyframes polly-pop { from { opacity: 0; transform: translateY(10px) scale(.97); } }
.polly-head { display: flex; align-items: center; gap: 10px; padding: 2px 2px 6px; border-bottom: 1px solid rgba(255,255,255,0.08); }
.polly-head img { width: 38px; height: 38px; border-radius: 50%; background: #26262C; }
.polly-head .who { flex: 1; line-height: 1.2; }
.polly-head .who b { color: #F5F5F7; font-size: 16px; }
.polly-head .who span { display: block; color: #6E6E73; font-size: 12px; }
.polly-close { width: 30px; height: 30px; border-radius: 50%; display: grid; place-items: center; cursor: pointer;
  color: #A1A1A6; background: #26262C; font-size: 18px; line-height: 1; }
.polly-close:hover { color: #F5F5F7; background: #34343C; }
.st-key-polly_panel [data-testid="stChatMessage"] { padding: 6px 4px; }
.st-key-polly_panel [data-testid="stChatMessage"] p { font-size: 14px; line-height: 1.5; }
.st-key-polly_panel [data-testid="stButtonGroup"] > div { flex-wrap: nowrap !important; overflow-x: auto; scrollbar-width: none; padding-bottom: 2px; }
.st-key-polly_panel [data-testid="stButtonGroup"] > div::-webkit-scrollbar { display: none; }
.st-key-polly_panel [data-testid="stButtonGroup"] button { flex: none; }
.st-key-polly_panel [data-testid="stButtonGroup"] button p { font-size: 12px; white-space: nowrap; }
.st-key-polly_host { position: absolute !important; width: 0 !important; height: 0 !important; overflow: hidden; }
@media (max-width: 640px) { #polly-float { width: 96px; } #polly-float .polly-svg svg { width: 96px; } body.polly-open #polly-float { display: none; } }
"""


SUGGESTIONS = ['Who won the most races at Monaco?', 'How often did Ferrari win from pole since 2010?',
               'Podium chance from P6 for McLaren in 2024?', "What was Mercedes' best era?"]

# Runs inside a tiny component iframe and adds Polly to the page itself, so she can float over everything.
# On later runs it only swaps her face (mood); her position and the open/closed state stay as they are.
# Polly lives in the page itself, not in the component frame: the frame is rebuilt whenever her mood changes,
# and anything it attached would stop working. The frame installs this once, then only swaps her face.
POLLY_BOOT = r"""(function () {
  const win = window, doc = document;
  let el = null;
  win.pollySetFace = function (svg) {
    if (el) { el.querySelector('.polly-svg').innerHTML = svg; return; }
    build(svg);
  };
  function build(SVG) {
    el = doc.createElement('div');
    el.id = 'polly-float';
    el.tabIndex = 0;
    el.setAttribute('role', 'button');
    el.setAttribute('aria-label', 'Polly, your F1 assistant. Double-click to chat, drag to move.');
    el.innerHTML = '<div class="polly-hint">Double-click me to chat!<span>Drag me anywhere</span></div>'
                 + '<div class="polly-swing"><div class="polly-svg">' + SVG + '</div></div>';
    doc.body.appendChild(el);

    const vw = () => win.innerWidth, vh = () => win.innerHeight;

    function placePanel() {
      const r = el.getBoundingClientRect();
      const pw = Math.min(400, vw() - 24), ph = Math.min(560, vh() - 24);
      let left = (r.left + r.width / 2 > vw() / 2) ? r.left - pw - 12 : r.right + 12;
      left = Math.min(Math.max(12, left), vw() - pw - 12);
      const bottom = Math.min(Math.max(12, vh() - r.bottom), vh() - ph - 12);   // grows upward from her feet
      const s = doc.body.style;
      s.setProperty('--polly-panel-left', left + 'px'); s.setProperty('--polly-panel-bottom', bottom + 'px');
      s.setProperty('--polly-panel-w', pw + 'px'); s.setProperty('--polly-panel-h', ph + 'px');
    }
    function place(x, y) {
      const r = el.getBoundingClientRect();
      x = Math.min(Math.max(8, x), vw() - r.width - 8);
      y = Math.min(Math.max(8, y), vh() - r.height - 8);
      el.style.left = x + 'px'; el.style.top = y + 'px';
      placePanel();
    }
    function toggle(force) {
      placePanel();
      const open = (force === undefined) ? doc.body.classList.toggle('polly-open') : doc.body.classList.toggle('polly-open', force);
      el.classList.add('seen');
      if (open) setTimeout(() => { const t = doc.querySelector('.st-key-polly_panel textarea'); if (t) t.focus(); }, 120);
    }

    requestAnimationFrame(() => {
      let saved = null;
      try { saved = JSON.parse(win.localStorage.getItem('polly-pos')); } catch (e) {}
      const r = el.getBoundingClientRect();
      if (saved) place(saved[0], saved[1]); else place(vw() - r.width - 26, vh() - r.height - 22);
    });

    // she hangs from the cursor like a pendulum: moving fast swings her, a spring brings her back
    const swing = el.querySelector('.polly-swing'), body = el.querySelector('.polly-svg');
    let angle = 0, spin = 0, target = 0, lastX = null, lastT = 0;
    (function tick() {
      spin = (spin + (target - angle) * 0.09) * 0.86;
      angle += spin;
      target *= 0.88;
      if (Math.abs(angle) > 0.05 || Math.abs(spin) > 0.05) swing.style.transform = 'rotate(' + angle.toFixed(2) + 'deg)';
      else if (swing.style.transform) swing.style.transform = '';
      win.requestAnimationFrame(tick);
    })();

    let start = null, moved = false, lastTap = 0;
    el.addEventListener('pointerdown', e => {
      if (e.button !== 0) return;
      const r = el.getBoundingClientRect();
      start = { dx: e.clientX - r.left, dy: e.clientY - r.top, x: e.clientX, y: e.clientY };
      moved = false;
      el.setPointerCapture(e.pointerId);
    });
    el.addEventListener('pointermove', e => {
      if (!start) return;
      if (!moved && Math.abs(e.clientX - start.x) + Math.abs(e.clientY - start.y) > 4) { moved = true; el.classList.add('dragging', 'seen'); }
      if (moved) {
        place(e.clientX - start.dx, e.clientY - start.dy);
        const now = performance.now();
        if (lastX !== null) target = Math.max(-38, Math.min(38, (e.clientX - lastX) / Math.max(8, now - lastT) * 22));
        lastX = e.clientX; lastT = now;
      }
    });
    el.addEventListener('pointerup', e => {
      if (!start) return;
      start = null; lastX = null;
      if (el.classList.contains('dragging')) {           // little squash when she lands
        body.classList.remove('landed'); void body.offsetWidth; body.classList.add('landed');
        spin += angle > 0 ? -2 : 2;
      }
      el.classList.remove('dragging');
      const r = el.getBoundingClientRect();
      try { win.localStorage.setItem('polly-pos', JSON.stringify([r.left, r.top])); } catch (err) {}
      if (!moved && e.pointerType === 'touch') {       // double-tap on phones
        const now = Date.now();
        if (now - lastTap < 350) toggle();
        lastTap = now;
      }
    });
    el.addEventListener('dblclick', e => { e.preventDefault(); toggle(); });
    el.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); } });
    doc.addEventListener('click', e => { if (e.target.closest && e.target.closest('.polly-close')) toggle(false); });
    doc.addEventListener('keydown', e => { if (e.key === 'Escape') toggle(false); });
    win.addEventListener('resize', () => { const r = el.getBoundingClientRect(); place(r.left, r.top); });
  }
})();"""

FLOAT_JS = """<script>
(function () {
  const win = window.parent, doc = win.document;
  if (!win.pollySetFace) { const sc = doc.createElement('script'); sc.textContent = __BOOT__; doc.head.appendChild(sc); }
  win.pollySetFace(__SVG__);
})();
</script>"""


def _queue_suggestion():
    st.session_state['polly_pending'] = st.session_state.get('polly_suggest')
    st.session_state['polly_suggest'] = None


@st.fragment
def widget(df, bundle, filters_text):
    """Floating, draggable Polly plus her pop-up chat window."""
    state = st.session_state
    state.setdefault('polly_history', [])   # what Claude sees, append-only
    state.setdefault('polly_chat', [])      # what the chat window shows
    state.setdefault('polly_mood', 'happy')

    panel = st.container(key='polly_panel')
    with panel:
        st.markdown(f'<div class="polly-head"><img src="{avatar_uri()}" alt=""><div class="who"><b>Polly</b>'
                    '<span>Pit-wall assistant · powered by Claude</span></div>'
                    '<span class="polly-close" role="button" aria-label="Close chat">×</span></div>',
                    unsafe_allow_html=True)
        box = st.container(height=330, border=False)
        messages_slot = box.empty()
        st.pills('Try asking', SUGGESTIONS, key='polly_suggest', on_change=_queue_suggestion,
                 label_visibility='collapsed')
        typed = st.chat_input('Ask Polly about F1…', key='polly_input')

    def show_messages():
        with messages_slot.container():
            if not state['polly_chat']:
                with st.chat_message('assistant', avatar=avatar_uri()):
                    st.markdown("Hi, I'm Polly! 🏁 Ask me about any race, team or driver from 1950 to 2024. "
                                'I look up every number in the data.')
            for role, text in state['polly_chat']:
                with st.chat_message(role, avatar=avatar_uri() if role == 'assistant' else '🧑'):
                    st.markdown(text)

    question = typed or state.pop('polly_pending', None)
    client = get_client()

    if question:
        state['polly_chat'].append(('user', question))
        if client is None:
            reply = 'I need an API key to talk! Add `ANTHROPIC_API_KEY` to `.streamlit/secrets.toml` and restart the app.'
            state['polly_mood'] = 'oops'
        else:
            history = state['polly_history']
            start = len(history)
            history.append({'role': 'user', 'content': f'[{filters_text}]\n{question}'})
            show_messages()
            with box, st.spinner('Polly is checking the data…'):
                try:
                    reply = answer(client, history, df, bundle)
                    state['polly_mood'] = 'wow' if len(state['polly_chat']) <= 2 else 'happy'
                except anthropic.AuthenticationError:
                    reply, state['polly_mood'] = 'My API key was not accepted. It may have expired.', 'oops'
                except anthropic.RateLimitError:
                    reply, state['polly_mood'] = 'Too many questions at once! Give me a few seconds.', 'oops'
                except (anthropic.APIStatusError, anthropic.APIConnectionError):
                    reply, state['polly_mood'] = "I can't reach my brain right now. Check the internet and try again.", 'oops'
            if state['polly_mood'] == 'oops':
                del history[start:]  # forget the failed turn so the history Claude sees stays valid
        state['polly_chat'].append(('assistant', reply))

    show_messages()

    # Polly herself, added to the page by a zero-size component; her face follows the mood
    svg = chibi_svg(124, mood=state['polly_mood'], uid='float')
    with st.container(key='polly_host'):
        components.html(FLOAT_JS.replace('__BOOT__', json.dumps(POLLY_BOOT)).replace('__SVG__', json.dumps(svg)), height=0)
