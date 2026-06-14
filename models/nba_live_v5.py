#!/usr/bin/env python3
"""
NBA 实时胜率预测 v5 — Logistic 回归 + 蒙特卡洛双引擎
===================================================
方法:
  [主] Logistic 回归: 基于历史NBA数据的校准参数, 毫秒级
  [辅] 蒙特卡洛: 逐回合模拟, 验证Logistic结果

数据源: ESPN 公共 API
用法:
  python3 nba_live_v5.py              → 当前比赛
  python3 nba_live_v5.py --watch      → 每15秒自动刷新
  python3 nba_live_v5.py --mc         → 仅蒙特卡洛模式

⚠️ DISCLAIMER: For educational/research purposes only.
NOT for gambling or betting. Use at your own risk.
Full disclaimer: see DISCLAIMER.md
"""
import numpy as np
import json, sys, time, os
import urllib.request
from typing import Dict, Optional
from dataclasses import dataclass

# ═════════════════════════════════════════════
# 1. 数据层
# ═════════════════════════════════════════════

def fetch_game(game_id: Optional[str] = None) -> Dict:
    """从 ESPN API 拉取实时数据"""
    if game_id:
        url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={game_id}"
    else:
        url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=20260613"
    
    with urllib.request.urlopen(url, timeout=10) as resp:
        data = json.load(resp)
    
    if game_id:
        # summary 格式
        header = data.get('header', {})
        comps = header.get('competitions', [])
    else:
        events = data.get('events', [])
        if not events:
            return None
        comps = [events[0]['competitions'][0]]
    
    if not comps:
        return None
    
    comp = comps[0]
    status = comp['status']
    
    game = {
        'clock': status.get('clock', 0),
        'period': status.get('period', 1),
        'detail': status['type']['detail'],
        'state': status['type']['state'],
        'is_live': status['type']['state'] == 'in',
        'is_finished': status.get('type', {}).get('completed', False),
        'teams': {},
    }
    
    for c in comp['competitors']:
        abbr = c['team']['abbreviation']
        stats = {}
        for s in c.get('statistics', []):
            val = s.get('displayValue', '0')
            stats[s['name']] = float(val) if '.' in str(val).replace('-','').replace(':','') and '%' not in str(val) else (
                int(val) if str(val).lstrip('-').isdigit() else val
            )
        # Fix: parse percentages correctly
        stats = {}
        for s in c.get('statistics', []):
            v = s.get('displayValue', '0')
            name = s['name']
            if isinstance(v, str) and v.endswith('%'):
                stats[name] = float(v.rstrip('%'))
            elif isinstance(v, str) and ':' in v:
                stats[name] = v  # time string
            else:
                try:
                    stats[name] = int(v) if '.' not in v else float(v)
                except:
                    stats[name] = v
        
        game['teams'][abbr] = {
            'score': int(c['score']),
            'stats': stats,
            'home_away': c.get('homeAway', ''),
            'linescores': [ls['value'] for ls in c.get('linescores', [])],
        }
    
    # 获取 espn win probability
    if not game_id:
        try:
            summary_url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={comps[0].get('id','')}"
            # Actually get the event id from somewhere
        except:
            pass
    
    return game


# ═════════════════════════════════════════════
# 2. 赛季基线
# ═════════════════════════════════════════════

SEASON = {
    'NY': {'fg%': 0.480, '3p%': 0.362, 'ft%': 0.785, 'pace': 97.5, 'ortg': 116.5, 'drtg': 101.3},
    'SA': {'fg%': 0.480, '3p%': 0.370, 'ft%': 0.795, 'pace': 100.2, 'ortg': 119.8, 'drtg': 105.3},
}


# ═════════════════════════════════════════════
# 3. 引擎 A: Logistic 回归 (主)
# ═════════════════════════════════════════════

