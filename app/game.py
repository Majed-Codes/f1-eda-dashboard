"""Lights Out Arcade: three F1 mini-games that use the real data.

The games themselves run in the browser (app/arcade/index.html, a small two-way component) so they are smooth.
This file picks real races from clean_data.csv for them, turns the results back into F1 numbers, and runs the
online championship rooms that friends join from their phones.
"""
import os
import random
import socket
import threading
import time
import uuid

import numpy as np
import streamlit as st
import streamlit.components.v1 as components

from polly import chibi_svg

try:
    import segno   # QR codes for the online rooms; without it the room shows the code and link only
except ImportError:
    segno = None

_arcade = components.declare_component('lights_out_arcade',
                                       path=os.path.join(os.path.dirname(__file__), 'arcade'))

PLAYER_COLORS = ['#FF2B17', '#3DD6F5', '#FFD60A', '#30D158', '#BF5AF2', '#FF9F0A', '#FF6BB5', '#F5F5F7']
POINTS = [10, 8, 6, 5, 4, 3, 2, 1]
ROUND_SECONDS = {'lights': 45, 'pit': 60, 'dash': 80}   # online rounds end after this, finished or not
GAMES = {
    'lights': ('🚦', 'Lights Out', 'Five red lights, then go! React faster than an F1 driver. Your launch decides '
                                  'how many places you gain from a real grid slot.'),
    'pit': ('🔧', 'Pit Stop', 'Change the tyre that lights up, in order, then release the car. Wrong wheel costs '
                             'time. Can you get under 1.8 seconds?'),
    'dash': ('🏎️', 'Grid Dash', "Take a real driver's seat on a real grid. Overtake, grab DRS and dodge rivals in "
                               'their team colours. Then see what really happened.'),
}
TEAM_COLORS = {
    'Ferrari': '#E8002D', 'Mercedes': '#27F4D2', 'Red Bull': '#3671C6', 'McLaren': '#FF8000', 'Williams': '#64C4FF',
    'Alpine F1 Team': '#0093CC', 'Aston Martin': '#229971', 'Haas F1 Team': '#B6BABD', 'Sauber': '#52E252',
    'Alfa Romeo': '#C92D4B', 'AlphaTauri': '#5E8FAA', 'RB F1 Team': '#6692FF', 'Racing Point': '#F596C8',
    'Force India': '#F596C8', 'Renault': '#FFF500', 'Toro Rosso': '#469BFF', 'Lotus F1': '#B8A057',
    'Manor Marussia': '#E5413B', 'Marussia': '#E5413B', 'Caterham': '#2E8B57', 'HRT': '#B39058', 'Virgin': '#C1002B',
    'Team Lotus': '#FFDD00', 'Brawn': '#B8FD6E', 'Toyota': '#E7E7E7', 'BMW Sauber': '#6CD3FF', 'Honda': '#E5E5E5',
    'Jordan': '#FFD300', 'Benetton': '#00A651', 'Tyrrell': '#4A6FD1', 'Brabham': '#2D7D46', 'Ligier': '#3A6FD8',
    'Jaguar': '#2A8C3E', 'Arrows': '#FF8C00', 'Prost': '#2E5DA8', 'Stewart': '#FFFFFF', 'BAR': '#C8C8C8',
    'Super Aguri': '#E10600', 'Spyker': '#FF6A00', 'Lotus-Climax': '#2E6B30', 'Maserati': '#C8102E',
    'Minardi': '#A0A0A6', 'Sauber-BMW': '#6CD3FF', 'MF1': '#FF6A00', 'Spyker MF1': '#FF6A00', 'Lotus': '#FFDD00',
}


# ================================================================ real data for the games
def pick_race(df, rng):
    """A random 2000-2024 race with a full grid, and the grid slot the player takes over."""
    d = df[(df['year'] >= 2000) & df['starter'] & df['grid_clean'].between(1, 26)]
    sizes = d.groupby('raceId').size()
    race_id = int(rng.choice(sizes[sizes >= 16].index))
    race = d[d['raceId'] == race_id].sort_values('grid_clean')
    slot = int(rng.integers(6, min(17, len(race)) + 1))
    me = race[race['grid_clean'] == slot].iloc[0]
    field = [{'start': int(r['grid_clean']), 'short': r['driver'].split()[-1][:3].upper(),
              'color': TEAM_COLORS.get(r['team'], '#8E8E93')} for _, r in race.iterrows()]
    return {'title': f'{int(me["year"])} {me["race_name"]}', 'start': slot, 'driver': me['driver'],
            'team': me['team'], 'real': (f'P{int(me["positionOrder"])}' if me['finished'] else f'DNF ({me["status"]})'),
            'field': field}


