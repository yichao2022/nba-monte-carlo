#!/usr/bin/env python3
"""
赛后权重校准 — 从 ESPN API 拉 +/- 数据并更新 lineup_weights.json
==============================================================
用法:
    python3 calibrate_weights.py <game_id>
    python3 calibrate_weights.py 401859967    # G5 校准
    python3 calibrate_weights.py --last       # 最近一场已结束的比赛
"""

import json, sys, os, urllib.request
from datetime import datetime

WEIGHTS_FILE = os.path.join(os.path.dirname(__file__), 'lineup_weights.json')

# ═════════════════════════════════════════════
# 加载/保存权重
# ═════════════════════════════════════════════

def load_weights():
    with open(WEIGHTS_FILE) as f:
        return json.load(f)

def save_weights(data):
    data['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M')
    with open(WEIGHTS_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"  ✅ 权重已保存 → {WEIGHTS_FILE}")

# ═════════════════════════════════════════════
# 从 ESPN summary API 拉球员 +/- 
# ═════════════════════════════════════════════

def fetch_boxscore(game_id):
    """拉取完整 boxscore，返回 {team: [{name, min, pts, pm, starter}, ...]}"""
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={game_id}"
    print(f"  📡 请求: {url[:80]}...")
    with urllib.request.urlopen(url, timeout=10) as r:
        d = json.load(r)
    
    players_data = d.get('boxscore', {}).get('players', [])
    result = {}
    
    for team_data in players_data:
        team = team_data.get('team', {}).get('abbreviation', '??')
        statistics = team_data.get('statistics', [])
        if not statistics:
            continue
        
        # 第一组统计一般是基本数据
        labels = statistics[0].get('labels', [])
        athletes = statistics[0].get('athletes', [])
        
        # 在 labels 里找 +/- 的索引
        pm_idx = None
        min_idx = None
        pts_idx = None
        for i, lbl in enumerate(labels):
            lbl_lower = lbl.lower()
            if lbl_lower in ('+/-', 'plus/minus', 'plus-minus', '+ / -'):
                pm_idx = i
            if lbl_lower in ('min', 'minutes', 'min:sec', 'mins'):
                min_idx = i
            if lbl_lower in ('pts', 'points', 'p'):
                pts_idx = i
        
        print(f"  📋 {team} labels: {labels}")
        print(f"  🔍 pm_idx={pm_idx}, min_idx={min_idx}, pts_idx={pts_idx}")
        
        team_players = []
        for a in athletes:
            athlete = a.get('athlete', {})
            name = athlete.get('displayName', '??')
            stats = a.get('stats', [])
            
            # Parse minutes: '25:34' → 25.57
            minutes = 0
            if min_idx is not None and min_idx < len(stats):
                m_str = stats[min_idx]
                if ':' in m_str:
                    parts = m_str.split(':')
                    minutes = int(parts[0]) + int(parts[1]) / 60
                else:
                    try: minutes = float(m_str)
                    except: minutes = 0
            
            plus_minus = 0
            if pm_idx is not None and pm_idx < len(stats):
                try: plus_minus = int(stats[pm_idx])
                except: plus_minus = 0
            
            pts = 0
            if pts_idx is not None and pts_idx < len(stats):
                try: pts = int(stats[pts_idx])
                except: pts = 0
            
            starter = a.get('starter', False)
            did_not_play = a.get('didNotPlay', False)
            
            if not did_not_play:
                team_players.append({
                    'name': name,
                    'min': round(minutes, 1),
                    'pts': pts,
                    'pm': plus_minus,
                    'starter': starter,
                })
        
        result[team] = team_players
    
    return result

# ═════════════════════════════════════════════
# 贝叶斯权重更新
# ═════════════════════════════════════════════

