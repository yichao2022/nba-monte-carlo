# 🏀 NBA Finals 2026 — Model Validation Results

> Real-time tracking and post-game analysis of the Hermes MC v4/v5/v6 prediction engines during the 2026 NBA Finals (Knicks vs Spurs).

---

## Series Summary

| Game | Date | Result | Series | Key Story |
|------|------|--------|--------|-----------|
| G1 | Jun 5 | NY 105-104 | NY 1-0 | Knicks steal opener |
| G2 | Jun ? | ? | ? | ? |
| G3 | Jun 8 | SA 115-111 | SA 1-0* | *series tied 1-1? |
| G4 | Jun 10 | **NY 107-106** | NY 3-1 | Largest comeback in Finals history (29 pts) |
| G5 | **Jun 13** | **NY 94-90** 🏆 | **NY 4-1** | Brunson 45 pts, Knicks end 53-year drought |

---

## Game 4 — Knicks 107-106 Spurs

> *Real-time tracking of three models during the historic 29-point comeback.*

**Tracking Data:** Tracked live from Q2 7:25 through final buzzer.

![G4 Three-Model Comparison](../results/nba_g4_three_model_comparison.png)

| Time | Score | MC | Logistic | ESPN | Event |
|------|-------|----|----------|------|-------|
| Q1 ? | SA 37-13 | — | — | — | Spurs lead by 24 |
| Q2 7:25 | SA 45-32 | 87.0% | — | 94.0% | — |
| Q2 0:00 | SA 56-43 | 88.4% | — | 96.6% | — |
| Q3 7:28 | SA 67-52 | 91.6% | — | 96.8% | — |
| Q3 2:51 | SA 76-59 | 93.8% | — | 96.5% | — |
| Q3 End | SA 80-64 | 92.0% | — | 95.7% | — |
| Q4 11:22 | SA 80-64 | 92.0% | — | 96.6% | — |
| Q4 8:23 | SA 82-69 | 91.3% | — | 96.3% | — |
| Q4 5:15 | SA 89-79 | 89.2% | — | 95.5% | — |
| Q4 3:32 | SA 91-84 | 82.3% | — | 91.8% | NY on a run |
| Q4 2:21 | SA 94-89 | 70.5% | — | 80.9% | NY keeps coming |
| Q4 1:12 | SA 96-93 | 52.0% | — | 61.7% | Down to 3! |
| Q4 0:20 | SA 101-97 | 76.0% | — | 53.8% | Spurs answer |
| Q4 0:01 | **NY 107-106** | — | — | — | Anunoby tip-in |

**Model Verdict:**
- **MC ✓** — Closely tracked ESPN throughout, correctly declined from 92%→52% as Knicks closed
- **Logistic ✗** — Failed in Q1-Q3 (uncalibrated for early game), became usable in Q4 with `--q4only`
- **ESPN ✓** — Most accurate, but still surprised by the tip-in finish

---

## Game 5 — Knicks 94-90 Spurs 🏆

> *Championship-clinching game. Lineup-enhanced v6 model tested live. Full session documented in [session log].*

### Three-Model Tracking

![G5 Win Probability](../g5_win_prob_chart.png)

