#!/usr/bin/env python3
"""
NBA 实时胜率预测 v6 — MC + ESPN + 🧑‍🤝‍🧑 Lineup Factors
========================================================
在 v5 基础上增加: 实时阵容强度因子
- 文班在/不在场 → 马刺防守效率调整
- 布伦森在/不在场 → 尼克斯进攻效率调整
- 板凳 vs 主力混搭 → 整体阵容深度系数

用法: python3 nba_live_v6.py [--watch] [--q4only]
"""
import numpy as np
import json, sys, time, os
import urllib.request

# ═════════════════════════════════════════════
# 球员影响力权重 — 从校准文件加载
# ═════════════════════════════════════════════
# 通过 models/calibrate_weights.py 赛后校准更新
# 前 K 场偏向手动先验, 之后逐步信任实际 +/- 数据

WEIGHTS_FILE = os.path.join(os.path.dirname(__file__), 'lineup_weights.json')

def _load_weights():
    try:
        with open(WEIGHTS_FILE) as f:
            data = json.load(f)
        return {name: p['impact'] for name, p in data.get('players', {}).items()}, data.get('default_impact', 0.99)
    except:
        return {}, 0.99

PLAYER_IMPACT, DEFAULT_IMPACT = _load_weights()

# ═════════════════════════════════════════════
# 阵容强度计算 (保守版)
# ═════════════════════════════════════════════
# 方法: 场上5人影响因子的均值, 范围压缩到 [0.97, 1.03]
# 即最多调整 ±3% 的进攻效率

# ═════════════════════════════════════════════
# 阵容推导 (从替换人事件追踪)
# ═════════════════════════════════════════════
# 替代 athlete.active 方法, 更可靠的直播阵容
# 移植自 nba-on-court (shufinskiy) 的核心算法

def _parse_team_id_map(data):
    m = {}
    for comp in data.get('header', {}).get('competitions', []):
        for c in comp.get('competitors', []):
            m[c['team']['id']] = c['team']['abbreviation']
    return m

def _parse_player_id_map(data):
    m = {}
    for team_data in data.get('boxscore', {}).get('players', []):
        for sl in team_data.get('statistics', []):
            for a in sl.get('athletes', []):
                ath = a.get('athlete', {})
                pid = ath.get('id')
                name = ath.get('displayName')
                if pid and name:
                    m[pid] = name
    return m

def derive_lineup_from_data(data, game_id='401859967'):
    """
    从已获取的 ESPN summary 数据推导场上阵容。
    返回 {abbr: {'on_court': [names], 'bench': [names]}}
    """
    team_ids = _parse_team_id_map(data)
    player_names = _parse_player_id_map(data)
    
    # 获取每队的首发/替补列表
    starters = {}
    bench_players = {}
    for team_data in data.get('boxscore', {}).get('players', []):
        team_info = team_data.get('team', {})
        tid = str(team_info.get('id', ''))
        abbr = team_ids.get(tid, '??')
        if not abbr or abbr == '??': continue
        
        starters.setdefault(abbr, [])
        bench_players.setdefault(abbr, [])
        for sl in team_data.get('statistics', []):
            for a in sl.get('athletes', []):
                if a.get('didNotPlay'): continue
                pid = a.get('athlete', {}).get('id')
                if pid:
                    if a.get('starter'):
                        starters[abbr].append(pid)
                    else:
                        bench_players[abbr].append(pid)
    
    # 初始化场上阵容: 首发5人
    on_court = {}
    for team in starters:
        on_court[team] = set(starters[team][:5])
    
    # 处理替换人事件
    plays = data.get('plays', [])
    subs = []
    for p in plays:
        if p.get('type', {}).get('text') == 'Substitution':
            period = p.get('period', {}).get('number', 1)
            seq = int(p.get('sequenceNumber', 0))
            c = p.get('clock', {}).get('displayValue', '12:00')
            parts = c.split(':')
            clock_sec = int(parts[0])*60 + int(parts[1]) if len(parts)==2 else 0
            
            participants = p.get('participants', [])
            if len(participants) >= 2:
                p_in = str(participants[0].get('athlete', {}).get('id'))
                p_out = str(participants[1].get('athlete', {}).get('id'))
                t_id = str(p.get('team', {}).get('id', ''))
                team = team_ids.get(t_id, '??')
                if team != '??':
                    subs.append((period, -clock_sec, seq, team, p_in, p_out))
    
    subs.sort()
    
    # 应用换人
    for _, _, _, team, p_in, p_out in subs:
        if team not in on_court:
            continue
        if p_out in on_court[team] and p_in not in on_court[team]:
            on_court[team].discard(p_out)
            on_court[team].add(p_in)
    
    # 构建返回值
    result = {}
    for team in on_court:
        all_pids = set(starters.get(team, []) + bench_players.get(team, []))
        on_names, bench_names = [], []
        for pid in all_pids:
            name = player_names.get(pid, f'ID:{pid}')
            if pid in on_court[team]:
                on_names.append(name)
            else:
                bench_names.append(name)
        result[team] = {'on_court': on_names[:5], 'bench': bench_names[:5]}
    
    return result.get('SA'), result.get('NY')

