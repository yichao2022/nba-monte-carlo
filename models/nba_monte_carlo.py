#!/usr/bin/env python3
"""
NBA 实时胜率预测模型 v4
========================
方法: 贝叶斯收缩投篮命中率 + 蒙特卡洛模拟
数据源: ESPN 公共 API
"""

import numpy as np
import json
import urllib.request
from typing import Dict


# ═════════════════════════════════════════════
# 1. 获取实时比赛数据
# ═════════════════════════════════════════════

def fetch_live_game(debug=False) -> Dict:
    """从 ESPN API 拉取实时比分、投篮统计和时间"""
    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=20260610"
    with urllib.request.urlopen(url, timeout=10) as resp:
        data = json.load(resp)

    event = data['events'][0]
    comp = event['competitions'][0]

    status = comp['status']
    clock_sec = status['clock']
    period = status['period']
    detail = status['type']['detail']

    teams = {}
    for c in comp['competitors']:
        abbr = c['team']['abbreviation']
        stats = {}
        for s in c.get('statistics', []):
            val = s.get('displayValue', '0')
            stats[s['name']] = float(val) if '.' in val else int(val)
        teams[abbr] = {
            'score': int(c['score']),
            'stats': stats,
            'linescores': [ls['value'] for ls in c.get('linescores', [])],
        }
        if debug:
            print(f"  {abbr} raw stats: {json.dumps(stats, indent=2)}")

    return {
        'teams': teams,
        'clock_sec': clock_sec,
        'period': period,
        'detail': detail,
    }


# ═════════════════════════════════════════════
# 2. 赛季基线数据
# ═════════════════════════════════════════════

SEASON = {
    'NY': {'fg%': 0.480, '3p%': 0.362, 'ft%': 0.785,
           '3pa_rate': 0.37, 'ft_rate': 0.22, 'pace': 97.5, 'ortg': 116.5},
    'SA': {'fg%': 0.480, '3p%': 0.370, 'ft%': 0.795,
           '3pa_rate': 0.40, 'ft_rate': 0.20, 'pace': 100.2, 'ortg': 119.8},
}

HOME_COURT_PPP = 0.025  # +2.5分/场


# ═════════════════════════════════════════════
# 3. 贝叶斯收缩
# ═════════════════════════════════════════════

def bayesian_shrinkage(game_made: int, game_att: int,
                       season_pct: float, k: int = 10) -> float:
    """
    贝叶斯收缩: 当场命中率 → 赛季平均

    θ̂ = (made + κ·p_season) / (att + κ)

    κ=10: 约10次出手后当场数据主导
    κ→∞: 纯赛季平均
    κ=0: 纯当场数据 (小样本噪音)
    """
    if game_att == 0:
        return season_pct
    return min((game_made + k * season_pct) / (game_att + k), 0.85)


# ═════════════════════════════════════════════
# 4. 蒙特卡洛模拟
# ═════════════════════════════════════════════