def podium_rate(df, slot):
    m = df[(df['year'] >= 2010) & df['starter'] & (df['grid_clean'] == slot)]
    return m['podium'].mean() if len(m) else 0.0


def launch_places(best_ms):
    """Turns a reaction time into places won or lost at the start."""
    if best_ms is None:
        return -5            # every start was a jump start: drive-through penalty
    for limit, places in [(180, 3), (220, 2), (260, 1), (320, 0), (450, -1)]:
        if best_ms < limit:
            return places
    return -2


def story(df, game, race, r):
    """One or two sentences that connect a result back to the real data."""
    if game == 'lights':
        places = launch_places(r.get('best_ms'))
        new = int(np.clip(race['start'] - places, 1, 20))
        verb = (f'gains you {places} place{"s" if places != 1 else ""}' if places > 0 else
                'keeps your place' if places == 0 else f'drops you {-places} place{"s" if places != -1 else ""}')
        best = f'Best reaction <b>{r["best_ms"] / 1000:.3f}s</b>' if r.get('best_ms') else 'Every start was a jump start'
        return (f'{best}. Starting <b>P{race["start"]}</b> in the {race["title"]}, that launch {verb}: '
                f'you are <b>P{new}</b> into turn one. Since 2010, <b>{podium_rate(df, new):.0%}</b> of starts from P{new} '
                f'ended on the podium.')
    if game == 'pit':
        best = r['best_ms'] / 1000
        level = 'world-class' if best < 1.8 else ('a solid stop' if best < 2.5 else 'a slow one, the crew needs practice')
        return (f'Best stop <b>{best:.3f}s</b>, {level}. Background, not from our data: top F1 crews change all four '
                f'tyres in about 2 seconds.')
    gained = race['start'] - r['finish_pos']
    return (f'You took <b>{race["driver"]}</b>\'s {race["team"]} from <b>P{race["start"]}</b> to <b>P{r["finish_pos"]}</b> '
            f'({"+" if gained >= 0 else ""}{gained} places, {r["crashes"]} crash{"es" if r["crashes"] != 1 else ""}). '
            f'In the real {race["title"]}, {race["driver"]} finished <b>{race["real"]}</b>.')


def mood_for(game, r):
    if game == 'lights':
        return ('wow', 'Lightning launch! ⚡') if (r.get('best_ms') or 999) < 220 else \
               (('happy', 'Nice start!') if r.get('best_ms') else ('oops', 'Jump start! Drive-through penalty!'))
    if game == 'pit':
        return ('wow', 'Box box, perfect stop!') if r['best_ms'] < 1800 else ('happy', 'Good work, crew!')
    return ('wow', 'What a drive! 🏆') if r['finish_pos'] <= 3 else \
           (('happy', 'Points finish!') if r['finish_pos'] <= 10 else ('oops', 'Tough race. Rematch?'))


def rank_key(game, r):
    if game == 'dash':
        return (r.get('finish_pos', 99), r.get('time_ms', 10 ** 9))
    return (r.get('best_ms') or 10 ** 9,)


# ================================================================ shared bits
def _s():
    return st.session_state.setdefault('arc', {'screen': 'home'})


def _to(screen, **kw):
    st.session_state['arc'] = dict({'screen': screen}, **kw)


def _new_run(game, mode, names, df):
    seed = random.randrange(10 ** 9)
    st.session_state['arc'] = {'screen': 'run', 'game': game, 'mode': mode, 'names': names, 'seed': seed,
                               'nonce': uuid.uuid4().hex[:10],
                               'race': pick_race(df, np.random.default_rng(seed)), 'result': None}


def _save_best(game, r):
    best = st.session_state.setdefault('arc_best', {})
    if game == 'dash':
        best['Grid Dash'] = min(best.get('Grid Dash', 99), r['finish_pos'])
    elif r.get('best_ms'):
        name = GAMES[game][1]
        best[name] = min(best.get(name, 10 ** 9), r['best_ms'])