def update_weight(impact, games, cum_pm, cum_min, new_pm, new_min, prior_strength=5):
    """
    更新单个球员权重。
    
    核心逻辑:
    - 新数据给出的 impact = 1.0 + (pm_per_48 / 100)
    - 用分钟加权 (games_tracked) 混合新旧数据
    - 前 K 场偏向先验 (手动赋值), 之后逐步信任数据
    """
    if new_min < 1:
        return impact, games, cum_pm, cum_min  # 几乎没上场，不更新
    
    new_cum_pm = cum_pm + new_pm
    new_cum_min = cum_min + new_min
    new_games = games + 1
    
    # 从比赛数据计算的 impact
    pm_per_48 = new_cum_pm / new_cum_min * 48
    data_impact = 1.0 + pm_per_48 / 100
    
    # 先验强度：前 K 场比赛偏向先验
    prior_weight = prior_strength / (new_games + prior_strength)
    data_weight = new_games / (new_games + prior_strength)
    
    final_impact = impact * prior_weight + data_impact * data_weight
    final_impact = max(0.96, min(1.06, final_impact))  # clamp
    
    return round(final_impact, 4), new_games, new_cum_pm, new_cum_min

# ═════════════════════════════════════════════
# 主流程
# ═════════════════════════════════════════════

def main():
    if len(sys.argv) < 2:
        print("用法: python3 calibrate_weights.py <game_id>")
        print("       python3 calibrate_weights.py --last")
        sys.exit(1)
    
    game_id = sys.argv[1]
    if game_id == '--last':
        # 自动检测最近已结束的比赛
        url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
        with urllib.request.urlopen(url, timeout=5) as r:
            sb = json.load(r)
        events = sb.get('events', [])
        if not events:
            print("  ❌ 无最近比赛")
            sys.exit(1)
        game_id = events[0]['id']
        print(f"  📌 最近比赛: {events[0].get('name', '??')} (ID: {game_id})")
    
    weights = load_weights()
    prior_k = weights.get('prior_strength', 5)
    players = weights['players']
    default_impact = weights['default_impact']
    
    print(f"\n{'='*50}")
    print(f"  赛后权重校准")
    print(f"  Game ID: {game_id}")
    print(f"{'='*50}\n")
    
    # 拉数据
    box = fetch_boxscore(game_id)
    
    if not box:
        print("  ❌ 未获取到 boxscore 数据")
        sys.exit(1)
    
    total_updated = 0
    new_players = 0
    
    for team, player_list in box.items():
        print(f"\n── {team} ──")
        for p in player_list:
            name = p['name']
            new_pm = p['pm']
            new_min = p['min']
            
            if name in players:
                old = players[name]
                new_impact, new_games, new_cum_pm, new_cum_min = update_weight(
                    old['impact'], old['games'], old['cum_pm'], old['cum_min'],
                    new_pm, new_min, prior_k
                )
                change = new_impact - old['impact']
                arrow = '↑' if change > 0 else ('↓' if change < 0 else '→')
                print(f"  {name:25s}  PM={new_pm:+3d}  MIN={new_min:5.1f}  "
                      f"{old['impact']:.4f}→{new_impact:.4f} {arrow} ({change:+5.4f})")
                players[name] = {
                    'impact': new_impact,
                    'games': new_games,
                    'cum_pm': new_cum_pm,
                    'cum_min': round(new_cum_min, 1),
                }
                total_updated += 1
            else:
                # 新球员，用数据初始化
                pm_per_48 = new_pm / new_min * 48 if new_min >= 1 else 0
                data_impact = 1.0 + pm_per_48 / 100
                data_impact = max(0.96, min(1.06, data_impact))
                print(f"  {name:25s}  PM={new_pm:+3d}  MIN={new_min:5.1f}  "
                      f"(新) {default_impact}→{data_impact:.4f} 🆕")
                players[name] = {
                    'impact': round(data_impact, 4),
                    'games': 1,
                    'cum_pm': new_pm,
                    'cum_min': new_min,
                }
                new_players += 1
    
    print(f"\n{'─'*50}")
    print(f"  更新: {total_updated} 人 | 新增: {new_players} 人")
    
    save_weights(weights)
    
    # 汇总最大变化
    print(f"\n📊 最大权重变化:")
    for name, p in sorted(players.items(), key=lambda x: abs(x[1]['impact'] - 1.0), reverse=True)[:5]:
        print(f"  {name:25s} → {p['impact']:.4f} ({p['games']}场, cum PM={p['cum_pm']:+d})")

if __name__ == '__main__':
    main()
