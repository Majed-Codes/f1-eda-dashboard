"""Animated charts for the dashboard, drawn with ECharts.

Every chart animates in when it first appears and again whenever the filters change. Hover any bar, line or
cell for the exact numbers. ECharts is loaded from the jsDelivr CDN, pinned to one version.
"""
import json
import math

import streamlit.components.v1 as components

ECHARTS = 'https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js'
RED = '#FF2B17'
INK = '#F5F5F7'
MUTED = '#A1A1A6'
FAINT = '#6E6E73'
FONT = "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Helvetica Neue', Arial, sans-serif"

GREY_BAR = {'type': 'linear', 'x': 0, 'y': 0, 'x2': 0, 'y2': 1,
            'colorStops': [{'offset': 0, 'color': '#55555E'}, {'offset': 1, 'color': '#2B2B31'}]}
RED_BAR = {'type': 'linear', 'x': 0, 'y': 0, 'x2': 0, 'y2': 1,
           'colorStops': [{'offset': 0, 'color': '#FF5A45'}, {'offset': 1, 'color': '#C41C0E'}]}

BASE = {
    'backgroundColor': 'transparent',
    'textStyle': {'fontFamily': FONT, 'color': MUTED},
    'animationDuration': 1200,
    'animationEasing': 'cubicOut',
    'animationDurationUpdate': 700,
    'tooltip': {'backgroundColor': 'rgba(28,28,34,0.96)', 'borderColor': '#2C2C33', 'padding': [8, 12],
                'textStyle': {'color': INK, 'fontFamily': FONT, 'fontSize': 13},
                'extraCssText': 'border-radius:12px;box-shadow:0 12px 32px rgba(0,0,0,.45);'},
    'grid': {'left': 6, 'right': 18, 'top': 58, 'bottom': 6, 'containLabel': True},
}

# small JS helpers: "__fn__" strings become functions, so options can stay plain JSON
PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>
html, body { margin: 0; background: transparent; overflow: hidden; font-family: __FONT__; }
#c { width: 100%; height: __H__px; }
#replay { position: absolute; top: 6px; right: 8px; background: #1C1C22; color: #F5F5F7; border: 1px solid #2C2C33;
  border-radius: 10px; padding: 6px 12px; font: 600 12px __FONT__; cursor: pointer; display: none; }