def _polly(line, mood, size=140):
    st.markdown(f'<div class="polly-card"><div class="bubble">{line}</div>{chibi_svg(size, mood=mood, uid="arc" + mood)}'
                '</div>', unsafe_allow_html=True)


def play_component(args, key):
    return _arcade(**args, key=key, default=None)


# ================================================================ home
def home(df):
    st.markdown('<div class="eyebrow">Mini games</div><div class="section-title">Lights Out Arcade</div>'
                '<div class="lede">Three quick F1 games built on the real grids and results. Play alone, with a '
                'friend on this laptop, or start an online championship that everyone joins from their phone.</div>',
                unsafe_allow_html=True)
    cols = st.columns(3)
    for col, (game, (icon, title, text)) in zip(cols, GAMES.items()):
        with col:
            st.markdown(f'<div class="gp-mode"><div class="gp-mode-icon">{icon}</div><div class="gp-mode-title">{title}'
                        f'</div><div class="gp-mode-text">{text}</div></div>', unsafe_allow_html=True)
            a, b = st.columns(2)
            a.button('Solo', key=f'arc_solo_{game}', type='primary', width='stretch', on_click=_new_run,
                     args=(game, 'solo', ['You'], df))
            b.button('2 players', key=f'arc_two_{game}', width='stretch', on_click=_to, args=('names',),
                     kwargs={'game': game})
    st.markdown('<div class="gp-online"><div><div class="gp-mode-title">📱 Online championship</div>'
                '<div class="gp-mode-text">Everyone joins from their phone with a code. Each round is one of the games, '
                'played at the same moment, and F1 points decide the champion.</div></div></div>',
                unsafe_allow_html=True)
    st.button('Open online rooms', key='arc_online', on_click=_to, args=('online',), type='primary')
    best = st.session_state.get('arc_best', {})
    if best:
        shown = [f'{k}: <b>{"P" + str(v) if k == "Grid Dash" else f"{v / 1000:.3f}s"}</b>' for k, v in best.items()]
        st.markdown('<div class="note" style="margin-top:12px">Your bests · ' + ' · '.join(shown) + '</div>',
                    unsafe_allow_html=True)


def names_screen(df):
    s = _s()
    game = s['game']
    icon, title, _ = GAMES[game]
    keys = {'lights': 'Player 1 presses A, player 2 presses L.',
            'pit': 'Players take turns, three stops each.',
            'dash': 'Split screen: player 1 steers with A and D, player 2 with the arrow keys.'}[game]
    st.markdown(f'<div class="gp-head"><div><div class="eyebrow">2 players · same device</div><div class="gp-title">'
                f'{icon} {title}</div></div></div><div class="lede">{keys}</div>', unsafe_allow_html=True)
    c1, c2, _ = st.columns([1, 1, 2])
    n1 = c1.text_input('Player 1', value='Player 1', max_chars=12, key='arc_n1').strip() or 'Player 1'
    n2 = c2.text_input('Player 2', value='Player 2', max_chars=12, key='arc_n2').strip() or 'Player 2'
    b1, b2, _ = st.columns([1, 1, 2])
    b1.button('Start', type='primary', width='stretch', on_click=_new_run, args=(game, 'local', [n1, n2], df))
    b2.button('Back', width='stretch', on_click=_to, args=('home',))


def run_screen(df):
    s = _s()
    game, race = s['game'], s['race']
    icon, title, _ = GAMES[game]
    sub = '2 players' if s['mode'] == 'local' else 'Solo'
    st.markdown(f'<div class="gp-head"><div><div class="eyebrow">{sub}</div><div class="gp-title">{icon} {title}</div>'
                f'</div><div class="gp-meta">{race["title"]}</div></div>', unsafe_allow_html=True)
    players = [{'name': n, 'color': PLAYER_COLORS[i]} for i, n in enumerate(s['names'])]
    value = play_component({'game': game, 'players': players, 'seed': s['seed'], 'nonce': s['nonce'], 'race': race,
                            'start_at': None, 'server_now': None}, key=f'arc_{s["nonce"]}')
    if value and value.get('nonce') == s['nonce'] and s['result'] is None:
        s['result'] = value['results']
        if s['mode'] == 'solo':
            _save_best(game, value['results'][0])
    if s['result']:
        left, right = st.columns([2.2, 1], gap='large')
        with left:
            for r in s['result']:
                who = f'<b>{r["name"]}</b> · ' if s['mode'] == 'local' else ''
                st.markdown(f'<div class="reveal">{who}{story(df, game, race, r)}</div>', unsafe_allow_html=True)
        with right:
            top = sorted(s['result'], key=lambda r: rank_key(game, r))[0]
            mood, line = mood_for(game, top)
            _polly(line if s['mode'] == 'solo' else f'{top["name"]} wins! 🏆', mood)
    c1, c2, _ = st.columns([1, 1, 2])
    c1.button('Play again', type='primary', width='stretch', on_click=_new_run,
              args=(game, s['mode'], s['names'], df))
    c2.button('Back to arcade', width='stretch', on_click=_to, args=('home',))


