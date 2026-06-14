#!/usr/bin/env python3
"""简单轮询 wrapper — 每30秒跑一次预测, 不刷屏, stdout即时输出"""
import subprocess, sys, time
while True:
    result = subprocess.run(
        [sys.executable, 'models/nba_live_v5.py'],
        capture_output=True, text=True, timeout=60,
        cwd='/Users/cary/nba-monte-carlo'
    )
    out = result.stdout
    # 提取关键行
    lines = [l for l in out.split('\n') if any(k in l for k in
        ['Quarter', 'Final', '终分', 'Logistic', 'MC', 'ESPN', '模型对比', '比赛已结束'])]
    ts = time.strftime('%H:%M:%S')
    print(f'[{ts}]')
    for l in lines: print(l)
    print(flush=True)
    if '比赛已结束' in out or ('Final' in out and '1st' not in out and '2nd' not in out):
        print(f'[{time.strftime("%H:%M:%S")}] 🏁 比赛结束')
        break
    time.sleep(30)