def simulate_game(game: Dict, n_sims: int = 50000,
                  k: int = 10, seed: int = 42) -> Dict:
    teams = game['teams']
    t1, t2 = 'NY', 'SA'
    s1, s2 = teams[t1]['score'], teams[t2]['score']

    # 剩余时间 → 预计回合数
    remaining_sec = (4 - game['period']) * 720 + game['clock_sec']
    avg_pace = (SEASON[t1]['pace'] + SEASON[t2]['pace']) / 2
    team_poss = int(avg_pace * remaining_sec / 2880)

    # 贝叶斯调整命中率
    adj = {}
    for t in (t1, t2):
        st = teams[t]['stats']
        s = SEASON[t]
        adj[t] = {
            'fg%':    bayesian_shrinkage(st.get('fieldGoalsMade',0), st.get('fieldGoalsAttempted',0), s['fg%'], k),
            '3p%':    bayesian_shrinkage(st.get('threePointFieldGoalsMade',0), st.get('threePointFieldGoalsAttempted',0), s['3p%'], k),
            'ft%':    bayesian_shrinkage(st.get('freeThrowsMade',0), st.get('freeThrowsAttempted',0), s['ft%'], k),
            '3pa_rate': bayesian_shrinkage(st.get('threePointFieldGoalsAttempted',0), st.get('fieldGoalsAttempted',0), s['3pa_rate'], k),
            'ft_rate':  bayesian_shrinkage(st.get('freeThrowsAttempted',0), st.get('fieldGoalsAttempted',0), s['ft_rate'], k),
        }

    # 模拟
    rng = np.random.default_rng(seed)
    wins = {t1: 0, t2: 0}
    finals = {t1: [], t2: []}

    for _ in range(n_sims):
        scores = {}
        for t in (t1, t2):
            extra = 0
            a = adj[t]
            for _ in range(team_poss):
                r = rng.random()
                if r < a['ft_rate']:
                    extra += (rng.random() < a['ft%']) + (rng.random() < a['ft%'])
                elif r < a['ft_rate'] + a['3pa_rate']:
                    extra += 3 if rng.random() < a['3p%'] else 0
                else:
                    extra += 2 if rng.random() < a['fg%'] else 0
            if t == t1:  # 主场优势
                extra = int(extra * (1 + HOME_COURT_PPP))
            scores[t] = teams[t]['score'] + extra
            finals[t].append(scores[t])

        if scores[t1] > scores[t2]:
            wins[t1] += 1
        elif scores[t2] > scores[t1]:
            wins[t2] += 1

    return {
        'p1': wins[t1]/n_sims*100, 'p2': wins[t2]/n_sims*100,
        'mean1': float(np.mean(finals[t1])), 'std1': float(np.std(finals[t1])),
        'mean2': float(np.mean(finals[t2])), 'std2': float(np.std(finals[t2])),
        'team1': t1, 'team2': t2, 'score1': s1, 'score2': s2,
        'n_sims': n_sims, 'remaining_sec': remaining_sec, 'team_poss': team_poss,
        'detail': game['detail'], 'adj': adj, 'k': k, 'teams': game['teams'],
    }


# ═════════════════════════════════════════════
# 5. 输出
# ═════════════════════════════════════════════

def print_result(r: Dict):
    """格式化打印模型结果"""
    t1, t2 = r['team1'], r['team2']
    teams_raw = r['teams']

    print(f"\n{'='*50}")
    print(f"  NBA 实时胜率预测 — 贝叶斯蒙特卡洛")
    print(f"{'='*50}")
    print(f"  {r['detail']}")
    print(f"  {t1} {r['score1']} — {t2} {r['score2']}")
    print(f"  {'─'*46}")
    print(f"  🗽 Knicks: {r['p1']:.1f}%  | 终分 {r['mean1']:.0f} ± {r['std1']:.0f}")
    print(f"  🏹 Spurs:  {r['p2']:.1f}%  | 终分 {r['mean2']:.0f} ± {r['std2']:.0f}")
    print(f"  {'─'*46}")
    print(f"  剩余 {r['remaining_sec']/60:.1f}分钟 | ~{r['team_poss']}回合/队")

    # 显示当场投篮数据 + 调整后
    print(f"\n  📊 投篮数据 (当场 → 贝叶斯调整)")
    for t in (t1, t2):
        st = teams_raw[t]['stats']
        fg = f"{st.get('fieldGoalsMade',0)}/{st.get('fieldGoalsAttempted',0)}"
        tp = f"{st.get('threePointFieldGoalsMade',0)}/{st.get('threePointFieldGoalsAttempted',0)}"
        a = r['adj'][t]
        name = f"{'NY' if t=='NY' else 'SA'}"
        print(f"  {name}  FG: {fg} ({st.get('fieldGoalPct',0):.1f}%)→{a['fg%']*100:.1f}%  "
              f"3PT: {tp} ({st.get('threePointPct',0):.1f}%)→{a['3p%']*100:.1f}%")

    print(f"\n  ⚙️  {r['n_sims']:,}次 | κ={r['k']} | 主场+{HOME_COURT_PPP:.1%}")
    print(f"{'='*50}")


# ═════════════════════════════════════════════
# 6. 入口
# ═════════════════════════════════════════════

if __name__ == '__main__':
    print("🔄 拉取 ESPN API ...")
    game = fetch_live_game(debug=False)
    print(f"  → NY {game['teams']['NY']['score']} — SA {game['teams']['SA']['score']}")
    print(f"  → {game['detail']}")
    print(f"🔄 运行 {50000:,} 次 MC 模拟 ...")
    result = simulate_game(game, n_sims=50000, k=10)
    print_result(result)
