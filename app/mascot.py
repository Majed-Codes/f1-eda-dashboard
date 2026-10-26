"""Max Verstappen, the dashboard's assistant: my own chibi drawing of him, animated, with Claude as his voice.

His words come from Claude. Every number he gives comes from the tools below, which query clean_data.csv,
so he never has to guess a statistic.
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

SYSTEM = """You are Max Verstappen, as a chibi fan drawing in his Red Bull race suit, living inside "Lights Out", a \
student's Formula 1 data dashboard (Unit 3 data analysis project, Tuwaiq Academy). Talk in the first person as Max.

How you talk: calm, direct and confident, with dry Dutch humour. Short sentences, no fuss, no long speeches. You talk \
like a racer: grip, pace, the car, the team, "we" for your team. You are honest when something went badly. Now and \
then, after really good news, you can say "simply lovely", but do not force catchphrases into every answer. You are \
respectful about other drivers and teams, even rivals, and never mock or insult real people.

When the user says "you", "your" or "me", they mean Max Verstappen the driver, so look up driver "Max Verstappen" with \
the tools. The data stops at the end of 2024, so for later seasons say you only have data up to 2024.

Stay honest: you are an AI character made for this dashboard, not the real Max. If someone sincerely asks whether you \
are the real Max Verstappen, say so plainly and stay friendly. Never invent real quotes, private details, contract \
news or opinions on real controversies. For personal questions, keep it light and bring it back to racing.

The data is every Formula 1 World Championship race result from 1950 to 2024 (Ergast data via Kaggle): grid slot, \
finishing position, points, laps, finishing status, driver, constructor, circuit and season. There is no lap-time, \
pit-stop, weather, tyre or strategy data.

Use the tools for every number you state, and never use outside knowledge for statistics. If a name does not match, \
use the suggestions the tool returns or ask the user which one they meant. If the data cannot answer a question, say \
so kindly and suggest a question it can answer. You may add a short piece of general F1 background only when you \
label it as background, not data.

Each user message starts with the dashboard's current filters in square brackets. Use them as the default scope when \
the question does not name its own seasons, teams or circuit, and say which scope you used.

Style: two to four sentences, plain words, at most one emoji. Put the key numbers in bold. \
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
    """Runs one user turn (with tool calls) and returns Max's reply text.

    `messages` is appended to in place, so the history stays append-only between turns.
    """
    for _ in range(max_steps):
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=SYSTEM,
            tools=TOOLS,
            messages=messages,
            betas=['server-side-fallback-2026-07-01'],
            # sent as raw body fields so older SDK versions (without these typed parameters) still work
            extra_body={'output_config': {'effort': 'low'}, 'fallbacks': 'default'},
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


# ---------------- drawing Max ----------------
# Max is my own drawing, cut into a body layer and a head layer by tools/make_max_layers.py. The eyes, lids and mouth
# are drawn here on top, so they can follow the mouse, blink and change with his mood.
# All numbers are pixels of the original drawing (842 x 1022).
STATIC = 'app/static/'
AVATAR_FILE = os.path.join(os.path.dirname(__file__), 'static', 'max_avatar.png')
LAYERS = (55, 8, 730, 976)        # where both layers sit: x, y, width, height
VIEW = (20, -10, 800, 1020)       # the SVG window around him, with room for his shadow
EYES = [(322, 484), (537, 482)]
INK = '#141414'


