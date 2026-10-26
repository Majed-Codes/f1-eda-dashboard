"""Podium or Not? A 10-round guessing game against the podium model, using real 2010-2024 starts."""
import numpy as np
import pandas as pd
import streamlit as st

from polly import chibi_svg

ROUNDS = 10


def _new_start(pool):
    rng = np.random.default_rng()
    # podiums are rare (14%), so they are picked a bit more often to keep the game interesting
    want = rng.random() < 0.45
    options = pool[pool['podium'] == want]
    return int(options.index[rng.integers(len(options))])


def _model_chance(bundle, row):
    model, top_teams, columns, _ = bundle
    group = row['team'] if row['team'] in top_teams else 'Other'
    x = pd.get_dummies(pd.DataFrame({'grid_clean': [row['grid_clean']], 'team_group': [group], 'year': [row['year']]}))
    return float(model.predict_proba(x.reindex(columns=columns, fill_value=0))[0, 1])


def _reset():
    for key in ['g_round', 'g_you', 'g_model', 'g_pick', 'g_guess', 'g_log']:
        st.session_state.pop(key, None)


def _guess(choice):
    st.session_state['g_guess'] = choice


def _next():
    st.session_state['g_round'] += 1
    st.session_state['g_pick'] = None
    st.session_state['g_guess'] = None


@st.fragment
def play(df, bundle):
    s = st.session_state
    pool = df[(df['year'] >= 2010) & df['starter'] & df['grid_clean'].between(1, 20)]
    s.setdefault('g_round', 1)
    s.setdefault('g_you', 0)
    s.setdefault('g_model', 0)
    s.setdefault('g_log', [])
    s.setdefault('g_guess', None)
    if s.get('g_pick') is None:
        s['g_pick'] = _new_start(pool)

    st.markdown('<div class="eyebrow">Mini game</div><div class="section-title">Podium or not?</div>'
                '<div class="lede">A real start from 2010–2024. You see the driver, the team and the grid slot. '
                'Did it end on the podium? Beat the model over <b>10 rounds</b>.</div>', unsafe_allow_html=True)

    # final score
    if s['g_round'] > ROUNDS:
        you, model = s['g_you'], s['g_model']
        if you > model:
            mood, line = 'wow', 'You beat the model! Saturday has no secrets from you.'
        elif you == model:
            mood, line = 'happy', "A dead heat! You think just like the model."
        else:
            mood, line = 'oops', 'The model wins this time. Grid slot is a sneaky clue!'
        left, right = st.columns([1, 2], gap='large')
        with left:
            st.markdown(f'<div class="polly-card"><div class="bubble">{line}</div>'
                        f'{chibi_svg(170, mood=mood, uid="gend")}</div>', unsafe_allow_html=True)
        with right:
            st.markdown(f'<div class="stat-grid" style="margin:12px 0 22px">'
                        f'<div class="stat glow"><div class="stat-label">You</div><div class="stat-value accent">'
                        f'{you}/{ROUNDS}</div></div>'
                        f'<div class="stat"><div class="stat-label">The model</div><div class="stat-value">'
                        f'{model}/{ROUNDS}</div></div></div>', unsafe_allow_html=True)
            st.dataframe(pd.DataFrame(s['g_log']), hide_index=True)
            st.button('Play again', on_click=_reset, type='primary')
        return

    row = df.loc[s['g_pick']]
    chance = _model_chance(bundle, row)
    model_says = chance >= 0.5

    # score the round before drawing the scoreboard, and only once per round
    actual = bool(row['podium'])
    if s['g_guess'] is not None:
        you_right = s['g_guess'] == actual
        model_right = model_says == actual
        if len(s['g_log']) < s['g_round']:
            s['g_you'] += int(you_right)
            s['g_model'] += int(model_right)
            s['g_log'].append({'Round': s['g_round'], 'Start': f'{row["driver"]}, P{int(row["grid_clean"])}',
                               'Result': f'P{int(row["positionOrder"])}' if row['finished'] else row['status'],
                               'You': '✓' if you_right else '✗', 'Model': '✓' if model_right else '✗'})
    chance_text = '<1%' if chance < 0.005 else f'{chance:.0%}'

    dots = ''.join(f'<span class="dot{" done" if i < s["g_round"] else ""}"></span>' for i in range(1, ROUNDS + 1))
    st.markdown(f'<div class="game-meta"><div class="dots">{dots}</div><div>Round <b>{s["g_round"]}</b> of {ROUNDS}'
                f' · You <b>{s["g_you"]}</b> · Model <b>{s["g_model"]}</b></div></div>', unsafe_allow_html=True)

    left, right = st.columns([1.7, 1], gap='large')
    with left:
        st.markdown(f'<div class="race-card"><div class="race-eyebrow">{int(row["year"])} · {row["race_name"]}</div>'
                    f'<div class="race-driver">{row["driver"]}</div><div class="race-team">{row["team"]}</div>'
                    f'<div class="race-grid"><span>Starts</span>P{int(row["grid_clean"])}</div></div>',
                    unsafe_allow_html=True)

        if s['g_guess'] is None:
            c1, c2 = st.columns(2)
            c1.button('🏆  Podium', on_click=_guess, args=(True,), type='primary', width='stretch')
            c2.button('No podium', on_click=_guess, args=(False,), width='stretch')
            mood, line = 'happy', 'What do you think? Look at the grid slot and the team!'
        else:
            result = (f'Finished <b>P{int(row["positionOrder"])}</b>' if row['finished']
                      else f'Did not finish · <b>{row["status"]}</b>')
            st.markdown(f'<div class="reveal {"good" if you_right else "bad"}">{result}<br>'
                        f'You said <b>{"podium" if s["g_guess"] else "no podium"}</b> {"✓" if you_right else "✗"} · '
                        f'Model gave it <b>{chance_text}</b> {"✓" if model_right else "✗"}</div>',
                        unsafe_allow_html=True)
            st.button('See final score' if s['g_round'] == ROUNDS else 'Next start →', on_click=_next,
                      type='primary')
            if you_right and not model_right:
                mood, line = 'wow', 'Wow, you beat the model on that one!'
            elif you_right:
                mood, line = 'happy', 'Correct! Nice read.'
            else:
                mood, line = 'oops', 'Oh no! Racing is full of surprises.'
    with right:
        st.markdown(f'<div class="polly-card"><div class="bubble">{line}</div>'
                    f'{chibi_svg(150, mood=mood, uid="game")}</div>', unsafe_allow_html=True)

    st.markdown('<div class="note" style="margin-top:18px">The model was trained on these same seasons, so it is a '
                'tough opponent. It only knows the grid slot, the team and the year.</div>', unsafe_allow_html=True)


