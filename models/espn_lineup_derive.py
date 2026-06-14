#!/usr/bin/env python3
"""
ESPN 阵容推导 — 从换人事件追踪场上5人
========================================
替代方案: 不依赖 athlete.active 字段, 通过替换人事件精确推导当前场上阵容。
移植自 nba-on-court (shufinskiy) 的核心算法, 适配 ESPN API 数据结构。
"""

import json, urllib.request

# ═════════════════════════════════════════════
# ESPN 数据获取
# ═════════════════════════════════════════════

def _fetch_summary(game_id='401859967'):
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={game_id}"
    with urllib.request.urlopen(url, timeout=5) as r:
        return json.load(r)

def _parse_team_id_map(d):
    """获取 球队ID → 缩写 映射"""
    m = {}
    for comp in d.get('header', {}).get('competitions', []):
        for c in comp.get('competitors', []):
            m[c['team']['id']] = c['team']['abbreviation']
    return m

def _parse_player_id_map(d):
    """获取 球员ID → 显示名 映射 (从 boxscore 拉)"""
    m = {}
    for team_data in d.get('boxscore', {}).get('players', []):
        stats_list = team_data.get('statistics', [])
        if not stats_list: continue
        for a in stats_list[0].get('athletes', []):
            ath = a.get('athlete', {})
            pid = ath.get('id')
            name = ath.get('displayName')
            if pid and name:
                m[pid] = name
    return m

# ═════════════════════════════════════════════
# 核心: 从替换人事件推导场上阵容
# ═════════════════════════════════════════════

def derive_lineup(game_id='401859967'):
    """
    通过跟踪替换人事件, 推导当前场上10人。
    
    返回: {team_abbr: {'on_court': [name1..name5], 'bench': [name6..]}}
    
    算法:
    1. 每节开始时, 初始化为该节首发5人 (从 boxscore.starter 获取)
    2. 按时间顺序处理每个 Substitution 事件
       - participant[0] = 上场球员
       - participant[1] = 下场球员
    3. 实时更新场上5人
    4. 所有不在场上的球员 → bench
    """
    d = _fetch_summary(game_id)
    team_ids = _parse_team_id_map(d)
    player_names = _parse_player_id_map(d)
    
    # 获取每队的首发5人 (从 boxscore)
    starters = {}  # {team_abbr: [player_id, ...]}
    bench_players = {}  # {team_abbr: [player_id, ...]}
    
    for team_data in d.get('boxscore', {}).get('players', []):
        team_info = team_data.get('team', {})
        tid = str(team_info.get('id', ''))
        abbr = team_ids.get(tid, '??')
        stats_list = team_data.get('statistics', [])
        if not stats_list: continue
        
        starters[abbr] = []
        bench_players[abbr] = []
        for a in stats_list[0].get('athletes', []):
            if a.get('didNotPlay'): continue
            pid = a.get('athlete', {}).get('id')
            if pid:
                if a.get('starter'):
                    starters[abbr].append(pid)
                else:
                    bench_players[abbr].append(pid)
    
    # 初始化场上阵容: 每队5个首发
    on_court = {}  # {team_abbr: set of player_id}
    for team in starters:
        on_court[team] = set(starters[team][:5])
    
    # 获取所有替换人事件, 按 quarter → sequenceNumber 排序
    plays = d.get('plays', [])
    subs = []
    for p in plays:
        if p.get('type', {}).get('text') == 'Substitution':
            period = p.get('period', {}).get('number', 1)
            seq = int(p.get('sequenceNumber', 0))
            clock_str = p.get('clock', {}).get('displayValue', '12:00')
            parts = clock_str.split(':')
            clock_sec = int(parts[0]) * 60 + int(parts[1]) if len(parts) == 2 else 0
            
            # participant[0] = 上场的, participant[1] = 下场的
            participants = p.get('participants', [])
            if len(participants) >= 2:
                p_in = str(participants[0].get('athlete', {}).get('id'))
                p_out = str(participants[1].get('athlete', {}).get('id'))
                
                # 找到球队
                t_id = str(p.get('team', {}).get('id', ''))
                team = team_ids.get(t_id, '??')
                
                subs.append({
                    'period': period,
                    'clock': clock_sec,
                    'clock_str': clock_str,
                    'seq': seq,
                    'team': team,
                    'in': p_in,
                    'out': p_out,
                })
    
    # 按 节 → 时间降序 → seq 升序排序
    # 注意: clock 是倒数的 (12:00 → 0:00), 所以 clock 降序 = 时间正序
    subs.sort(key=lambda x: (x['period'], -x['clock'], x['seq']))
    
    # 处理所有换人事件
    for sub in subs:
        team = sub['team']
        if team not in on_court:
            continue
        
        p_in = sub['in']
        p_out = sub['out']
        
        # 验证: p_out 应该在场上
        if p_out not in on_court[team]:
            # 如果 p_out 不在场上, 尝试找在场上的人替换
            # (可能是 multiple substitution 导致的偏移)
            # 保守处理: 换下场上任意一人
            if len(on_court[team]) == 5 and p_in not in on_court[team]:
                # 找个最可能被换下的: 替补席上的人
                # 简单方法: 移除第一个不在 starting 5 里的
                candidates = [p for p in on_court[team] if p not in starters.get(team, [])]
                if candidates:
                    p_out = candidates[0]
                else:
                    # 所有首发都在场上, 换下第一个
                    p_out = list(on_court[team])[0]
            
        if p_in not in on_court[team]:
            on_court[team].discard(p_out)
            on_court[team].add(p_in)
    
    # 转换为名称和分类
    result = {}
    for team in on_court:
        on_court_names = []
        bench_names = []
        all_players = set(starters.get(team, []) + bench_players.get(team, []))
        
        for pid in all_players:
            name = player_names.get(pid, f'ID:{pid}')
            if pid in on_court[team]:
                on_court_names.append(name)
            else:
                bench_names.append(name)
        
        result[team] = {
            'on_court': on_court_names[:5],
            'bench': bench_names[:5],
        }
    
    return result

