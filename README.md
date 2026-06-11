# 🏀 NBA Monte Carlo Live Predictor

**实时胜率预测 | 贝叶斯收缩蒙特卡洛 + Logistic 回归双引擎**

A live NBA win probability model that compares three independent engines: **Monte Carlo simulation with Bayesian shrinkage**, **calibrated logistic regression**, and **ESPN's official win probability** (when available).

---

## Method

### Engine 1: Monte Carlo with Bayesian Shrinkage 🎲

Simulates the remainder of a game play-by-play, using Bayesian shrinkage to blend current-game shooting data with season baselines:

```python
def bayesian_shrinkage(game_makes, game_attempts, season_pct, k=10):
    """Shrink observed shooting toward season average"""
    return min((game_makes + k * season_pct) / (game_attempts + k), 0.85)
```

For each remaining possession, the model probabilistically decides 2PT / 3PT / FT based on league-average rates, then uses the shrunk percentages to determine scoring. **100,000 simulations** per run.

### Engine 2: Logistic Regression 📐

A continuous-time win probability model using calibrated parameters from public NBA research (Inpredictable, 538). The log-odds function:

```
z = β₀ + home_boost + β₁ × score_diff × seconds_remaining + β₂ × score_diff × √(seconds_remaining)
p = 1 / (1 + e^(-z))
```

Parameters `β₁ = 0.000455` (score × time interaction) and `β₂ = 0.0040` (score × √time) are calibrated from historical NBA play-by-play data.

### Engine 3: ESPN Official 🏢

Fetches ESPN's proprietary win probability via their public summary API for direct comparison.

---

## Files

| File | Description |
|------|-------------|
| `models/nba_live_v5.py` | Triple-engine live predictor (watch mode available) |
| `models/nba_monte_carlo.py` | Standalone Bayesian MC simulator |
| `models/nba_g5_predict.py` | Pre-game prediction with series-specific adjustments |

## Usage

```bash
# Live game prediction (detects current game)
python3 models/nba_live_v5.py

# Watch mode (refreshes every 15s)
python3 models/nba_live_v5.py --watch

# Monte Carlo only (50,000 sims)
python3 models/nba_live_v5.py --mc

# Pre-game prediction with series context
python3 models/nba_g5_predict.py
```

### Dependencies

- `numpy` (≥1.23)
- Python 3.9+

No API key required — data sourced from ESPN's public endpoints.

---

## Design Philosophy

- **Honest uncertainty**: MC naturally produces asymmetric, non-normal distributions — no Gaussian approximation
- **Conservatism**: Bayesian shrinkage prevents overreacting to small-sample hot/cold streaks
- **Triangulation**: Three independent engines with different assumptions reveal when the answer is robust vs. fragile

---

## Series Test: 2026 NBA Finals (Knicks vs Spurs)

| Game | Result | MC | Logistic | ESPN | Winner |
|------|--------|----|----------|------|--------|
| G4 | Knicks 107-106 | ✓ Closely tracked | ✗ Failed (uncalibrated) | ✓ | MC + ESPN |

The model was validated in real-time during the 2026 NBA Finals, correctly capturing the Knicks' comeback from 24 down.

---

*Part of a broader research interest in computational social science and structural modeling. See also: [Behavioral Digital Twins](https://ssrn.com/abstract=6686418), [Value Contamination in LLMs](https://ssrn.com/abstract=6876161).*