GAME_CSS = """
.game-meta { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap;
  color: #A1A1A6; font-size: 14px; margin: 4px 0 18px; }
.game-meta b { color: #F5F5F7; }
.dots { display: flex; gap: 6px; }
.dot { width: 10px; height: 10px; border-radius: 50%; background: #2A2A31; }
.dot.done { background: #FF2B17; box-shadow: 0 0 10px rgba(255,43,23,0.6); }
.race-card { background: linear-gradient(160deg, #1B1B21, #121216); border: 1px solid rgba(255,255,255,0.08);
  border-radius: 24px; padding: 26px 28px; margin-bottom: 16px; }
.race-eyebrow { color: #FF2B17; font-size: 13px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; }
.race-driver { color: #F5F5F7; font-size: clamp(30px, 4vw, 44px); font-weight: 700; letter-spacing: -0.03em; margin-top: 8px; }
.race-team { color: #A1A1A6; font-size: 18px; margin-top: 2px; }
.race-grid { color: #F5F5F7; font-size: 64px; font-weight: 700; letter-spacing: -0.04em; line-height: 1; margin-top: 18px; }
.race-grid span { display: block; color: #6E6E73; font-size: 13px; font-weight: 500; letter-spacing: 0.06em;
  text-transform: uppercase; margin-bottom: 6px; }
.reveal { border-radius: 16px; padding: 14px 18px; margin: 4px 0 14px; font-size: 16px; line-height: 1.6; color: #F5F5F7; }
.reveal.good { background: rgba(48,209,88,0.12); border: 1px solid rgba(48,209,88,0.35); }
.reveal.bad { background: rgba(255,43,23,0.10); border: 1px solid rgba(255,43,23,0.35); }
"""