def lineup_adjustment(lineup_data):
    """
    计算阵容调整系数。
    返回: 进攻效率乘数, 范围 ~[0.97, 1.03]
    
    逻辑:
    - 场上5人的impact均值
    - 以1.00为基线 (5个普通首发)
    - 压缩到 ±3%, 防止过度敏感
    """
    if not lineup_data:
        return 1.0
    
    on_court = lineup_data.get('on_court', [])
    if not on_court:
        return 1.0
    
    impacts = [PLAYER_IMPACT.get(p, DEFAULT_IMPACT) for p in on_court[:5]]
    raw_factor = sum(impacts) / len(impacts)
    
    # 压缩到 [0.97, 1.03]
    factor = max(0.97, min(1.03, raw_factor))
    return factor


def fetch_lineup_adjustments(summary_data=None):
    """获取阵容调整; 返回 (sa_factor, ny_factor, sa_lu, ny_lu)"""
    if summary_data:
        sa_lu, ny_lu = derive_lineup_from_data(summary_data)
    else:
        sa_lu, ny_lu = None, None
    sa_f = lineup_adjustment(sa_lu)
    ny_f = lineup_adjustment(ny_lu)
    return sa_f, ny_f, sa_lu, ny_lu


# ═════════════════════════════════════════════
# 比赛数据获取 (同 v5)
# ═════════════════════════════════════════════

def fetch_game(game_id=None):
    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=20260613" if not game_id else \
        f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={game_id}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        data = json.load(resp)
    if game_id:
        comps = data.get('header', {}).get('competitions', [])
    else:
        events = data.get('events', [])
        if not events: return None
        comps = [events[0]['competitions'][0]]
    if not comps: return None
    comp = comps[0]
    status = comp['status']
    game = {
        'clock': status.get('clock', 0), 'period': status.get('period', 1),
        'detail': status['type']['detail'], 'state': status['type']['state'],
        'is_finished': status.get('type', {}).get('completed', False),
        'teams': {},
    }
    for c in comp['competitors']:
        abbr = c['team']['abbreviation']
        stats = {}
        for s in c.get('statistics', []):
            v = s.get('displayValue', '0')
            name = s['name']
            try: stats[name] = float(v) if '.' in str(v) else int(v)
            except: stats[name] = v
        game['teams'][abbr] = {'score': int(c['score']), 'stats': stats, 'home_away': c.get('homeAway', '')}
    return game


# ═════════════════════════════════════════════
# MC 引擎 (含阵容因子)
# ═════════════════════════════════════════════

SEASON = {
    'NY': {'fg%': 0.478, '3p%': 0.373, 'ft%': 0.792, 'pace': 97.5, 'ortg': 116.5},
    'SA': {'fg%': 0.483, '3p%': 0.359, 'ft%': 0.787, 'pace': 100.2, 'ortg': 119.8},
}