#replay:hover { background: #26262C; }
.offline { color: #6E6E73; font: 14px __FONT__; padding: 40px 10px; text-align: center; }
</style></head><body><div id="c"></div><button id="replay">↻ Replay</button>
<script src="__ECHARTS__"></script>
<script>
function revive(o) {
  for (const k in o) {
    const v = o[k];
    if (typeof v === 'string' && v.startsWith('__fn__')) o[k] = eval('(' + v.slice(6) + ')');
    else if (v && typeof v === 'object') revive(v);
  }
  return o;
}
if (typeof echarts === 'undefined') {
  document.getElementById('c').innerHTML = '<div class="offline">The animated charts need an internet connection.</div>';
} else {
  // Streamlit builds hidden tabs too, so a chart only animates once it is really on screen,
  // and again each time its tab is opened (not when you just scroll past it).
  const box = document.getElementById('c');
  const chart = echarts.init(box, null, { renderer: 'canvas' });
  const OPTION = __OPTION_JSON__;
  // charts that must fit their width (rings, radar) set window.fit(option, w, h) to size themselves to the real frame
  const H = __H__;
  const build = () => { const o = revive(JSON.parse(OPTION)); return window.fit ? window.fit(o, box.clientWidth, H) : o; };
  window.addEventListener('resize', () => { chart.resize(); if (shown && window.fit) chart.setOption(build()); });
  __SCRIPT__
  let shown = false;
  function animateIn() {
    chart.resize(); chart.clear(); chart.setOption(build());
    if (window.afterShow) window.afterShow();
  }
  new IntersectionObserver(entries => {
    const e = entries[entries.length - 1];
    if (e.isIntersecting && !shown) { shown = true; animateIn(); }
    else if (!e.isIntersecting && e.boundingClientRect.width === 0) { shown = false; if (window.afterHide) window.afterHide(); }
  }, { threshold: 0.01 }).observe(box);
}
</script></body></html>"""


def _merge(base, extra):
    out = dict(base)
    for k, v in extra.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def render(option, height=380, script=''):
    """Draws one chart. `script` is extra JS that runs once the chart exists (the bar chart race uses it)."""
    html = (PAGE.replace('__FONT__', FONT).replace('__H__', str(height)).replace('__ECHARTS__', ECHARTS)
            .replace('__OPTION_JSON__', json.dumps(json.dumps(_merge(BASE, option)))).replace('__SCRIPT__', script))
    components.html(html, height=height + 4)


def title(text):
    return {'text': text, 'left': 0, 'top': 2,
            'textStyle': {'color': INK, 'fontSize': 16, 'fontWeight': 600, 'fontFamily': FONT}}


def x_axis(data=None, **kw):
    axis = {'type': 'category', 'axisLine': {'lineStyle': {'color': 'rgba(255,255,255,0.12)'}},
            'axisTick': {'show': False}, 'axisLabel': {'color': MUTED}, 'splitLine': {'show': False}}
    if data is not None:
        axis['data'] = data
    return _merge(axis, kw)


def y_axis(**kw):
    axis = {'type': 'value', 'axisLine': {'show': False}, 'axisTick': {'show': False}, 'axisLabel': {'color': MUTED},
            'splitLine': {'lineStyle': {'color': 'rgba(255,255,255,0.06)'}}}
    return _merge(axis, kw)


STAGGER = '__fn__function (i) { return i * 45; }'


# ================================================================ qualifying
def rate_by_slot(rates, counts, outcome, height=340):
    data = []
    for i, (r, n) in enumerate(zip(rates, counts)):
        bar = {'value': None if r is None else round(r, 1), 'starts': n,
               'itemStyle': {'color': RED_BAR if i == 0 else GREY_BAR}}
        if i == 0:
            bar['label'] = {'show': True, 'position': 'top', 'color': INK, 'fontWeight': 700, 'formatter': '{c}%'}
        data.append(bar)
    render({
        'title': title(f'{outcome} rate by grid slot'),
        'tooltip': {'trigger': 'item', 'formatter': '__fn__function (p) { return "From <b>" + p.name + "</b>: " + '
                                                     'p.value + "% ' + outcome.lower() + ' rate<br/>" + p.data.starts '
                                                     '+ " starts"; }'},
        'xAxis': x_axis([f'P{i}' for i in range(1, len(rates) + 1)]),
        'yAxis': y_axis(axisLabel={'formatter': '{value}%'}),
        'series': [{'type': 'bar', 'data': data, 'barCategoryGap': '28%', 'itemStyle': {'borderRadius': [6, 6, 0, 0]},
                    'emphasis': {'itemStyle': {'color': '#FF7A6A'}}, 'animationDelay': STAGGER}],
    }, height)


def grid_to_result(flows, height=430):
    """Sankey diagram: grid slot groups on the left, what happened on Sunday on the right."""
    left = ['P1', 'P2–3', 'P4–6', 'P7–10', 'P11+']
    right = ['Win', 'Podium', 'Points', 'No points', 'DNF']
    colors = {'P1': RED, 'P2–3': '#C9372A', 'P4–6': '#7A2E28', 'P7–10': '#4E3532', 'P11+': '#3A3A41',
              'Win': '#FFD60A', 'Podium': '#FF8A7A', 'Points': '#8E8E93', 'No points': '#55555E', 'DNF': '#2C2C33'}
    nodes = [{'name': n, 'itemStyle': {'color': colors[n], 'borderColor': colors[n]}} for n in left + right]
    links = [{'source': s, 'target': t, 'value': int(v)} for (s, t), v in flows.items() if v > 0]
    render({
        'title': title('From the grid to the flag'),
        'tooltip': {'trigger': 'item', 'formatter': '__fn__function (p) { return p.dataType === "edge" ? '
                                                     'p.data.source + " → " + p.data.target + ": <b>" + p.data.value + '
                                                     '"</b> starts" : p.name + ": <b>" + p.value + "</b> starts"; }'},
        'series': [{'type': 'sankey', 'top': 54, 'bottom': 10, 'left': 6, 'right': 80, 'nodeWidth': 14, 'nodeGap': 12,
                    'draggable': False, 'data': nodes, 'links': links, 'layoutIterations': 0,
                    'label': {'color': INK, 'fontSize': 13, 'fontWeight': 600},
                    'lineStyle': {'color': 'gradient', 'opacity': 0.38, 'curveness': 0.55},
                    'emphasis': {'focus': 'adjacency', 'lineStyle': {'opacity': 0.75}}}],
        'animationDuration': 1600,
    }, height)


def heatmap(matrix, x_labels, height=470):
    data = [[x, y, None if v is None else round(v, 1)] for y, row in enumerate(matrix) for x, v in enumerate(row)]
    render({
        'title': title('Where each grid slot finishes'),
        'tooltip': {'formatter': '__fn__function (p) { return "Started <b>P" + (p.value[1] + 1) + "</b>, finished <b>" '
                                 '+ p.name + "</b><br/>" + (p.value[2] === null ? 0 : p.value[2]) + "% of starts"; }'},
        'grid': {'right': 64},
        'xAxis': x_axis(x_labels, name='Result', nameLocation='middle', nameGap=26,
                        nameTextStyle={'color': MUTED}, axisLabel={'fontSize': 10}),
        'yAxis': {'type': 'category', 'data': [f'P{i}' for i in range(1, len(matrix) + 1)], 'inverse': True,
                  'axisLine': {'show': False}, 'axisTick': {'show': False}, 'axisLabel': {'color': MUTED, 'fontSize': 10}},
        'visualMap': {'min': 0, 'max': 50, 'calculable': False, 'orient': 'vertical', 'right': 0, 'top': 'middle',
                      'itemHeight': 160, 'itemWidth': 10, 'text': ['50%', '0%'], 'textStyle': {'color': MUTED},
                      'inRange': {'color': ['#111115', '#4A1510', RED, '#FFD7D0']}},
        'series': [{'type': 'heatmap', 'data': data, 'itemStyle': {'borderColor': '#0A0A0C', 'borderWidth': 1.5,
                                                                    'borderRadius': 3},
                    'emphasis': {'itemStyle': {'borderColor': INK, 'borderWidth': 1.5}},
                    'animationDelay': '__fn__function (i) { return (i % 21) * 18 + Math.floor(i / 21) * 22; }'}],
    }, height)


def places_gained(counts, height=470):
    data = [{'value': int(v), 'itemStyle': {'color': RED_BAR if abs(k) <= 3 else GREY_BAR}} for k, v in counts.items()]
    render({
        'title': title('Places gained on Sunday'),
        'tooltip': {'formatter': '__fn__function (p) { const k = Number(p.name); return (k > 0 ? "+" : "") + k + '
                                 '" places: <b>" + p.value + "</b> finishes"; }'},
        'xAxis': x_axis([str(k) for k in counts.index], name='Places gained (+) or lost (−)', nameLocation='middle',
                        nameGap=26, nameTextStyle={'color': MUTED}, axisLabel={'interval': 4}),
        'yAxis': y_axis(),
        'series': [{'type': 'bar', 'data': data, 'barCategoryGap': '18%', 'itemStyle': {'borderRadius': [4, 4, 0, 0]},
                    'animationDelay': '__fn__function (i) { return Math.abs(i - 15) * 45; }'}],
    }, height)


# ================================================================ dominance
def leader_share(years, teams, wins_n, totals, shares, colors, height=340):
    data = [{'value': round(s, 1), 'team': t, 'w': int(w), 'n': int(n), 'itemStyle': {'color': c}}
            for t, w, n, s, c in zip(teams, wins_n, totals, shares, colors)]
    render({
        'title': title("Leading team's share of wins, season by season"),
        'tooltip': {'formatter': '__fn__function (p) { return "<b>" + p.name + "</b>: " + p.data.team + "<br/>" + '
                                 'p.data.w + " of " + p.data.n + " wins (" + p.value + "%)"; }'},
        'xAxis': x_axis([str(y) for y in years]),
        'yAxis': y_axis(max=100, axisLabel={'formatter': '{value}%'}),
        'series': [{'type': 'bar', 'data': data, 'barCategoryGap': '22%', 'itemStyle': {'borderRadius': [5, 5, 0, 0]},
                    'animationDelay': STAGGER}],
    }, height)


def bar_race(frames, teams, colors, height=460):
    """Bar chart race: total wins per constructor, growing season by season."""
    first = frames[0]
    option = {
        'title': title('Race to the most wins'),
        'grid': {'top': 50, 'right': 60, 'left': 6, 'bottom': 10},
        'xAxis': {'type': 'value', 'max': 'dataMax', 'axisLabel': {'show': False}, 'splitLine': {'show': False},
                  'axisLine': {'show': False}, 'axisTick': {'show': False}},
        'yAxis': {'type': 'category', 'data': teams, 'inverse': True, 'max': min(9, len(teams) - 1),
                  'animationDuration': 300, 'animationDurationUpdate': 300, 'axisLine': {'show': False},
                  'axisTick': {'show': False}, 'axisLabel': {'color': INK, 'fontSize': 13, 'fontWeight': 600}},
        'series': [{'type': 'bar', 'realtimeSort': True, 'barCategoryGap': '30%',
                    'data': [{'value': v, 'itemStyle': {'color': colors[i], 'borderRadius': [0, 6, 6, 0]}}
                             for i, v in enumerate(first['values'])],
                    'label': {'show': True, 'position': 'right', 'valueAnimation': True, 'color': INK,
                              'fontWeight': 700, 'fontSize': 13}}],
        'animationDuration': 0, 'animationDurationUpdate': 900, 'animationEasing': 'linear',
        'animationEasingUpdate': 'linear',
        'graphic': {'elements': [{'type': 'text', 'id': 'year', 'right': 70, 'bottom': 34,
                                  'style': {'text': str(first['year']), 'font': f'800 72px {FONT}',
                                            'fill': 'rgba(245,245,247,0.30)'}}]},
    }
    step = max(300, min(1000, int(18000 / max(1, len(frames)))))
    script = """
const frames = __FRAMES__, colors = __COLORS__, STEP = __STEP__;
let i = 0, timer = null;
function show(k) {
  chart.setOption({
    series: [{ data: frames[k].values.map((v, j) => ({ value: v, itemStyle: { color: colors[j], borderRadius: [0, 6, 6, 0] } })) }],
    graphic: { elements: [{ id: 'year', style: { text: String(frames[k].year) } }] },
    animationDurationUpdate: STEP,
  });
}
function play() {
  clearInterval(timer); i = 0; show(0);
  document.getElementById('replay').style.display = 'none';
  timer = setInterval(() => {
    i++;
    if (i >= frames.length) { clearInterval(timer); document.getElementById('replay').style.display = 'block'; return; }
    show(i);
  }, STEP);
}
document.getElementById('replay').onclick = play;
window.afterShow = () => setTimeout(play, 250);
window.afterHide = () => clearInterval(timer);
""".replace('__FRAMES__', json.dumps(frames)).replace('__COLORS__', json.dumps(colors)).replace('__STEP__', str(step))
    render(option, height, script)


# ================================================================ reliability
def dnf_lines(years, dnf, mech, height=360):
    def series(name, values, color, area):
        return {'name': name, 'type': 'line', 'data': [round(v, 1) for v in values], 'smooth': 0.35,
                'symbol': 'circle', 'symbolSize': 5, 'showSymbol': False, 'lineStyle': {'width': 3 if area else 2.2, 'color': color},
                'itemStyle': {'color': color},
                'areaStyle': {'color': {'type': 'linear', 'x': 0, 'y': 0, 'x2': 0, 'y2': 1, 'colorStops': [
                    {'offset': 0, 'color': color + ('55' if area else '22')}, {'offset': 1, 'color': color + '00'}]}},
                'endLabel': {'show': True, 'color': color, 'fontWeight': 700, 'formatter': '{a}  {c}%'},
                'emphasis': {'focus': 'series'}}
    render({
        'title': title('Share of starters who did not finish'),
        'tooltip': {'trigger': 'axis', 'valueFormatter': '__fn__function (v) { return v + "%"; }'},
        'grid': {'right': 120},
        'xAxis': x_axis([str(y) for y in years], boundaryGap=False),
        'yAxis': y_axis(axisLabel={'formatter': '{value}%'}),
        'series': [series('All DNFs', dnf, RED, True), series('Mechanical', mech, '#F5F5F7', False)],
        'animationDuration': 2200,
        'animationEasing': 'cubicInOut',
    }, height)


def causes_by_decade(decades, causes, height=340):
    palette = {'Mechanical': RED, 'Crash/collision': '#8E8E93', 'Other': '#3A3A41'}
    series = [{'name': name, 'type': 'bar', 'stack': 'all', 'data': [round(v, 1) for v in values],
               'barWidth': '46%' if len(decades) > 3 else '24%', 'itemStyle': {'color': palette[name]},
               'emphasis': {'focus': 'series'}, 'animationDelay': STAGGER}
              for name, values in causes.items()]
    if series:
        series[-1]['itemStyle']['borderRadius'] = [6, 6, 0, 0]
    render({
        'title': title('What ended the race, by decade'),
        'legend': {'top': 4, 'right': 0, 'textStyle': {'color': MUTED}, 'itemWidth': 12, 'itemHeight': 12,
                   'icon': 'roundRect'},
        'tooltip': {'trigger': 'axis', 'axisPointer': {'type': 'shadow'},
                    'valueFormatter': '__fn__function (v) { return v + "%"; }'},
        'xAxis': x_axis(decades),
        'yAxis': y_axis(max=100, axisLabel={'formatter': '{value}%'}),
        'series': series,
    }, height)


# ================================================================ drivers and predict
def podiums_per_season(years, wins_n, other, height=340):
    render({
        'title': title('Podiums per season'),
        'legend': {'top': 4, 'right': 0, 'textStyle': {'color': MUTED}, 'itemWidth': 12, 'itemHeight': 12,
                   'icon': 'roundRect'},
        'tooltip': {'trigger': 'axis', 'axisPointer': {'type': 'shadow'}},
        'xAxis': x_axis([str(y) for y in years]),
        'yAxis': y_axis(minInterval=1),
        'series': [{'name': 'Wins', 'type': 'bar', 'stack': 'p', 'data': [int(v) for v in wins_n],
                    'itemStyle': {'color': RED_BAR}, 'animationDelay': STAGGER},
                   {'name': 'Other podiums', 'type': 'bar', 'stack': 'p', 'data': [int(v) for v in other],
                    'itemStyle': {'color': GREY_BAR, 'borderRadius': [5, 5, 0, 0]}, 'animationDelay': STAGGER}],
    }, height)


def gauge(chance, label, height=270):
    render({
        'series': [{'type': 'gauge', 'startAngle': 210, 'endAngle': -30, 'min': 0, 'max': 100, 'radius': '96%',
                    'center': ['50%', '54%'], 'splitNumber': 5,
                    'progress': {'show': True, 'width': 16, 'roundCap': True,
                                 'itemStyle': {'color': {'type': 'linear', 'x': 0, 'y': 0, 'x2': 1, 'y2': 0,
                                                         'colorStops': [{'offset': 0, 'color': '#C41C0E'},
                                                                        {'offset': 1, 'color': '#FF7A6A'}]}}},
                    'axisLine': {'roundCap': True, 'lineStyle': {'width': 16, 'color': [[1, '#24242A']]}},
                    'pointer': {'length': '58%', 'width': 5, 'itemStyle': {'color': INK}},
                    'anchor': {'show': True, 'size': 14, 'itemStyle': {'color': INK, 'borderWidth': 3, 'borderColor': RED}},
                    'axisTick': {'show': False}, 'splitLine': {'length': 8, 'lineStyle': {'color': '#3A3A41', 'width': 2}},
                    'axisLabel': {'color': FAINT, 'distance': 22, 'fontSize': 11},
                    'title': {'offsetCenter': [0, '86%'], 'color': MUTED, 'fontSize': 13},
                    'detail': {'valueAnimation': True, 'offsetCenter': [0, '42%'], 'formatter': '{value}%',
                               'color': INK, 'fontSize': 40, 'fontWeight': 800},
                    'data': [{'value': round(chance), 'name': label}]}],
        'animationDuration': 1500,
        'animationEasing': 'elasticOut',
    }, height)


def chance_curve(curve, selected, height=300, subtitle=''):
    data = [{'value': round(v, 1), 'itemStyle': {'color': RED_BAR if i + 1 == selected else GREY_BAR}}
            for i, v in enumerate(curve)]
    render({
        'title': title(f'Predicted podium chance by grid slot{subtitle}'),
        'tooltip': {'formatter': '__fn__function (p) { return "From <b>" + p.name + "</b>: " + p.value + "%"; }'},
        'xAxis': x_axis([f'P{i}' for i in range(1, len(curve) + 1)]),
        'yAxis': y_axis(max=100, axisLabel={'formatter': '{value}%'}),
        'series': [{'type': 'bar', 'data': data, 'barCategoryGap': '28%', 'itemStyle': {'borderRadius': [6, 6, 0, 0]},
                    'animationDelay': STAGGER}],
    }, height)


# ================================================================ driver deep dive
def rings(items, height=230):
    """A row of progress rings, e.g. [('Win rate', 31.2, '#FF2B17'), ...]. Each sweeps round and counts up."""
    n = len(items)
    series = []
    for i, (name, value, color) in enumerate(items):
        cx = f'{(i + 0.5) / n * 100:.1f}%'
        series.append({
            'type': 'gauge', 'startAngle': 90, 'endAngle': -270, 'min': 0, 'max': 100, 'radius': '62%',
            'center': [cx, '46%'], 'pointer': {'show': False},
            'progress': {'show': True, 'overlap': False, 'roundCap': True, 'clip': False, 'width': 12,
                         'itemStyle': {'color': color, 'shadowColor': color, 'shadowBlur': 12}},
            'axisLine': {'lineStyle': {'width': 12, 'color': [[1, '#202026']]}},
            'splitLine': {'show': False}, 'axisTick': {'show': False}, 'axisLabel': {'show': False},
            'title': {'offsetCenter': [0, '128%'], 'color': MUTED, 'fontSize': 13, 'fontWeight': 600},
            'detail': {'valueAnimation': True, 'offsetCenter': [0, 0], 'formatter': '{value}%', 'color': INK,
                       'fontSize': 24, 'fontWeight': 800},
            'data': [{'value': round(value), 'name': name}],
            'animationDuration': 1600 + i * 250, 'animationEasing': 'cubicOut'})
    # size each ring from its share of the width too, so the outer rings and their glow never touch the edges
    fit = '''window.fit = (o, w, h) => {
      const slot = w / o.series.length, r = Math.max(26, Math.min(h * 0.29, slot * 0.33));
      o.series.forEach(s => {
        s.radius = r; s.progress.width = s.axisLine.lineStyle.width = Math.max(6, Math.round(r * 0.17));
        s.detail.fontSize = Math.max(14, Math.round(r * 0.36));
        Object.assign(s.title, { fontSize: slot < 150 ? 11 : 13, width: slot - 12, overflow: 'break', lineHeight: 15 });
      });
      return o;
    };'''
    render({'series': series}, height, fit)


def radar(labels, maxes, driver_vals, field_vals, driver_name, color, height=330):
    labels_js = json.dumps(labels)
    render({
        'title': title('Against the field'),
        'legend': {'bottom': 0, 'textStyle': {'color': MUTED}, 'itemWidth': 12, 'itemHeight': 12, 'icon': 'roundRect'},
        'tooltip': {'trigger': 'item', 'formatter': '__fn__function (p) { const L = ' + labels_js + '; return "<b>" + p.name + "</b><br/>" + p.value.map((v, i) => L[i] + ": " + v + "%").join("<br/>"); }'},
        'radar': {'indicator': [{'name': l.replace(' ', '\n', 1) if len(l) > 9 else l, 'max': m} for l, m in zip(labels, maxes)],
                  'radius': '58%', 'center': ['50%', '50%'],
                  'splitNumber': 4, 'axisName': {'color': MUTED, 'fontSize': 12, 'lineHeight': 15},
                  'splitLine': {'lineStyle': {'color': 'rgba(255,255,255,0.08)'}},
                  'splitArea': {'areaStyle': {'color': ['rgba(255,255,255,0.015)', 'rgba(255,255,255,0.035)']}},
                  'axisLine': {'lineStyle': {'color': 'rgba(255,255,255,0.08)'}}},
        'series': [{'type': 'radar', 'symbol': 'circle', 'symbolSize': 6, 'data': [
            {'name': 'Field average', 'value': [round(v, 1) for v in field_vals],
             'lineStyle': {'color': '#8E8E93', 'type': 'dashed', 'width': 1.5}, 'itemStyle': {'color': '#8E8E93'},
             'areaStyle': {'color': 'rgba(142,142,147,0.10)'}},
            {'name': driver_name, 'value': [round(v, 1) for v in driver_vals],
             'lineStyle': {'color': color, 'width': 2.5}, 'itemStyle': {'color': color},
             'areaStyle': {'color': color + '40'}}]}],
        'animationDuration': 1800, 'animationEasing': 'elasticOut',
    }, height, '''window.fit = (o, w, h) => { o.radar.radius = Math.max(36, Math.min(h * 0.27, w / 2 - 74)); return o; };''')


def race_scatter(points, height=420):
    """Every start of one driver: grid slot (x) against result (y). points = [{'x','y','kind','race'}]."""
    style = {'Win': ('#FFD60A', 13), 'Podium': (RED, 11), 'Points': ('#F5F5F7', 8), 'No points': ('#6E6E73', 8),
             'DNF': ('#4A4A52', 8)}
    top = math.ceil(max([p['x'] for p in points] + [20]))
    series = []
    for kind, (color, size) in style.items():
        pts = [{'value': [p['x'], p['y']], 'race': p['race']} for p in points if p['kind'] == kind]
        if not pts:
            continue
        series.append({'name': kind, 'type': 'scatter', 'data': pts, 'symbolSize': size, 'clip': False,
                       'itemStyle': {'color': color, 'opacity': 0.9, 'borderColor': '#0A0A0C', 'borderWidth': 1,
                                     'shadowColor': color if kind in ('Win', 'Podium') else 'transparent',
                                     'shadowBlur': 10 if kind == 'Win' else 0},
                       'emphasis': {'scale': 1.6},
                       'animationDelay': '__fn__function (i) { return 200 + i * 12; }',
                       'animationDuration': 900, 'animationEasing': 'backOut'})
    end = {'value': [top, top], 'label': {'show': True, 'formatter': 'finished where they started', 'color': FAINT,
                                          'fontSize': 11, 'position': 'top', 'align': 'right', 'offset': [-4, -2]}}
    series.append({'type': 'line', 'data': [[1, 1], end], 'symbol': 'circle', 'symbolSize': 0, 'silent': True,
                   'lineStyle': {'color': 'rgba(255,255,255,0.18)', 'type': 'dashed', 'width': 1.5},
                   'z': 0, 'animationDuration': 1500})
    render({
        'title': title('Every race: grid slot vs result'),
        'legend': {'top': 30, 'left': 0, 'textStyle': {'color': MUTED}, 'itemWidth': 10, 'itemHeight': 10},
        'tooltip': {'trigger': 'item', 'formatter': '__fn__function (p) { if (!p.data.race) return ""; '
                                                     'return "<b>" + p.data.race + "</b><br/>Grid P" + p.value[0] + " → " + '
                                                     '(p.value[1] >= 24 ? "DNF" : "P" + p.value[1]); }'},
        'grid': {'top': 72, 'right': 24},
        'xAxis': {'type': 'value', 'min': 0, 'max': top + 1, 'name': 'Grid slot', 'nameLocation': 'middle', 'nameGap': 26,
                  'nameTextStyle': {'color': MUTED}, 'axisLabel': {'color': MUTED, 'formatter': 'P{value}', 'showMaxLabel': False},
                  'splitLine': {'lineStyle': {'color': 'rgba(255,255,255,0.05)'}}, 'axisLine': {'show': False},
                  'axisTick': {'show': False}, 'interval': 5},
        'yAxis': {'type': 'value', 'min': 0, 'max': 25, 'inverse': True, 'interval': 4,
                  'axisLabel': {'color': MUTED, 'showMaxLabel': False, 'formatter': '__fn__function (v) { return v >= 24 ? "DNF" : (v === 0 ? "" : "P" + v); }'},
                  'splitLine': {'lineStyle': {'color': 'rgba(255,255,255,0.05)'}}, 'axisLine': {'show': False},
                  'axisTick': {'show': False}},
        'series': series,
    }, height)


def career(years, wins_n, other, teams, colors, height=330):
    """Podiums per season, each season in the colour of the team the driver raced for."""
    win_data = [{'value': int(w), 'team': t, 'itemStyle': {'color': c}} for w, t, c in zip(wins_n, teams, colors)]
    pod_data = [{'value': int(o), 'team': t, 'itemStyle': {'color': c + '66', 'borderRadius': [5, 5, 0, 0]}}
                for o, t, c in zip(other, teams, colors)]
    render({
        'title': title('Career, season by season · coloured by team'),
        'tooltip': {'trigger': 'axis', 'axisPointer': {'type': 'shadow'},
                    'formatter': '__fn__function (ps) { const t = ps[0].data.team; let s = "<b>" + ps[0].name + "</b> · " + t; '
                                 'ps.forEach(p => { s += "<br/>" + p.seriesName + ": " + p.value; }); return s; }'},
        'legend': {'top': 4, 'right': 0, 'textStyle': {'color': MUTED}, 'itemWidth': 12, 'itemHeight': 12,
                   'icon': 'roundRect', 'data': ['Wins', 'Other podiums']},
        'xAxis': x_axis([str(y) for y in years]),
        'yAxis': y_axis(minInterval=1),
        'series': [{'name': 'Wins', 'type': 'bar', 'stack': 'p', 'data': win_data, 'barCategoryGap': '24%',
                    'itemStyle': {'color': '#F5F5F7'}, 'animationDelay': STAGGER},
                   {'name': 'Other podiums', 'type': 'bar', 'stack': 'p', 'data': pod_data,
                    'itemStyle': {'color': '#8E8E93'}, 'animationDelay': '__fn__function (i) { return 300 + i * 45; }'}],
    }, height)