def logistic_win_prob(game: Dict) -> Dict:
    """
    Logistic 回归胜率模型
    
    基于 NBA 历史数据校准参数 (Inpredictable, 538 等公开研究):
      z = β₀ + β₁ × score_diff + β₂ × score_diff × √(seconds_remaining)
      p = 1 / (1 + e^(-z))
    
    参数校准来源:
      - β₁ (分差项): ~0.000455 (每分每秒的影响)
      - β₂ (分差×时间交互): 让早期大分差不那么致命, 后期小分差很致命
      - β₀ (截距): ~0 (均衡开局)
      - 主场调整: +0.04 × (sec/3600) 在截距上
    """
    teams = game['teams']
    t_order = sorted(teams.keys(), key=lambda t: teams[t]['home_away'] == 'home', reverse=True)
    home, away = t_order[0], t_order[1]
    
    s_home = teams[home]['score']
    s_away = teams[away]['score']
    score_diff = s_home - s_away  # 正值 = 主队领先
    
    clock = game['clock']
    period = game['period']
    
    # 总剩余秒数
    if game['state'] == 'pre':
        remaining_sec = 2880  # 整场
    else:
        remaining_sec = max(0, (4 - period) * 720 + clock)
    
    # ── Logistic 回归参数 ──
    # 这几个参数来自公开的NBA胜率模型校准 (Inpredictable, 2017)
    B0 = 0.0       # 截距 (主场优势在此处理)
    B1 = 0.000455  # 分差主效应
    B2 = 0.0040    # 分差 × √时间 交互项
    
    # 主场优势: 约2.5分/48分钟 → 开局~55%
    home_boost = 0.04 * (remaining_sec / 2880)
    
    z = B0 + home_boost + B1 * score_diff * remaining_sec + B2 * score_diff * np.sqrt(remaining_sec)
    p_home = 1.0 / (1.0 + np.exp(-z))
    p_away = 1.0 - p_home
    
    # 校准: 夹逼边界
    p_home = np.clip(p_home, 0.001, 0.999)
    p_away = 1.0 - p_home
    
    # 预期终分: 简单模型
    # 使用当前节奏估计剩余得分
    avg_pace = (SEASON[home]['pace'] + SEASON[away]['pace']) / 2
    team_poss = avg_pace * remaining_sec / 2880
    
    # 用赛季ORTG估计剩余得分
    home_ppp = SEASON[home]['ortg'] / 100 + 0.025  # 主场
    away_ppp = SEASON[away]['ortg'] / 100
    
    expected_home_extra = home_ppp * team_poss
    expected_away_extra = away_ppp * team_poss
    
    return {
        'method': 'Logistic 回归',
        'home': home,
        'away': away,
        'score_home': s_home,
        'score_away': s_away,
        'p_home': p_home * 100,
        'p_away': p_away * 100,
        'pred_home': s_home + expected_home_extra,
        'pred_away': s_away + expected_away_extra,
        'remaining_sec': remaining_sec,
        'team_poss': team_poss,
        'params': {'B0': B0, 'B1': B1, 'B2': B2, 'home_boost_start': home_boost},
        'detail': game['detail'],
    }


# ═════════════════════════════════════════════
# 4. 引擎 B: 蒙特卡洛 (辅)
# ═════════════════════════════════════════════

def bayesian_shrinkage(gm, ga, sp, k=10):
    if ga == 0: return sp
    return min((gm + k * sp) / (ga + k), 0.85)

def mc_win_prob(game: Dict, n_sims: int = 20000, k: int = 10, seed=42) -> Dict:
    teams = game['teams']
    t_names = sorted(teams.keys())
    t1, t2 = t_names[0], t_names[1]
    s1, s2 = teams[t1]['score'], teams[t2]['score']
    
    remaining_sec = max(0, (4 - game['period']) * 720 + game['clock'])
    if game['state'] == 'pre':
        remaining_sec = 2880
    
    avg_pace = (SEASON[t1]['pace'] + SEASON[t2]['pace']) / 2
    team_poss = int(avg_pace * remaining_sec / 2880)
    
    adj = {}
    for t in t_names:
        st = teams[t]['stats']
        s = SEASON[t]
        adj[t] = {
            'fg%': bayesian_shrinkage(st.get('fieldGoalsMade',0), st.get('fieldGoalsAttempted',0), s['fg%'], k),
            '3p%': bayesian_shrinkage(st.get('threePointFieldGoalsMade',0), st.get('threePointFieldGoalsAttempted',0), s['3p%'], k),
            'ft%': bayesian_shrinkage(st.get('freeThrowsMade',0), st.get('freeThrowsAttempted',0), s['ft%'], k),
            '3pa_r': bayesian_shrinkage(st.get('threePointFieldGoalsAttempted',0), st.get('fieldGoalsAttempted',0), 0.38, k),
            'ft_r': bayesian_shrinkage(st.get('freeThrowsAttempted',0), st.get('fieldGoalsAttempted',0), 0.21, k),
        }
    
    rng = np.random.default_rng(seed)
    wins = {t1: 0, t2: 0}
    
    for _ in range(n_sims):
        scores = {}
        for t in t_names:
            extra = 0
            a = adj[t]
            for _ in range(team_poss):
                r = rng.random()
                if r < a['ft_r']:
                    extra += (rng.random() < a['ft%']) + (rng.random() < a['ft%'])
                elif r < a['ft_r'] + a['3pa_r']:
                    extra += 3 if rng.random() < a['3p%'] else 0
                else:
                    extra += 2 if rng.random() < a['fg%'] else 0
            if t == t1 and teams[t]['home_away'] == 'home':
                extra = int(extra * 1.025)
            scores[t] = teams[t]['score'] + extra
        
        if scores[t1] > scores[t2]:
            wins[t1] += 1
        elif scores[t2] > scores[t1]:
            wins[t2] += 1
    
    # 谁是主队
    home = [t for t in t_names if teams[t]['home_away'] == 'home'][0]
    away = [t for t in t_names if teams[t]['home_away'] != 'home'][0]
    
    return {
        'method': f'蒙特卡洛 ({n_sims:,}次)',
        'home': home,
        'away': away,
        'score_home': teams[home]['score'],
        'score_away': teams[away]['score'],
        'p_home': wins[home] / n_sims * 100,
        'p_away': wins[away] / n_sims * 100,
        'remaining_sec': remaining_sec,
        'team_poss': team_poss,
        'detail': game['detail'],
        'adj': adj,
    }


