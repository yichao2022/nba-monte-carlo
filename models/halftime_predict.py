#!/usr/bin/env python3
"""半场比分预测 — Q2 2:34, SA 38-32 NY"""
import numpy as np

sa = {'fg': 14/39, '3p': 6/20, 'ft': 4/4, 'fg_a': 39, '3p_a': 20, 'score': 38}
ny = {'fg': 11/38, '3p': 7/16, 'ft': 3/6, 'fg_a': 38, '3p_a': 16, 'score': 32}

sa_seas = {'fg': 0.483, '3p': 0.359, 'ft': 0.787, 'pace': 100.2}
ny_seas = {'fg': 0.478, '3p': 0.373, 'ft': 0.792, 'pace': 97.5}
sa_ser = {'fg': 144/337, '3p': 51/149, 'ft': 81/104}
ny_ser = {'fg': 152/349, '3p': 54/143, 'ft': 70/89}

def shrink(pct, series_pct, seas_pct, att, k=8):
    blended = (pct * att + k * series_pct) / (att + k)
    blended = (blended * 4 + 8 * seas_pct) / (4 + 8)
    return min(blended, 0.85)

sa_adj = {
    'fg': shrink(sa['fg'], sa_ser['fg'], sa_seas['fg'], sa['fg_a']),
    '3p': shrink(sa['3p'], sa_ser['3p'], sa_seas['3p'], sa['3p_a']),
    'ft': shrink(sa['ft'], sa_ser['ft'], sa_seas['ft'], sa['fg_a']),
}
ny_adj = {
    'fg': shrink(ny['fg'], ny_ser['fg'], ny_seas['fg'], ny['fg_a']),
    '3p': shrink(ny['3p'], ny_ser['3p'], ny_seas['3p'], ny['3p_a']),
    'ft': shrink(ny['ft'], ny_ser['ft'], ny_seas['ft'], ny['fg_a']),
}

remaining_poss = 5  # ~2.5 min
rng = np.random.default_rng(42)
sims = 50000
half_sa, half_ny = [], []

for _ in range(sims):
    sc_sa, sc_ny = 0, 0
    for _ in range(remaining_poss):
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
    half_sa.append(sa['score'] + sc_sa)
    half_ny.append(ny['score'] + sc_ny)

avg_sa = np.mean(half_sa); avg_ny = np.mean(half_ny)
sa_lead = sum(1 for s, n in zip(half_sa, half_ny) if s > n) / sims * 100

print("=" * 50)
print("  半场比分预测 (Q2 2:34)")
print("=" * 50)
print(f"  当前: SA 38 — 32 NY")
print(f"  剩余回合: ~5")
print(f"\n  📊 半场预测: SA {avg_sa:.0f} — {avg_ny:.0f} NY")
print(f"  马刺半场领先概率: {sa_lead:.1f}%")
print(f"  {'= '*25}")
print(f"  实时胜率: ESPN 85.9% | MC 62.5%")
print(f"  {'= '*25}")
print(f"  ⚠️ 尼克斯三分 7/16 (43.8%) — 这是他们活着的理由")
print(f"  ESPN ↑ 85.9% vs MC ↓ 62.5% — 模型严重分歧")