# ================================================================ online championship
@st.cache_resource
def _store():
    """Rooms shared by everyone connected to this Streamlit server."""
    return {'rooms': {}, 'lock': threading.Lock()}


def _pid():
    return st.session_state.setdefault('arc_pid', uuid.uuid4().hex)


def _join_url(code):
    host = st.context.headers.get('host') or st.context.headers.get('Host') or 'localhost:8501'
    name, _, port = host.partition(':')
    if name in ('localhost', '127.0.0.1', '::1'):
        try:   # use the laptop's address on the Wi-Fi so phones can reach it
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect(('10.255.255.255', 1))
            name = sock.getsockname()[0]
            sock.close()
        except OSError:
            pass
    scheme = 'https' if st.context.headers.get('x-forwarded-proto') == 'https' else 'http'
    return f'{scheme}://{name}{":" + port if port else ""}/?room={code}'


def _player(name, i):
    return {'name': name, 'color': PLAYER_COLORS[i % len(PLAYER_COLORS)], 'points': 0, 'seen': time.time()}


def create_room(name):
    store = _store()
    with store['lock']:
        rooms = store['rooms']
        for code in [c for c, r in rooms.items() if time.time() - r['created'] > 3 * 3600]:
            del rooms[code]
        code = ''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ', k=4))
        while code in rooms:
            code = ''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ', k=4))
        rooms[code] = {'code': code, 'host': _pid(), 'created': time.time(), 'phase': 'lobby', 'round': None,
                       'history': [], 'players': {_pid(): _player(name, 0)}}
    st.session_state['arc_room'] = code


def join_room(code, name):
    store = _store()
    with store['lock']:
        room = store['rooms'].get(code)
        if room is None:
            st.session_state['arc_join_error'] = 'No room with that code.'
            return
        if _pid() not in room['players']:
            if len(room['players']) >= len(PLAYER_COLORS):
                st.session_state['arc_join_error'] = 'That room is full.'
                return
            room['players'][_pid()] = _player(name, len(room['players']))
    st.session_state['arc_room'] = code


def leave_room():
    code = st.session_state.pop('arc_room', None)
    store = _store()
    with store['lock']:
        room = store['rooms'].get(code)
        if room:
            room['players'].pop(_pid(), None)
            if not room['players']:
                del store['rooms'][code]
            elif room['host'] == _pid():
                room['host'] = next(iter(room['players']))
    _to('home')


def start_round(code, game, df):
    room = _store()['rooms'].get(code)
    if not room:
        return
    seed = random.randrange(10 ** 9)
    with _store()['lock']:
        room['round'] = {'id': uuid.uuid4().hex[:10], 'game': game, 'seed': seed,
                         'race': pick_race(df, np.random.default_rng(seed)),
                         'start_at': int((time.time() + 5) * 1000), 'results': {}}
        room['phase'] = 'playing'


def end_championship(code):
    room = _store()['rooms'].get(code)
    if room:
        with _store()['lock']:
            room['phase'] = 'final'


def new_championship(code):
    room = _store()['rooms'].get(code)
    if room:
        with _store()['lock']:
            room.update({'phase': 'lobby', 'round': None, 'history': []})
            for p in room['players'].values():
                p['points'] = 0