# ═════════════════════════════════════════════
# 5. ESPN 模型对比
# ═════════════════════════════════════════════

def fetch_espn_wp() -> Optional[Dict]:
    """从ESPN summary API拉取他们的胜率"""
    try:
        url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event=401859967"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.load(resp)
        wp = data.get('winprobability', [])
        if wp:
            hwp = wp[-1].get('homeWinPercentage', 0)
            return {'p_home': hwp * 100, 'p_away': (1-hwp) * 100}
    except:
        pass
    return None


# ═════════════════════════════════════════════
# 6. 输出
# ═════════════════════════════════════════════

def print_prediction(log_r: Dict, mc_r: Optional[Dict] = None, espn_wp: Optional[Dict] = None):
    """格式化输出两个引擎的结果"""
    home, away = log_r['home'], log_r['away']
    
    print(f"\n{'='*52}")
    print(f"  🏀 NBA 实时胜率预测 v5")
    print(f"  {'='*48}")
    print(f"  {log_r['detail']}")
    print(f"  {home} {log_r['score_home']} — {log_r['score_away']} {away}")
    print(f"  {'='*48}")
    
    # Logistic 回归 (主引擎)
    print(f"  📐 Logistic 回归 [主]")
    print(f"  {home:<18}: {log_r['p_home']:>5.1f}%  | 终分 {log_r['pred_home']:.0f}")
    print(f"  {away:<18}: {log_r['p_away']:>5.1f}%  | 终分 {log_r['pred_away']:.0f}")
    
    # 蒙特卡洛 (辅引擎)
    if mc_r:
        print(f"  {'─'*48}")
        print(f"  🎲 {mc_r['method']} [辅]")
        print(f"  {home:<18}: {mc_r['p_home']:>5.1f}%")
        print(f"  {away:<18}: {mc_r['p_away']:>5.1f}%")
    
    # ESPN 对比
    if espn_wp:
        print(f"  {'─'*48}")
        print(f"  🏢 ESPN 官方")
        print(f"  {home:<18}: {espn_wp['p_home']:>5.1f}%")
        print(f"  {away:<18}: {espn_wp['p_away']:>5.1f}%")
    
    # 三个模型对比
    models = {'Logistic': log_r}
    if mc_r: models['MC'] = mc_r
    if espn_wp: models['ESPN'] = espn_wp
    
    print(f"  {'─'*48}")
    print(f"  模型对比 (主场胜率):")
    for name, m in models.items():
        emoji = {'Logistic':'📐','MC':'🎲','ESPN':'🏢'}.get(name, ' ')
        bar = '█' * int(m['p_home'] / 2) + '░' * (50 - int(m['p_home'] / 2))
        print(f"  {emoji} {name:<10} {m['p_home']:>5.1f}% {bar}")
    
    print(f"{'='*52}")
    
    # 如果比赛已结束
    if mc_r and mc_r.get('detail', '').startswith('Final'):
        print(f"\n  🏁 比赛已结束")
    print()


# ═════════════════════════════════════════════
# 7. 主循环
# ═════════════════════════════════════════════

def main():
    watch_mode = '--watch' in sys.argv
    mc_only = '--mc' in sys.argv
    
    print(f"\n{'='*52}")
    print(f"  NBA 实时胜率预测引擎 v5")
    print(f"  Logistic + MC 双引擎")
    print(f"{'='*52}")
    
    if watch_mode:
        print(f"  Watch 模式: 每15秒自动刷新 (Ctrl+C 退出)\n")
    
    try:
        while True:
            game = fetch_game()
            if not game:
                print("  ❌ 无法获取比赛数据")
                return
            
            if game['is_finished']:
                print(f"  🏁 比赛已结束!")
            
            # Logistic (快, 必跑)
            log_r = logistic_win_prob(game)
            
            # MC (跑少一点次数)
            mc_r = None
            if not mc_only:
                mc_r = mc_win_prob(game, n_sims=10000)
            else:
                mc_r = mc_win_prob(game, n_sims=50000)
            
            # ESPN
            espn_wp = fetch_espn_wp()
            
            # 增量输出 (不刷屏, 带时间戳)
            if watch_mode:
                ts = time.strftime('%H:%M:%S')
                print(f"\n{'─'*52}")
                print(f"  ⏱ {ts} | {game['detail']} | SA {game['teams']['SA']['score']} — {game['teams']['NY']['score']} NY")
                print(f"{'─'*52}")
                print(f"  📐 Logistic  {log_r['p_home']:>5.1f}%  |  🎲 MC  {mc_r['p_home']:>5.1f}%  |  🏢 ESPN  {(espn_wp['p_home'] if espn_wp else 0):>5.1f}%")
            else:
                print_prediction(log_r, mc_r, espn_wp)
            
            if not watch_mode:
                break
            
            time.sleep(15)
            
    except KeyboardInterrupt:
        print("\n\n  👋 再见!")


if __name__ == '__main__':
    main()