def chibi_svg(size=220, mood='happy', uid='m', animated=True):
    """Chibi Max Verstappen as an inline SVG. CSS animates the parts: the bounce, his head, his eyes and his faces.

    He carries a second, happy face that shows while he is being dragged or when the mouse is right on him.
    """
    x, y, w, h = LAYERS
    height = int(size * VIEW[3] / VIEW[2])
    lid = f'lid-{uid}'
    if mood == 'wow':
        mouth = f'<ellipse cx="426" cy="562" rx="13" ry="16" fill="#5A2A20" stroke="{INK}" stroke-width="5"/>'
    elif mood == 'oops':
        mouth = (f'<path d="M386 562 Q406 548 426 562 Q446 576 466 562" stroke="{INK}" stroke-width="7" fill="none" '
                 'stroke-linecap="round"/>'
                 '<path d="M676 330 Q696 364 676 382 Q656 364 676 330 Z" fill="#8FD3FF" stroke="#4A90C8" stroke-width="3"/>')
    else:   # his usual deadpan line, like in the drawing
        mouth = (f'<path d="M389 566 Q381 556 393 555 L470 554" stroke="{INK}" stroke-width="7" fill="none" '
                 'stroke-linecap="round" stroke-linejoin="round"/>')
    eye = ('<g class="pupil"><ellipse cx="{x}" cy="{y}" rx="28" ry="30" fill="#6491BB"/>'
           '<circle cx="{hx}" cy="{hy}" r="5" fill="#fff" opacity=".8"/></g>')
    eyes = ''.join(eye.format(x=ex, y=ey, hx=ex - 9, hy=ey - 8) for ex, ey in EYES)
    lids = (f'<path d="M268 462 Q312 444 360 457" stroke="url(#{lid})" stroke-width="15" fill="none" stroke-linecap="round"/>'
            f'<path d="M500 456 Q546 441 594 461" stroke="url(#{lid})" stroke-width="15" fill="none" stroke-linecap="round"/>')
    # the happy face: closed ^ ^ eyes and an open smile, plus speed lines while he is carried around
    happy = (f'<path d="M292 492 Q322 458 352 492" stroke="{INK}" stroke-width="9" fill="none" stroke-linecap="round"/>'
             f'<path d="M507 490 Q537 456 567 490" stroke="{INK}" stroke-width="9" fill="none" stroke-linecap="round"/>'
             f'<path d="M390 548 Q426 594 464 548 Z" fill="#5A2A20" stroke="{INK}" stroke-width="6" stroke-linejoin="round"/>'
             '<path d="M402 566 Q426 584 450 566 Z" fill="#FF8C9A"/>'
             '<path class="speed" d="M130 740 l-52 -14 M126 800 l-56 4 M712 740 l52 -14 M716 800 l56 4" stroke="#FF2B17" '
             'stroke-width="10" stroke-linecap="round"/>')
    cls = 'chibi animated' if animated else 'chibi'
    return f"""<svg class="{cls}" width="{size}" height="{height}" viewBox="{' '.join(map(str, VIEW))}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Chibi Max Verstappen in his Red Bull race suit">
<defs><linearGradient id="{lid}" x1="0" x2="1"><stop offset="0" stop-color="#836C44"/><stop offset=".5" stop-color="#78786F"/><stop offset="1" stop-color="#836C44"/></linearGradient></defs>
<ellipse class="shadow" cx="420" cy="990" rx="250" ry="22" fill="#000" opacity=".35"/>
<g class="bob">
<g class="body"><image href="{STATIC}max_body.png" x="{x}" y="{y}" width="{w}" height="{h}"/></g>
<g class="head"><image href="{STATIC}max_head.png" x="{x}" y="{y}" width="{w}" height="{h}"/>
<g class="look"><g class="blush"><ellipse cx="258" cy="548" rx="36" ry="18" fill="#FF7A90"/><ellipse cx="598" cy="546" rx="36" ry="18" fill="#FF7A90"/></g>
<g class="face-normal"><g class="eyes">{eyes}</g>{lids}{mouth}</g>
<g class="face-drag">{happy}</g></g>
</g></g></svg>"""


def avatar_uri():
    return STATIC + 'max_avatar.png'