| Time | Score | v5 | v6 | ESPN | Logistic | Event |
|------|-------|----|----|------|----------|-------|
| Half | 42-37 | 65.6% | 63.3% | 71.0% | — | — |
| Q3 9:42 | 47-41 | 76.7% | 74.8% | 78.4% | — | Even start to Q3 |
| Q3 6:27 | 55-50 | 75.4% | 72.3% | 74.6% | — | NY run (no Wemby/Fox) → v6 flags bench lineup |
| Q3 5:18 | **62-53** | 87.8% | **88.6%** 🚀 | 83.7% | — | Wemby+Fox back → v6 highest! |
| Q3 2:31 | 69-55 | 97.8% | 97.3% | 95.8% | — | Peak |
| Q3 End | 72-65 | 85.8% | 85.2% | 83.0% | — | NY closes quarter on run |
| Q4 8:51 | 80-71 | 91.8% | 91.6% | 90.3% | 95.3% | Logistic joins |
| Q4 7:14 | 83-77 | 85.4% | 84.1% | 86.4% | 84.4% | NY starters win lineup battle (1.016 vs 1.000) |
| Q4 5:30 | **83-79** | 78.5% | 77.1% | 79.9% | 71.0% | Spurs scoreless for 2min |
| Q4 4:59 | 83-81 | 64.0% | 62.9% | 64.2% | 60.2% | Down to 2! |
| Q4 4:12 | 85-83 | 63.7% | 63.1% | 68.0% | 58.9% | Spurs answer |
| Q4 3:40 | 85-84 | 57.0% | 56.3% | 51.6% | 54.1% | 1-point game |
| Q4 **1:53** | **85-88** | **10.7%** | **10.4%** | **35.9%** | 43.0% | Knicks take lead! |
| **Final** | **90-94** | 0.0% | 0.0% | 6.7% | 50.0% | 🏆 Knicks win! |

### Quarter-by-Quarter: Prediction vs Reality

![G5 Quarter Scores](../g5_quarter_scores.png)

| Quarter | SA Actual | NY Actual | SA Predicted | NY Predicted | Error |
|---------|-----------|-----------|--------------|--------------|-------|
| Q1 | **23** | **13** | — | — | No prediction |
| Q2 | **19** | **24** | — | — | No prediction |
| Half | 42 | 37 | 44 | 37 | SA +2 off |
| Q3 | **30** | **28** | **27** | **27** | ✅ Close (SA +3, NY +1) |
| Q4 | **18** | **29** | **28** | **27** | ❌ Massive miss (SA -10) |
| **Total** | **90** | **94** | **100** | **92** | — |

### Lineup Factor Validation (v6)

| Test Case | v5 | v6 | Verdict |
|-----------|----|----|---------|
| Q3 6:27 — SA bench (no Wemby/Fox, coef 0.988) | 75.4% | 72.3% (↓3.1%) | ✅ Correct — bench unit was getting outplayed |
| Q3 5:18 — SA stars return (coef 1.010) | 87.8% | 88.6% (↑0.8%) | ✅ Correct — first time v6 > ESPN |
| Q4 7:14 — NY full starters (coef 1.016) vs SA no Fox (1.000) | 85.4% | 84.1% (↓1.3%) | ✅ Correct — NY's best lineup dominating |
| Final stretch — NY lockdown defense | 0.0% | 0.0% | ⚖️ No difference — too much time/score signal |

**Summary:** v6 lineup factor works in the right direction at the right amplitude (~3% swing). The model correctly identifies lineup strength/weakness transitions. Its main limitation: it cannot account for cold shooting or superstar explosions (Brunson 45 pts).

### Model Performance Comparison

| Metric | MC v5 | MC v6 (lineup) | Logistic | ESPN |
|--------|-------|----------------|----------|------|
| Final SA win% | 0.0% | 0.0% | 50.0% | 6.7% |
| Peak SA win% | 97.8% | 97.3% | 95.3% | 95.8% |
| Final score (SA) | — | — | 90 | — |
| Final score (NY) | — | — | 94 | — |

---

## Key Takeaways

1. **MC engine** is the most reliable workhorse — tracks ESPN closely, Bayesian shrinkage works.
2. **Logistic engine** should only be used in Q4 (`--q4only`). Its parameters are calibrated for late-game contexts.
3. **Lineup factor (v6)** adds real but marginal signal. Direction always correct, amplitude ~3% appropriate.
4. **Post-game calibration**: Compare predicted vs actual after each game to identify systematic biases (e.g., consistently underestimating comeback teams).
5. **No model predicts superstar explosions** — Brunson's 45-point game is the kind of outlier that models cannot and should not capture.

---

*Generated by Hermes Agent — https://github.com/yichao2022/nba-monte-carlo*