def _tick(room):
    """Ends a round when everyone has finished or time runs out. Any player's poll can do it."""
    now = time.time()
    with _store()['lock']:
        rnd = room['round']
        if room['phase'] != 'playing' or rnd is None:
            return
        active = [pid for pid, p in room['players'].items() if now - p['seen'] < 12]
        all_in = active and all(pid in rnd['results'] for pid in active)
        if all_in or now > rnd['start_at'] / 1000 + ROUND_SECONDS[rnd['game']]:
            ranked = sorted(rnd['results'].items(), key=lambda kv: rank_key(rnd['game'], kv[1]))
            table = []
            for place, (pid, r) in enumerate(ranked):
                pts = POINTS[place] if place < len(POINTS) else 0
                if pid in room['players']:
                    room['players'][pid]['points'] += pts
                table.append({'pid': pid, 'name': r['name'], 'pts': pts, 'r': r})
            room['history'].append({'game': rnd['game'], 'race': rnd['race'], 'table': table})
            room['phase'] = 'results'


def online_entry():
    st.markdown('<div class="gp-head"><div><div class="eyebrow">Lights Out Arcade</div><div class="gp-title">'
                'Online championship</div></div></div>', unsafe_allow_html=True)
    preset = st.query_params.get('room', '')
    left, right = st.columns(2, gap='large')
    with left:
        st.markdown('<div class="gp-panel-title">Join a room</div>', unsafe_allow_html=True)
        code = st.text_input('Room code', value=preset.upper(), max_chars=4, key='arc_join_code').strip().upper()
        name = st.text_input('Your name', max_chars=12, key='arc_join_name').strip()
        st.button('Join', type='primary', disabled=not (code and name), on_click=join_room, args=(code, name))
        if st.session_state.get('arc_join_error'):
            st.error(st.session_state.pop('arc_join_error'))
    with right:
        st.markdown('<div class="gp-panel-title">Host a room</div>', unsafe_allow_html=True)
        host_name = st.text_input('Your name', max_chars=12, key='arc_host_name').strip()
        st.button('Create room', type='primary', disabled=not host_name, on_click=create_room, args=(host_name,))
        st.markdown('<div class="note">Friends on the same Wi-Fi scan the QR code or type the code. Rounds are played '
                    'at the same moment on every phone.</div>', unsafe_allow_html=True)
    st.button('Back to arcade', key='arc_online_back', on_click=_to, args=('home',))


def _standings(room):
    order = sorted(room['players'].items(), key=lambda kv: -kv[1]['points'])
    rows = ''.join(f'<div class="gp-lobby-player"><b style="width:28px">P{i + 1}</b><i class="dot" style="background:'
                   f'{p["color"]}"></i>{p["name"]}{" (you)" if pid == _pid() else ""}<span style="margin-left:auto">'
                   f'<b>{p["points"]}</b> pts</span></div>' for i, (pid, p) in enumerate(order))
    return '<div class="gp-panel-title">Championship</div>' + rows


def _game_picker(code, df, label):
    st.markdown(f'<div class="gp-panel-title">{label}</div>', unsafe_allow_html=True)
    cols = st.columns(3)
    for col, (game, (icon, title, _)) in zip(cols, GAMES.items()):
        col.button(f'{icon} {title}', key=f'arc_pick_{game}', width='stretch', type='primary',
                   on_click=start_round, args=(code, game, df))