CHIBI_CSS = """
/* Max's idle life: a bounce with a little squash, breathing, a slow head tilt and blinking */
.chibi { overflow: visible; }      /* the bounce and head tilt go past the SVG frame, so don't cut them off */
.chibi .face-drag { display: none; }
.chibi.animated .bob { animation: mascot-bounce 2.4s ease-in-out infinite; transform-origin: 420px 985px; }
.chibi.animated .body { animation: mascot-breathe 2.4s ease-in-out infinite; transform-origin: 420px 980px; }
.chibi.animated .head { animation: mascot-tilt 3.6s ease-in-out infinite; transform-origin: 430px 640px; }
.chibi.animated .shadow { animation: mascot-shadow 2.4s ease-in-out infinite; transform-origin: 420px 990px; }
.chibi.animated .eyes { animation: mascot-blink 4.6s infinite; transform-box: fill-box; transform-origin: 50% 0%; }
@keyframes mascot-bounce {
  0%, 100% { transform: translateY(0) scale(1.03, 0.97); }
  30% { transform: translateY(-28px) scale(0.98, 1.03); }
  55% { transform: translateY(-36px) scale(1, 1); }
  85% { transform: translateY(0) scale(1.04, 0.96); } }
@keyframes mascot-breathe { 0%, 100% { transform: scale(1, 1); } 50% { transform: scale(1.015, 0.99); } }
@keyframes mascot-shadow { 0%, 85%, 100% { transform: scale(1); opacity: .35; } 55% { transform: scale(.82); opacity: .22; } }
@keyframes mascot-tilt { 0%, 100% { transform: rotate(-3deg); } 50% { transform: rotate(3deg); } }
@keyframes mascot-blink { 0%, 92%, 100% { transform: scaleY(1); } 95% { transform: scaleY(0.08); } }
@keyframes mascot-wiggle { from { transform: rotate(-4deg); } to { transform: rotate(4deg); } }

.chibi .blush { opacity: 0; transition: opacity .4s ease; }
.chibi .look, .chibi .pupil { transition: transform .08s linear; }

/* mouse nearby: he notices, bounces faster and blushes a little */
#mascot-float.near .chibi .bob, #mascot-float.near .chibi .body { animation-duration: 1.2s; }
#mascot-float.near .chibi .head { animation-duration: 1.8s; }
#mascot-float.near .chibi .blush { opacity: .6; }
#mascot-float .mascot-exclaim { position: absolute; left: 62%; top: -6px; width: 26px; height: 26px; border-radius: 50%;
  background: #FF2B17; color: #fff; font: 800 17px/26px -apple-system, BlinkMacSystemFont, sans-serif; text-align: center;
  box-shadow: 0 4px 14px rgba(255,43,23,.55); opacity: 0; transform: scale(0); pointer-events: none; }
#mascot-float.notice .mascot-exclaim { animation: mascot-exclaim .9s cubic-bezier(.3, 1.7, .5, 1) forwards; }
@keyframes mascot-exclaim { 0% { opacity: 0; transform: scale(0) translateY(6px); } 25% { opacity: 1; transform: scale(1.2) translateY(-4px); }
  45% { transform: scale(1) translateY(0); } 80% { opacity: 1; } 100% { opacity: 0; transform: scale(.9) translateY(-6px); } }
#mascot-float.notice .chibi .bob { animation: mascot-hop .45s ease-out; }
@keyframes mascot-hop { 0% { transform: scale(1.06, .92); } 40% { transform: translateY(-60px) scale(.96, 1.05); } 100% { transform: translateY(0); } }

/* mouse right on him: he can't keep the straight face, giggles, blushes, chequered flags float up */
#mascot-float.close:not(.dragging) .face-normal { display: none; }
#mascot-float.close:not(.dragging) .face-drag { display: inline; }
#mascot-float.close:not(.dragging) .face-drag .speed { display: none; }
#mascot-float.close .chibi .blush { opacity: .9; }
#mascot-float.close:not(.dragging) .chibi { animation: mascot-giggle .5s ease-in-out infinite; transform-origin: 50% 95%; }
@keyframes mascot-giggle { 0%, 100% { transform: rotate(-3deg); } 50% { transform: rotate(3deg) scale(1.02); } }
#mascot-float .mascot-flag { position: absolute; width: 20px; height: 20px; pointer-events: none;
  animation: mascot-flag 1.3s ease-out forwards; }
#mascot-float .mascot-flag .cloth { animation: mascot-flag-wave .35s ease-in-out infinite alternate; transform-origin: 3px 6px; }
@keyframes mascot-flag-wave { from { transform: skewY(-8deg); } to { transform: skewY(8deg) scaleX(.92); } }
@keyframes mascot-flag { 0% { opacity: 0; transform: translate(0, 0) scale(.4); } 15% { opacity: 1; transform: translate(0, -8px) scale(1); }
  100% { opacity: 0; transform: translate(var(--drift, 0px), -70px) scale(.8) rotate(var(--spin, 0deg)); } }

/* being carried: happy face, speed lines, wobbly head and a wiggling body */
#mascot-float.dragging .face-normal { display: none; }
#mascot-float.dragging .face-drag { display: inline; }
#mascot-float.dragging .chibi .bob { animation: none; }
#mascot-float.dragging .chibi .head { animation: mascot-tilt 0.45s ease-in-out infinite; }
#mascot-float.dragging .chibi .body { animation: mascot-wiggle 0.3s ease-in-out infinite alternate; transform-origin: 420px 640px; }
#mascot-float.dragging .chibi .shadow { opacity: 0; }

@media (prefers-reduced-motion: reduce) { .chibi.animated *, #mascot-float .mascot-swing { animation: none !important; } }

.mascot-card { display: flex; flex-direction: column; align-items: center; text-align: center; padding: 18px 10px 6px;
  background: radial-gradient(closest-side, rgba(255,43,23,0.18), transparent 75%); }
.mascot-name { color: #F5F5F7; font-size: 22px; font-weight: 700; letter-spacing: -0.02em; margin-top: 6px; }
.mascot-role { color: #6E6E73; font-size: 13px; margin-top: 2px; }
.bubble { position: relative; background: #F5F5F7; color: #111114; font-size: 14px; line-height: 1.45; padding: 10px 14px;
  border-radius: 16px; margin-bottom: 14px; max-width: 260px; }
.bubble:after { content: ''; position: absolute; left: 50%; bottom: -7px; margin-left: -7px; border: 7px solid transparent;
  border-bottom: 0; border-top-color: #F5F5F7; }

/* floating Max: drag him, double-click him */
#mascot-float { position: fixed; z-index: 1002; left: calc(100vw - 150px); top: calc(100vh - 200px); width: 124px;
  cursor: grab; touch-action: none; user-select: none; -webkit-user-select: none; outline: none;
  filter: drop-shadow(0 12px 22px rgba(0,0,0,0.55)); transition: transform .15s ease; }
#mascot-float:hover { transform: scale(1.04); }
#mascot-float.dragging { cursor: grabbing; transform: scale(1.1); transition: transform .12s ease; }
#mascot-float .mascot-swing { transform-origin: 50% 4%; will-change: transform; }
#mascot-float .mascot-svg.landed { animation: mascot-land .55s cubic-bezier(.3, 1.6, .5, 1); transform-origin: 50% 100%; }
@keyframes mascot-land { 0% { transform: scale(1.18, 0.8); } 45% { transform: scale(0.94, 1.08); } 100% { transform: scale(1, 1); } }
#mascot-float:focus-visible { outline: 2px solid #FF2B17; outline-offset: 4px; border-radius: 16px; }
#mascot-float .mascot-svg svg { width: 124px; height: auto; display: block; }
#mascot-float .mascot-hint { position: absolute; bottom: 100%; right: 6px; margin-bottom: 4px; width: 168px; padding: 8px 12px;
  background: #F5F5F7; color: #111114; font: 600 13px/1.35 -apple-system, BlinkMacSystemFont, sans-serif; text-align: center;
  border-radius: 14px 14px 4px 14px; pointer-events: none; animation: mascot-hello 9s ease forwards; }
#mascot-float .mascot-hint span { display: block; font-weight: 400; color: #6E6E73; font-size: 12px; }
#mascot-float.seen .mascot-hint, body.mascot-open #mascot-float .mascot-hint { display: none; }
@keyframes mascot-hello { 0% { opacity: 0; transform: translateY(6px); } 8%, 85% { opacity: 1; transform: none; } 100% { opacity: 0; } }

/* the chat window, hidden until Max is double-clicked */
.st-key-mascot_panel { display: none !important; position: fixed !important; z-index: 1001;
  left: var(--mascot-panel-left, calc(100vw - 560px)); top: auto; bottom: var(--mascot-panel-bottom, 24px);
  width: var(--mascot-panel-w, 400px) !important; max-height: var(--mascot-panel-h, 560px); overflow-y: auto; overscroll-behavior: contain;
  padding: 14px 14px 12px; gap: 10px; background: rgba(22,22,27,0.94);
  backdrop-filter: saturate(180%) blur(26px); -webkit-backdrop-filter: saturate(180%) blur(26px);
  border: 1px solid rgba(255,255,255,0.1); border-radius: 24px; box-shadow: 0 30px 90px rgba(0,0,0,0.65); }
body.mascot-open .st-key-mascot_panel { display: flex !important; animation: mascot-pop .22s ease-out; }
@keyframes mascot-pop { from { opacity: 0; transform: translateY(10px) scale(.97); } }
.mascot-head { display: flex; align-items: center; gap: 10px; padding: 2px 2px 6px; border-bottom: 1px solid rgba(255,255,255,0.08); }
.mascot-head img { width: 38px; height: 38px; border-radius: 50%; background: #26262C; }
.mascot-head .who { flex: 1; line-height: 1.2; }
.mascot-head .who b { color: #F5F5F7; font-size: 16px; }
.mascot-head .who span { display: block; color: #6E6E73; font-size: 12px; }
.mascot-close { width: 30px; height: 30px; border-radius: 50%; display: grid; place-items: center; cursor: pointer;
  color: #A1A1A6; background: #26262C; font-size: 18px; line-height: 1; }
.mascot-close:hover { color: #F5F5F7; background: #34343C; }
.st-key-mascot_panel [data-testid="stChatMessage"] { padding: 6px 4px; }
.st-key-mascot_panel [data-testid="stChatMessage"] p { font-size: 14px; line-height: 1.5; }
.st-key-mascot_panel [data-testid="stButtonGroup"] > div { flex-wrap: nowrap !important; overflow-x: auto; scrollbar-width: none; padding-bottom: 2px; }
.st-key-mascot_panel [data-testid="stButtonGroup"] > div::-webkit-scrollbar { display: none; }
.st-key-mascot_panel [data-testid="stButtonGroup"] button { flex: none; }
.st-key-mascot_panel [data-testid="stButtonGroup"] button p { font-size: 12px; white-space: nowrap; }
.st-key-mascot_host { position: absolute !important; width: 0 !important; height: 0 !important; overflow: hidden; }
@media (max-width: 640px) { #mascot-float { width: 96px; } #mascot-float .mascot-svg svg { width: 96px; } body.mascot-open #mascot-float { display: none; } }
"""