def shrink(gm, ga, sp, k=10):
    if ga == 0: return sp
    return min((gm + k * sp) / (ga + k), 0.85)

def mc_with_lineup(game, n=10000, seed=42, summary_data=None):
    teams = game['teams']
    t1, t2 = list(teams.keys())[0], list(teams.keys())[1]
    home = [t for t in [t1, t2] if teams[t]['home_away'] == 'home'][0]
    away = [t for t in [t1, t2] if teams[t]['home_away'] != 'home'][0]
    
    remaining = max(0, (4 - game['period']) * 720 + game['clock'])
    pace = (SEASON.get(t1, {}).get('pace', 98) + SEASON.get(t2, {}).get('pace', 98)) / 2
    poss = int(pace * remaining / 2880)
    if poss < 1: poss = 1
    
    adj = {}
    for t in [t1, t2]:
        s = teams[t]['stats']
        seas = SEASON.get(t, {})
        adj[t] = {
            'fg': shrink(s.get('fieldGoalsMade',0), s.get('fieldGoalsAttempted',0), seas.get('fg%', 0.48), 10),
            '3p': shrink(s.get('threePointFieldGoalsMade',0), s.get('threePointFieldGoalsAttempted',0), seas.get('3p%', 0.36), 10),
            'ft': shrink(s.get('freeThrowsMade',0), s.get('freeThrowsAttempted',0), seas.get('ft%', 0.79), 10),
            '3r': shrink(s.get('threePointFieldGoalsAttempted',0), s.get('fieldGoalsAttempted',0), 0.38, 15),
            'fr': shrink(s.get('freeThrowsAttempted',0), s.get('fieldGoalsAttempted',0), 0.21, 15),
        }
    
    # ═══ 阵容因子 (从替换人事件推导) ═══
    sa_factor, ny_factor, sa_lu, ny_lu = fetch_lineup_adjustments(summary_data)
    
    home_factor = sa_factor if home == 'SA' else ny_factor
    away_factor = ny_factor if home == 'SA' else sa_factor
    
    rng = np.random.default_rng(seed)
    wins = {home: 0, away: 0}
    for _ in range(n):
        sc = {}
        for t in [t1, t2]:
            a = adj[t]
            factor = home_factor if t == home else away_factor
            pts = 0
            for _ in range(poss):
                r = rng.random()
                if r < a['fr']:
                    pts += (rng.random() < a['ft']) + (rng.random() < a['ft'])
                elif r < a['fr'] + a['3r']:
                    pts += 3 if rng.random() < a['3p'] * factor else 0
                else:
                    pts += 2 if rng.random() < a['fg'] * factor else 0
            sc[t] = teams[t]['score'] + int(pts)
        if sc[home] > sc[away]: wins[home] += 1
        elif sc[away] > sc[home]: wins[away] += 1
    
    return wins[home]/n*100, wins[away]/n*100, poss, sa_factor, ny_factor, sa_lu, ny_lu


# ═════════════════════════════════════════════
# 输出
# ═════════════════════════════════════════════

def format_lineup(lu_data, label, factor):
    if not lu_data:
        return f"  {label}: (无数据)"
    on = lu_data.get('on_court', [])
    bench = lu_data.get('bench', [])
    lines = [f"  {label} | 阵容系数: {factor:.3f}"]
    avg_impact = sum(PLAYER_IMPACT.get(p, DEFAULT_IMPACT) for p in on) / max(len(on), 1)
    lines.append(f"  🔥 场上: {', '.join(on[:5])} (均效{avg_impact:.3f})")
    if bench:
        lines.append(f"  🪑 替补: {', '.join(bench[:3])}")
    return '\n'.join(lines)