@st.fragment(run_every=1)
def online_live(df):
    code = st.session_state.get('arc_room')
    if not code:
        st.rerun()   # left the room: redraw the whole arcade
    room = _store()['rooms'].get(code)
    if room is None or _pid() not in room['players']:
        st.session_state.pop('arc_room', None)
        st.warning('This room has closed.')
        st.button('Back to arcade', on_click=_to, args=('home',))
        return
    me = room['players'][_pid()]
    me['seen'] = time.time()
    _tick(room)
    is_host = room['host'] == _pid()
    phase = room['phase']
    rounds = len(room['history'])
    st.markdown(f'<div class="gp-head"><div><div class="eyebrow">Online championship</div><div class="gp-title">Room '
                f'<span class="gp-code">{code}</span></div></div><div class="gp-meta">{len(room["players"])} drivers · '
                f'{rounds} round{"s" if rounds != 1 else ""} played</div></div>', unsafe_allow_html=True)

    if phase == 'lobby':
        left, right = st.columns([1.3, 1], gap='large')
        with left:
            st.markdown('<div class="gp-panel-title">On the grid</div>' + ''.join(
                f'<div class="gp-lobby-player"><i class="dot" style="background:{p["color"]}"></i>{p["name"]}'
                f'{" · host" if pid == room["host"] else ""}{" (you)" if pid == _pid() else ""}</div>'
                for pid, p in room['players'].items()), unsafe_allow_html=True)
            if is_host:
                _game_picker(code, df, 'Pick the first round')
            else:
                st.markdown('<div class="note">Waiting for the host to pick the first game…</div>',
                            unsafe_allow_html=True)
        with right:
            url = _join_url(code)
            qr = segno.make(url, error='m').svg_inline(scale=5, dark='#111114', light='#FFFFFF', border=2) if segno else ''
            st.markdown(f'<div class="gp-qr">{qr}<div class="gp-qr-code">{code}</div><div class="gp-qr-url">{url}</div>'
                        '</div>', unsafe_allow_html=True)
        st.button('Leave room', on_click=leave_room)
        return

    if phase == 'playing':
        rnd = room['round']
        icon, title, _ = GAMES[rnd['game']]
        done = sum(pid in rnd['results'] for pid in room['players'])
        st.markdown(f'<div class="lede">Round {rounds + 1}: <b>{icon} {title}</b> · {rnd["race"]["title"]} · '
                    f'{done} of {len(room["players"])} finished</div>', unsafe_allow_html=True)
        value = play_component({'game': rnd['game'], 'players': [{'name': me['name'], 'color': me['color']}],
                                'seed': rnd['seed'], 'nonce': rnd['id'], 'race': rnd['race'],
                                'start_at': rnd['start_at'], 'server_now': int(time.time() * 1000)},
                               key=f'arc_online_{rnd["id"]}')
        if value and value.get('nonce') == rnd['id'] and _pid() not in rnd['results']:
            with _store()['lock']:
                rnd['results'][_pid()] = dict(value['results'][0], name=me['name'])
        if _pid() in rnd['results']:
            st.markdown('<div class="note">Result locked in. Waiting for the others…</div>', unsafe_allow_html=True)
        st.button('Leave room', key='arc_leave_play', on_click=leave_room)
        return

    if phase == 'results':
        last = room['history'][-1]
        icon, title, _ = GAMES[last['game']]
        left, right = st.columns([1.4, 1], gap='large')
        with left:
            st.markdown(f'<div class="gp-panel-title">Round {rounds}: {icon} {title}</div>', unsafe_allow_html=True)
            rows = ''
            for i, row in enumerate(last['table']):
                r = row['r']
                score = (f'P{last["race"]["start"]} → P{r["finish_pos"]}' if last['game'] == 'dash'
                         else (f'{r["best_ms"] / 1000:.3f}s' if r.get('best_ms') else 'jump starts'))
                rows += (f'<div class="gp-lobby-player"><b style="width:28px">P{i + 1}</b>{row["name"]}'
                         f'<span style="margin-left:auto;color:#A1A1A6">{score}</span><b style="width:54px;'
                         f'text-align:right">+{row["pts"]}</b></div>')
            st.markdown(rows or '<div class="note">Nobody finished this round.</div>', unsafe_allow_html=True)
            mine = next((row['r'] for row in last['table'] if row['pid'] == _pid()), None)
            if mine:
                st.markdown(f'<div class="reveal">{story(df, last["game"], last["race"], mine)}</div>',
                            unsafe_allow_html=True)
        with right:
            st.markdown(_standings(room), unsafe_allow_html=True)
        if is_host:
            _game_picker(code, df, 'Next round')
            st.button('🏁 Finish the championship', on_click=end_championship, args=(code,))
        else:
            st.markdown('<div class="note">Waiting for the host to pick the next round…</div>', unsafe_allow_html=True)
        st.button('Leave room', key='arc_leave_res', on_click=leave_room)
        return

    # final
    order = sorted(room['players'].values(), key=lambda p: -p['points'])
    steps = ''
    for idx, cls, h in [(1, 'second', 92), (0, 'first', 128), (2, 'third', 70)]:
        if idx < len(order):
            p = order[idx]
            steps += (f'<div class="gp-step {cls}"><div class="gp-step-name">{p["name"]}</div>'
                      f'<div class="gp-step-pts">{p["points"]} pts</div>'
                      f'<div class="gp-step-block" style="height:{h}px">P{idx + 1}</div></div>')
    left, right = st.columns([2, 1], gap='large')
    left.markdown(f'<div class="gp-podium">{steps}</div>', unsafe_allow_html=True)
    with right:
        _polly(f'{order[0]["name"]} is the champion! 🏆', 'wow', 150)
    if is_host:
        st.button('New championship', type='primary', on_click=new_championship, args=(code,))
    st.button('Leave room', key='arc_leave_final', on_click=leave_room)