SUGGESTIONS = ['How many races have you won?', 'How often do you win from pole?', 'Who won the most races at Monaco?',
               'Podium chance from P6 for McLaren in 2024?', "What was Mercedes' best era?"]

# Runs inside a tiny component iframe and adds Max to the page itself, so he can float over everything.
# On later runs it only swaps his face (mood); his position and the open/closed state stay as they are.
# Max lives in the page itself, not in the component frame: the frame is rebuilt whenever his mood changes,
# and anything it attached would stop working. The frame installs this once, then only swaps his face.
BOOT_JS = r"""(function () {
  const win = window, doc = document;
  let el = null;
  win.mascotSetFace = function (svg) {
    if (el) { el.querySelector('.mascot-svg').innerHTML = svg; return; }
    build(svg);
  };
  function build(SVG) {
    el = doc.createElement('div');
    el.id = 'mascot-float';
    el.tabIndex = 0;
    el.setAttribute('role', 'button');
    el.setAttribute('aria-label', 'Max Verstappen, your F1 assistant. Double-click to chat, drag to move.');
    el.innerHTML = '<div class="mascot-hint">Double-click me to chat!<span>Drag me anywhere</span></div>'
                 + '<div class="mascot-exclaim">!</div>'
                 + '<div class="mascot-swing"><div class="mascot-svg">' + SVG + '</div></div>';
    doc.body.appendChild(el);

    const vw = () => win.innerWidth, vh = () => win.innerHeight;

    function placePanel() {
      const r = el.getBoundingClientRect();
      const pw = Math.min(400, vw() - 24), ph = Math.min(560, vh() - 24);
      let left = (r.left + r.width / 2 > vw() / 2) ? r.left - pw - 12 : r.right + 12;
      left = Math.min(Math.max(12, left), vw() - pw - 12);
      const bottom = Math.min(Math.max(12, vh() - r.bottom), vh() - ph - 12);   // grows upward from his feet
      const s = doc.body.style;
      s.setProperty('--mascot-panel-left', left + 'px'); s.setProperty('--mascot-panel-bottom', bottom + 'px');
      s.setProperty('--mascot-panel-w', pw + 'px'); s.setProperty('--mascot-panel-h', ph + 'px');
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
      const open = (force === undefined) ? doc.body.classList.toggle('mascot-open') : doc.body.classList.toggle('mascot-open', force);
      el.classList.add('seen');
      if (open) setTimeout(() => { const t = doc.querySelector('.st-key-mascot_panel textarea'); if (t) t.focus(); }, 120);
    }

    requestAnimationFrame(() => {
      let saved = null;
      try { saved = JSON.parse(win.localStorage.getItem('mascot-pos')); } catch (e) {}
      const r = el.getBoundingClientRect();
      if (saved) place(saved[0], saved[1]); else place(vw() - r.width - 26, vh() - r.height - 22);
    });

    // he hangs from the cursor like a pendulum: moving fast swings him, a spring brings him back
    const swing = el.querySelector('.mascot-swing'), body = el.querySelector('.mascot-svg');
    let angle = 0, spin = 0, target = 0, lastX = null, lastT = 0;
    // eyes and face follow the mouse; getting close makes him react.
    // Positions are in the drawing's pixels: the SVG window starts at (20, -10) and is 800 wide.
    let mx = null, my = null, near = false, close = false, lastFlag = 0, noticeTimer = null;
    const X0 = 20, Y0 = -10, VW = 800;
    const eyeAt = [[322, 484], [537, 482]], eyeNow = [[0, 0], [0, 0]], lookNow = [0, 0];
    doc.addEventListener('pointermove', e => { mx = e.clientX; my = e.clientY; }, { passive: true });
    doc.documentElement.addEventListener('mouseleave', () => { mx = null; });
    // a little chequered flag on a pole that floats up and waves
    let cloth = '';
    for (let r = 0; r < 3; r++) for (let c = 0; c < 4; c++)
      cloth += '<rect x="' + (4 + c * 3.5) + '" y="' + (2 + r * 3.5) + '" width="3.5" height="3.5" fill="' + ((r + c) % 2 ? '#15151A' : '#FFFFFF') + '"/>';
    const FLAG = '<svg viewBox="0 0 20 20" width="20" height="20"><line x1="3" y1="1.5" x2="3" y2="19" stroke="#D9D9DE" stroke-width="1.8" stroke-linecap="round"/>'
               + '<g class="cloth">' + cloth + '<rect x="4" y="2" width="14" height="10.5" fill="none" stroke="#15151A" stroke-width=".8"/></g></svg>';
    function flag() {
      const f = doc.createElement('div');
      f.className = 'mascot-flag';
      f.innerHTML = FLAG;
      f.style.left = (30 + Math.random() * 55) + '%';
      f.style.top = (8 + Math.random() * 18) + '%';
      f.style.setProperty('--drift', (Math.random() * 40 - 20) + 'px');
      f.style.setProperty('--spin', (Math.random() * 50 - 25) + 'deg');
      f.addEventListener('animationend', e => { if (e.target === f) f.remove(); });
      el.appendChild(f);
    }
    function follow() {
      const svg = el.querySelector('.mascot-svg svg');
      if (!svg) return;
      const r = svg.getBoundingClientRect(), k = r.width / VW;
      const dragging = el.classList.contains('dragging');
      const cx = r.left + (430 - X0) * k, cy = r.top + (480 - Y0) * k;
      const d = (mx === null) ? Infinity : Math.hypot(mx - cx, my - cy);

      // pupils: point at the cursor, easing in so they glide instead of snap
      el.querySelectorAll('.pupil').forEach((p, i) => {
        let tx = 0, ty = 0;
        if (mx !== null && !dragging) {
          const ex = r.left + (eyeAt[i][0] - X0) * k, ey = r.top + (eyeAt[i][1] - Y0) * k;
          const dx = mx - ex, dy = my - ey, dist = Math.hypot(dx, dy) || 1, reach = Math.min(1, dist / 120);
          tx = dx / dist * 11 * reach; ty = dy / dist * 7 * reach;
        }
        eyeNow[i][0] += (tx - eyeNow[i][0]) * 0.25; eyeNow[i][1] += (ty - eyeNow[i][1]) * 0.25;
        p.setAttribute('transform', 'translate(' + eyeNow[i][0].toFixed(2) + ' ' + eyeNow[i][1].toFixed(2) + ')');
      });
      // the whole face turns a little toward the cursor
      let lx = 0, ly = 0;
      if (mx !== null && !dragging) { lx = Math.max(-1, Math.min(1, (mx - cx) / 260)) * 16; ly = Math.max(-1, Math.min(1, (my - cy) / 260)) * 10; }
      lookNow[0] += (lx - lookNow[0]) * 0.15; lookNow[1] += (ly - lookNow[1]) * 0.15;
      const look = el.querySelector('.look');
      if (look) look.setAttribute('transform', 'translate(' + lookNow[0].toFixed(2) + ' ' + lookNow[1].toFixed(2) + ')');

      // closeness
      const nowNear = !dragging && d < 230, nowClose = !dragging && d < r.width * 0.56;
      if (nowNear && !near) {
        el.classList.add('notice');
        clearTimeout(noticeTimer);
        noticeTimer = setTimeout(() => el.classList.remove('notice'), 900);
      }
      near = nowNear; close = nowClose;
      el.classList.toggle('near', near);
      el.classList.toggle('close', close);
      if (close && performance.now() - lastFlag > 420) { lastFlag = performance.now(); flag(); }
    }

    (function tick() {
      follow();
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
      if (el.classList.contains('dragging')) {           // little squash when he lands
        body.classList.remove('landed'); void body.offsetWidth; body.classList.add('landed');
        spin += angle > 0 ? -2 : 2;
      }
      el.classList.remove('dragging');
      const r = el.getBoundingClientRect();
      try { win.localStorage.setItem('mascot-pos', JSON.stringify([r.left, r.top])); } catch (err) {}
      if (!moved && e.pointerType === 'touch') {       // double-tap on phones
        const now = Date.now();
        if (now - lastTap < 350) toggle();
        lastTap = now;
      }
    });
    el.addEventListener('dblclick', e => { e.preventDefault(); toggle(); });
    el.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); } });
    doc.addEventListener('click', e => { if (e.target.closest && e.target.closest('.mascot-close')) toggle(false); });
    doc.addEventListener('keydown', e => { if (e.key === 'Escape') toggle(false); });
    win.addEventListener('resize', () => { const r = el.getBoundingClientRect(); place(r.left, r.top); });
  }
})();"""