def print_result(game, mc_h, mc_a, poss, sa_f, ny_f, sa_lu, ny_lu, espn_wp=None):
    teams = game['teams']
    home = [t for t in teams if teams[t]['home_away'] == 'home'][0]
    away = [t for t in teams if teams[t]['home_away'] != 'home'][0]
    
    print(f"\n{'='*56}")
    print(f"  🏀 NBA 实时胜率预测 v6 — Lineup Enhanced")
    print(f"  {game['detail']} | {home} {teams[home]['score']} — {teams[away]['score']} {away}")
    print(f"  {'='*52}")
    
    # 阵容
    print(f"\n🧑‍🤝‍🧑 当前阵容:")
    print(format_lineup(sa_lu, 'SA', sa_f))
    print()
    print(format_lineup(ny_lu, 'NY', ny_f))
    
    # 胜率
    print(f"\n📊 胜率预测 (MC+ESPN):")
    print(f"  🎲 MC v6 (含阵容)  {mc_h:>5.1f}% | 模拟回合: {poss}")
    if espn_wp:
        print(f"  🏢 ESPN            {espn_wp['p_home']:>5.1f}%")
    print(f"  {'─'*50}")
    
    # vs 无阵容版本的比较 (用season基线估算)
    print(f"  阵容调整: SA x{sa_f:.3f} | NY x{ny_f:.3f}")
    print(f"{'='*56}")


# ═════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════

def fetch_espn_wp(summary_data=None):
    if summary_data:
        wp = summary_data.get('winprobability', [])
        if wp:
            hwp = wp[-1].get('homeWinPercentage', 0)
            return {'p_home': hwp * 100, 'p_away': (1-hwp) * 100}
    try:
        url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event=401859967"
        with urllib.request.urlopen(url, timeout=5) as r:
            d = json.load(r)
        wp = d.get('winprobability', [])
        if wp:
            hwp = wp[-1].get('homeWinPercentage', 0)
            return {'p_home': hwp * 100, 'p_away': (1-hwp) * 100}
    except: pass
    return None

def main():
    watch = '--watch' in sys.argv
    
    print(f"{'='*56}")
    print(f"  NBA 实时胜率预测 v6 — Lineup Enhanced")
    print(f"  MC 引擎 + ESPN + 实时阵容因子")
    print(f"{'='*56}")
    
    try:
        while True:
            game = fetch_game()
            if not game or game['is_finished']:
                print("  比赛已结束或无数据")
                return
            
            # 统一获取 summary 数据 (阵容 + ESPN WP 共用)
            summary_data = None
            try:
                url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event=401859967"
                with urllib.request.urlopen(url, timeout=5) as r:
                    summary_data = json.load(r)
            except: pass
            
            mc_h, mc_a, poss, sa_f, ny_f, sa_lu, ny_lu = mc_with_lineup(game, summary_data=summary_data)
            espn_wp = fetch_espn_wp(summary_data)
            
            if watch:
                ts = time.strftime('%H:%M:%S')
                sa_on = sa_lu.get('on_court',['?']) if sa_lu else ['?']
                ny_on = ny_lu.get('on_court',['?']) if ny_lu else ['?']
                wemby = '✓' if sa_lu and 'Victor Wembanyama' in sa_lu['on_court'] else '✗'
                brunson = '✓' if ny_lu and 'Jalen Brunson' in ny_lu['on_court'] else '✗'
                
                print(f"\n{'─'*52}")
                print(f"  ⏱ {ts} | {game['detail']} | SA {game['teams']['SA']['score']} — {game['teams']['NY']['score']} NY")
                print(f"{'─'*52}")
                print(f"  🎲 MC v6 {mc_h:.1f}% | 🏢 ESPN {(espn_wp['p_home'] if espn_wp else 0):.1f}%")
                print(f"  🧑‍🤝‍🧑 文班{wemby} 布伦森{brunson} | SA阵容x{sa_f:.3f} NY阵容x{ny_f:.3f}")
            else:
                print_result(game, mc_h, mc_a, poss, sa_f, ny_f, sa_lu, ny_lu, espn_wp)
            
            if not watch: break
            time.sleep(15)
    except KeyboardInterrupt:
        print(f"\n\n  👋 再见!")

if __name__ == '__main__':
    main()