# ================================================================ entry point
def play(df, bundle=None):
    if st.session_state.get('arc_room'):
        online_live(df)
        return
    s = _s()
    if s['screen'] == 'home' and st.query_params.get('room'):
        s['screen'] = 'online'
    {'home': home, 'names': names_screen, 'run': run_screen,
     'online': lambda _df: online_entry()}[s['screen']](df)


GAME_CSS = """
.gp-head { display: flex; justify-content: space-between; align-items: flex-end; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }
.gp-title { color: #F5F5F7; font-size: clamp(26px, 3vw, 36px); font-weight: 700; letter-spacing: -0.025em; }
.gp-meta { color: #A1A1A6; font-size: 14px; }
.gp-code { color: #FF2B17; letter-spacing: 0.12em; }
.gp-mode { background: linear-gradient(160deg, #1B1B21, #121216); border: 1px solid rgba(255,255,255,0.08); border-radius: 22px;
  padding: 22px 20px; min-height: 196px; margin-bottom: 10px; transition: transform .2s ease, border-color .2s ease; }
.gp-mode:hover { transform: translateY(-3px); border-color: rgba(255,43,23,0.45); }
.gp-mode-icon { font-size: 34px; }
.gp-mode-title { color: #F5F5F7; font-size: 20px; font-weight: 700; margin-top: 10px; letter-spacing: -0.01em; }
.gp-mode-text { color: #A1A1A6; font-size: 14px; line-height: 1.45; margin-top: 6px; }
.gp-online { margin: 22px 0 10px; padding: 20px 22px; border-radius: 22px; border: 1px solid rgba(255,43,23,0.35);
  background: radial-gradient(circle at 0% 0%, rgba(255,43,23,0.18), transparent 60%), #121216; }
.gp-online .gp-mode-title { margin-top: 0; }
.gp-panel-title { color: #F5F5F7; font-size: 18px; font-weight: 600; margin: 4px 0 10px; }
.reveal { border-radius: 16px; padding: 14px 18px; margin: 10px 0; font-size: 16px; line-height: 1.55; color: #D1D1D6;
  background: #141418; border: 1px solid rgba(255,255,255,0.08); }
.reveal b { color: #F5F5F7; }
.gp-lobby-player { display: flex; align-items: center; gap: 12px; color: #F5F5F7; font-size: 16px; padding: 10px 14px;
  border-radius: 14px; background: #141418; border: 1px solid rgba(255,255,255,0.06); margin-bottom: 8px;
  animation: gp-rise .4s ease-out both; }
.gp-lobby-player .dot { width: 12px; height: 12px; border-radius: 50%; flex: none; }
.gp-qr { background: #FFFFFF; border-radius: 22px; padding: 16px; text-align: center; max-width: 280px; margin-left: auto; }
.gp-qr svg { width: 100%; height: auto; }
.gp-qr-code { color: #111114; font-size: 34px; font-weight: 800; letter-spacing: 0.18em; margin-top: 4px; }
.gp-qr-url { color: #6E6E73; font-size: 11px; word-break: break-all; }
.gp-podium { display: flex; justify-content: center; align-items: flex-end; gap: 14px; margin: 10px 0 18px; }
.gp-step { width: 150px; text-align: center; animation: gp-rise .7s cubic-bezier(.3, 1.5, .5, 1) both; }
.gp-step.first { animation-delay: .5s; } .gp-step.second { animation-delay: .2s; }
@keyframes gp-rise { from { opacity: 0; transform: translateY(30px); } }
.gp-step-name { color: #F5F5F7; font-weight: 700; font-size: 17px; margin-top: 6px; }
.gp-step-pts { color: #A1A1A6; font-size: 13px; margin-bottom: 8px; }
.gp-step-block { border-radius: 14px 14px 0 0; display: grid; place-items: center; color: #F5F5F7; font-size: 28px; font-weight: 800;
  background: linear-gradient(180deg, #2A2A31, #1A1A20); border: 1px solid rgba(255,255,255,0.08); border-bottom: 0; }
.gp-step.first .gp-step-block { background: linear-gradient(180deg, #FF2B17, #A3170B); box-shadow: 0 0 40px rgba(255,43,23,.35); }
@media (max-width: 640px) { .gp-step { width: 100px; } .gp-qr { margin: 0 auto; } }
"""
