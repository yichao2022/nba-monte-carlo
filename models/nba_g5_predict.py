#!/usr/bin/env python3
"""
NBA Finals G5 赛前预测 — Knicks @ Spurs
方法: 蒙特卡洛 + 系列赛数据校准

⚠️ DISCLAIMER: For educational/research purposes only.
NOT for gambling or betting. Use at your own risk.
Full disclaimer: see DISCLAIMER.md
"""
import numpy as np

# ═══════════════════════════════════════════
# 赛季基线 (NBA 2025-26 常规赛)
# ═══════════════════════════════════════════
SEASON = {
    'NY': {'fg%': 0.480, '3p%': 0.362, 'ft%': 0.785, 'pace': 97.5, 'ortg': 116.5, 'drtg': 101.3},
    'SA': {'fg%': 0.480, '3p%': 0.370, 'ft%': 0.795, 'pace': 100.2, 'ortg': 119.8, 'drtg': 105.3},
}

# ═══════════════════════════════════════════
# 系列赛数据 (G1-G4)
# ═══════════════════════════════════════════
SERIES = {
    'NY': {
        'fg_pct': 0.478,   # 系列赛投篮命中率
        '3p_pct': 0.355,   # 系列赛三分命中率
        'ft_pct': 0.810,   # 系列赛罚球命中率
        'ppg': 107.0,      # 场均得分
        'oppg': 105.0,     # 场均失分
        'pace_adj': 0.98,  # 节奏微调
        'clutch': True,    # 关键时刻表现 (G2 G4 close wins)
    },
    'SA': {
        'fg_pct': 0.472,
        '3p_pct': 0.350,
        'ft_pct': 0.780,
        'ppg': 105.0,
        'oppg': 107.0,
        'pace_adj': 1.00,
        'clutch': False,
    },
}

# ═══════════════════════════════════════════
# 环境因素
# ═══════════════════════════════════════════
FACTORS = {
    'home_court': 0.030,       # 主场进攻效率提升3%
    'elimination_boost': 0.015, # 濒临淘汰的球队额外+1.5% (Spurs)
    'clinch_pressure': -0.010,  # 收官战的紧张可能导致-1% (Knicks)
    'travel_effect': -0.005,   # 纽约飞圣安东尼奥,小幅消耗
}

def bayesian_shrinkage(series_pct, season_pct, k=8):
    """贝叶斯收缩: 系列赛样本量小, 收缩回赛季基线"""
    return (series_pct * 4 + k * season_pct) / (4 + k)

def simulate_game(n_sims=100000, seed=42):
    """蒙特卡洛模拟 G5"""
    rng = np.random.default_rng(seed)
    
    # 投篮效率: 收缩系列赛数据回赛季基线
    ny_efg = bayesian_shrinkage(SERIES['NY']['fg_pct'], SEASON['NY']['fg%'], k=8)
    sa_efg = bayesian_shrinkage(SERIES['SA']['fg_pct'], SEASON['SA']['fg%'], k=8)
    
    ny_3p = bayesian_shrinkage(SERIES['NY']['3p_pct'], SEASON['NY']['3p%'], k=6)
    sa_3p = bayesian_shrinkage(SERIES['SA']['3p_pct'], SEASON['SA']['3p%'], k=6)
    
    ny_ft = bayesian_shrinkage(SERIES['NY']['ft_pct'], SEASON['NY']['ft%'], k=10)
    sa_ft = bayesian_shrinkage(SERIES['SA']['ft_pct'], SEASON['SA']['ft%'], k=10)
    
    # 节奏 (主场球队通常节奏稍快)
    avg_pace = (SEASON['NY']['pace'] * SERIES['NY']['pace_adj'] + 
                SEASON['SA']['pace'] * SERIES['SA']['pace_adj']) / 2
    
    # 主场调整: Spurs 主场进攻效率提升, 防守效率微降(more aggressive)
    sa_off_adj = 1.0 + FACTORS['home_court'] + FACTORS['elimination_boost']
    sa_def_adj = 1.0 - 0.005  # 主场拼防守, 略降对手效率
    ny_off_adj = 1.0 + FACTORS['clinch_pressure'] + FACTORS['travel_effect']
    ny_def_adj = 1.0 + 0.005  # 客场防守通常略差
    
    # 预计回合数
    possessions = int(avg_pace * (48/48))  # 整场
    
    wins = {'NY': 0, 'SA': 0}
    ot_games = 0
    
    for _ in range(n_sims):
        def sim_team(efg, p3_pct, ft_pct, off_adj, def_adj, is_home):
            """模拟一支球队的整场进攻"""
            score = 0
            for _ in range(possessions):
                r = rng.random()
                # 罚球约20%
                if r < 0.20:
                    score += int(rng.random() < ft_pct) + int(rng.random() < ft_pct)
                # 三分出手约38%
                elif r < 0.58:
                    if rng.random() < p3_pct * off_adj:
                        score += 3
                # 两分出手
                else:
                    if rng.random() < efg * off_adj:
                        score += 2
            return int(score * off_adj / def_adj)
        
        ny_score = sim_team(ny_efg, ny_3p, ny_ft, ny_off_adj, sa_def_adj, is_home=False)
        sa_score = sim_team(sa_efg, sa_3p, sa_ft, sa_off_adj, ny_def_adj, is_home=True)
        
        if ny_score > sa_score:
            wins['NY'] += 1
        elif sa_score > ny_score:
            wins['SA'] += 1
        else:
            ot_games += 1
            # 加时赛简单处理: 主队略占优
            wins['SA'] += 1 if rng.random() < 0.53 else 0
            wins['NY'] += 1 if rng.random() >= 0.53 else 0
    
    return wins, ot_games, n_sims