# ═════════════════════════════════════════════
# 对比测试: 新旧方法
# ═════════════════════════════════════════════

def old_active_method(game_id='401859967'):
    """原来的方法: 依赖 athlete.active 字段"""
    d = _fetch_summary(game_id)
    team_ids = _parse_team_id_map(d)
    player_names = _parse_player_id_map(d)
    
    result = {}
    for team_data in d.get('boxscore', {}).get('players', []):
        team_info = team_data.get('team', {})
        tid = str(team_info.get('id', ''))
        abbr = team_ids.get(tid, '??')
        stats_list = team_data.get('statistics', [])
        if not stats_list: continue
        
        athletes = stats_list[0].get('athletes', [])
        on_court = []
        bench = []
        for a in athletes:
            if a.get('didNotPlay'): continue
            name = a.get('athlete', {}).get('displayName', '?')
            if a.get('active'):
                on_court.append(name)
            else:
                bench.append(name)
        result[abbr] = {'on_court': on_court[:5], 'bench': bench[:5]}
    
    return result

if __name__ == '__main__':
    import sys
    gid = sys.argv[1] if len(sys.argv) > 1 else '401859967'
    
    print(f'阵容推导对比 — Game {gid}')
    print('=' * 60)
    
    new = derive_lineup(gid)
    old = old_active_method(gid)
    
    for team in sorted(new.keys()):
        print(f'\n── {team} ──')
        print(f'  🆕 换人追踪:')
        for name in new[team]['on_court']:
            print(f'    🔥 {name}')
        for name in new[team]['bench']:
            print(f'    🪑 {name}')
        
        print(f'  🗑  old active:')
        for name in old[team]['on_court']:
            print(f'    🔥 {name}')
        for name in old[team]['bench']:
            print(f'    🪑 {name}')
        
        # 对比
        new_set = set(new[team]['on_court'])
        old_set = set(old[team]['on_court'])
        diff = new_set - old_set
        if diff:
            print(f'  ⚠️  差异: 新方法有但旧方法没有 → {diff}')
        diff2 = old_set - new_set
        if diff2:
            print(f'  ⚠️  差异: 旧方法有新方法没有 → {diff2}')
        if not diff and not diff2:
            print(f'  ✅ 一致')