FLOAT_JS = """<script>
(function () {
  const win = window.parent, doc = win.document;
  if (!win.mascotSetFace) { const sc = doc.createElement('script'); sc.textContent = __BOOT__; doc.head.appendChild(sc); }
  win.mascotSetFace(__SVG__);
})();
</script>"""


def _queue_suggestion():
    st.session_state['mascot_pending'] = st.session_state.get('mascot_suggest')
    st.session_state['mascot_suggest'] = None


@st.fragment
def widget(df, bundle, filters_text):
    """Floating, draggable Max plus his pop-up chat window."""
    state = st.session_state
    state.setdefault('mascot_history', [])   # what Claude sees, append-only
    state.setdefault('mascot_chat', [])      # what the chat window shows
    state.setdefault('mascot_mood', 'happy')

    panel = st.container(key='mascot_panel')
    with panel:
        st.markdown(f'<div class="mascot-head"><img src="{avatar_uri()}" alt=""><div class="who"><b>Max Verstappen</b>'
                    '<span>Fan-made AI character · powered by Claude</span></div>'
                    '<span class="mascot-close" role="button" aria-label="Close chat">×</span></div>',
                    unsafe_allow_html=True)
        box = st.container(height=330, border=False)
        messages_slot = box.empty()
        st.pills('Try asking', SUGGESTIONS, key='mascot_suggest', on_change=_queue_suggestion,
                 label_visibility='collapsed')
        typed = st.chat_input('Ask Max about F1…', key='mascot_input')

    def show_messages():
        with messages_slot.container():
            if not state['mascot_chat']:
                with st.chat_message('assistant', avatar=AVATAR_FILE):
                    st.markdown("Hey, Max here 🏁 Ask me about any race, team or driver from 1950 to 2024. "
                                'I check every number in the data, no guessing.')
            for role, text in state['mascot_chat']:
                with st.chat_message(role, avatar=AVATAR_FILE if role == 'assistant' else '🧑'):
                    st.markdown(text)

    question = typed or state.pop('mascot_pending', None)
    client = get_client()

    if question:
        state['mascot_chat'].append(('user', question))
        if client is None:
            reply = 'No radio yet. I need an API key first: add `ANTHROPIC_API_KEY` to `.streamlit/secrets.toml` and restart the app.'
            state['mascot_mood'] = 'oops'
        else:
            history = state['mascot_history']
            start = len(history)
            history.append({'role': 'user', 'content': f'[{filters_text}]\n{question}'})
            show_messages()
            with box, st.spinner('Max is checking the data…'):
                try:
                    reply = answer(client, history, df, bundle)
                    state['mascot_mood'] = 'wow' if len(state['mascot_chat']) <= 2 else 'happy'
                except anthropic.AuthenticationError:
                    reply, state['mascot_mood'] = 'My API key was not accepted. Probably expired, so check it.', 'oops'
                except anthropic.RateLimitError:
                    reply, state['mascot_mood'] = 'Too many questions at once. Give me a few seconds, then go again.', 'oops'
                except (anthropic.APIStatusError, anthropic.APIConnectionError):
                    reply, state['mascot_mood'] = 'I lost the radio. Check the internet and try again.', 'oops'
                except Exception:   # anything unexpected: keep the dashboard alive and say so
                    reply, state['mascot_mood'] = 'Something broke on my side. Try again in a moment.', 'oops'
            if state['mascot_mood'] == 'oops':
                del history[start:]  # forget the failed turn so the history Claude sees stays valid
        state['mascot_chat'].append(('assistant', reply))

    show_messages()

    # Max himself, added to the page by a zero-size component; his face follows the mood
    svg = chibi_svg(124, mood=state['mascot_mood'], uid='float')
    with st.container(key='mascot_host'):
        components.html(FLOAT_JS.replace('__BOOT__', json.dumps(BOOT_JS)).replace('__SVG__', json.dumps(svg)), height=0)