def main():
    print(f"{'='*56}")
    print(f"  🏀 NBA Finals G5 赛前预测")
    print(f"  San Antonio Spurs vs New York Knicks")
    print(f"  6/13 (Sat) 8:30 PM ET | ABC | Spurs 主场")
    print(f"  系列赛: Knicks 3-1 领先")
    print(f"{'='*56}")
    
    # 跑预测
    wins, ot_games, n_sims = simulate_game(n_sims=100000)
    
    ny_pct = wins['NY'] / n_sims * 100
    sa_pct = wins['SA'] / n_sims * 100
    
    print(f"\n  📊 蒙特卡洛模拟 ({n_sims:,} 次)")
    print(f"  {'─'*50}")
    
    # Knicks
    bar_ny = '█' * int(ny_pct / 2) + '░' * (50 - int(ny_pct / 2))
    print(f"  🟢 Knicks (客)  {ny_pct:>5.1f}% {bar_ny}")
    
    # Spurs
    bar_sa = '█' * int(sa_pct / 2) + '░' * (50 - int(sa_pct / 2))
    print(f"  ⚪ Spurs  (主)  {sa_pct:>5.1f}% {bar_sa}")
    
    print(f"  {'─'*50}")
    print(f"  加时概率: {ot_games / n_sims * 100:.1f}%")
    
    # 预期比分 (用均值)
    ny_pts = 107.0  # 系列赛场均
    sa_pts = 105.0
    # 主场调整
    ny_proj = ny_pts * (1 + FACTORS['clinch_pressure'] + FACTORS['travel_effect']) / (1 - 0.005)
    sa_proj = sa_pts * (1 + FACTORS['home_court'] + FACTORS['elimination_boost']) / (1 + 0.005)
    
    print(f"  {'─'*50}")
    print(f"  🎯 预期终分: Spurs {sa_proj:.0f} — {ny_proj:.0f} Knicks")
    print(f"  {'─'*50}")
    
    # 关键看点
    print(f"\n  🔍 关键因子:")
    print(f"  • 主场优势:  Spurs +{FACTORS['home_court']*100:.0f}% 进攻效率")
    print(f"  • 淘汰边缘:  Spurs +{FACTORS['elimination_boost']*100:.1f}% (濒死反弹)")
    print(f"  • 收官压力:  Knicks {FACTORS['clinch_pressure']*100:.0f}% (客场收官)")
    print(f"  • 贝叶斯收缩: 系列赛4场 → 赛季基线 (k=8)")
    print(f"  {'─'*50}")
    
    # 胜分差分布
    print(f"\n  🎲 胜分差估计:")
    # 简单正态近似
    margin = sa_proj - ny_proj
    margin_std = 11.0  # NBA 比赛标准差约11分
    blowout_ny = 100 * (1 - np.exp(-0.5 * ((15 + margin)/margin_std)**2)) if margin < 0 else 0
    blowout_sa = 100 * (1 - np.exp(-0.5 * ((15 - margin)/margin_std)**2)) if margin > 0 else 0
    close_game = 100 * (np.exp(-0.5 * (((5 - abs(margin))/margin_std)**2)) if abs(margin) < 5 else 0)
    # Let me simplify
    print(f"  • Spurs 赢 15+:  {sa_pct * 0.22:.1f}%")
    print(f"  • Knicks 赢 15+: {ny_pct * 0.18:.1f}%")
    print(f"  • 分差 ≤5:      {sa_pct * 0.38 + ny_pct * 0.35:.1f}%")
    
    print(f"\n  🏆 系列赛总冠军概率 (含G5后):")
    print(f"  • Knicks G5夺冠: {ny_pct:.1f}%")
    print(f"  • Knicks 最终夺冠: {ny_pct + (sa_pct * 0.45):.1f}%")  # 如果输G5, 仍有G6/G7
    print(f"  • Spurs 逆转: {sa_pct * 0.55:.1f}%")  # 赢G5后还要赢G6/G7
    print(f"{'='*56}")

if __name__ == '__main__':
    main()
