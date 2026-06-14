#!/usr/bin/env python3
"""半场比分预测 — Q2 模拟"""
import numpy as np

# === Q1 Actuals ===
sa_q1 = {'fg': 9/21, '3p': 3/11, 'ft': 2/2, 'fg_a': 21, '3p_a': 11}
ny_q1 = {'fg': 4/22, '3p': 3/9,  'ft': 2/4, 'fg_a': 22, '3p_a': 9}
sa_score_q1, ny_score_q1 = 23, 13

# === Season baselines ===
sa_seas = {'fg': 0.483, '3p': 0.359, 'ft': 0.787, 'ortg': 119.8, 'pace': 100.2}
ny_seas = {'fg': 0.478, '3p': 0.373, 'ft': 0.792, 'ortg': 116.5, 'pace': 97.5}

# === Series baselines ===
sa_ser = {'fg': 144/337, '3p': 51/149, 'ft': 81/104}
ny_ser = {'fg': 152/349, '3p': 54/143, 'ft': 70/89}

def shrink(q1_pct, series_pct, seas_pct, q1_att, k=8):
    """Three-level shrinkage: Q1 → series → season"""
    blended = (q1_pct * q1_att + k * series_pct) / (q1_att + k)
    blended = (blended * 4 + 8 * seas_pct) / (4 + 8)
    return min(blended, 0.85)

sa_adj = {
    'fg': shrink(sa_q1['fg'], sa_ser['fg'], sa_seas['fg'], sa_q1['fg_a']),
    '3p': shrink(sa_q1['3p'], sa_ser['3p'], sa_seas['3p'], sa_q1['3p_a']),
    'ft': shrink(sa_q1['ft'], sa_ser['ft'], sa_seas['ft'], sa_q1['fg_a']),
}
ny_adj = {
    'fg': shrink(ny_q1['fg'], ny_ser['fg'], ny_seas['fg'], ny_q1['fg_a']),
    '3p': shrink(ny_q1['3p'], ny_ser['3p'], ny_seas['3p'], ny_q1['3p_a']),
    'ft': shrink(ny_q1['ft'], ny_ser['ft'], ny_seas['ft'], ny_q1['fg_a']),
}

q2_poss = int((sa_seas['pace'] + ny_seas['pace']) / 2 / 4)

rng = np.random.default_rng(42)
sims = 50000
halftime_sa = []
halftime_ny = []

for _ in range(sims):
    sc_sa, sc_ny = 0, 0
    for _ in range(q2_poss):
        r = rng.random()
        if r < 0.20:
            sc_sa += (rng.random() < sa_adj['ft'] * 1.035) + (rng.random() < sa_adj['ft'] * 1.035)
        elif r < 0.58:
            sc_sa += 3 if rng.random() < sa_adj['3p'] * 1.035 else 0
        else:
            sc_sa += 2 if rng.random() < sa_adj['fg'] * 1.035 else 0
        
        r2 = rng.random()
        if r2 < 0.20:
            sc_ny += (rng.random() < ny_adj['ft']) + (rng.random() < ny_adj['ft'])
        elif r2 < 0.58:
            sc_ny += 3 if rng.random() < ny_adj['3p'] else 0
        else:
            sc_ny += 2 if rng.random() < ny_adj['fg'] else 0
    
    halftime_sa.append(sa_score_q1 + sc_sa)
    halftime_ny.append(ny_score_q1 + sc_ny)

avg_sa = np.mean(halftime_sa)
avg_ny = np.mean(halftime_ny)
std_sa = np.std(halftime_sa)
std_ny = np.std(halftime_ny)

sa_lead = sum(1 for s, n in zip(halftime_sa, halftime_ny) if s > n) / sims * 100
ny_lead = sum(1 for s, n in zip(halftime_sa, halftime_ny) if n > s) / sims * 100

print("=" * 50)
print("  半场比分预测 — Q2 模拟 (50,000次)")
print("=" * 50)
print(f"  Q1结束: SA {sa_score_q1} — {ny_score_q1} NY")
print(f"  Q2预计回合: ~{q2_poss}")
print()
print(f"  📊 半场预测:")
print(f"  SA {avg_sa:.0f} — {avg_ny:.0f} NY")
print(f"  范围: SA {avg_sa-std_sa:.0f}-{avg_sa+std_sa:.0f} | NY {avg_ny-std_ny:.0f}-{avg_ny+std_ny:.0f}")
print(f"  马刺半场领先概率: {sa_lead:.1f}%")
print(f"  尼克斯半场反超概率: {ny_lead:.1f}%")
print()
sa_q2 = avg_sa - sa_score_q1
ny_q2 = avg_ny - ny_score_q1
print(f"  📈 Q2预计得分:")
print(f"  SA: ~{sa_q2:.0f}分 (Q1: 23)")
print(f"  NY: ~{ny_q2:.0f}分 (Q1: 13)")
print()
print(f"  🔑 关键: 尼克斯Q1 FG 4/22 (18%), 几乎不可能更差")
print(f"  Q2大概率反弹, 但马刺主场+领先心态占优")
