# Phase 16 — Historical Manager Simulation Report

## Executive summary

Phase 16 evaluates transfer and squad-management strategies under a chronological walk-forward simulation across 2023–24, 2024–25, and 2025–26. Each season contributes 37 evaluated gameweeks. Decisions use pre-gameweek predictions; actual historical points are used only to score the resulting squad and manager decisions.

The strongest validated strategy was **Ridge xP**, producing **5,705 net points after hits** across the three seasons. The strongest secondary variants were **ML + minutes** at 5,162 net points and **rolling average** at 5,166 net points. The main operational conclusion is that ranking quality and transfer economics matter more than transfer volume: Ridge xP recorded no hits in the validated artifact while still leading every evaluated season.

> Net points after hits = total actual points − 4 × hit count.

## 1. Scope and methodology

The simulation compares transparent manager strategies under identical squad legality, budget, position, club, bank, transfer, starting-XI, captain, vice-captain, bench, and scoring rules. It is intended as a historical decision-system evaluation, not as a guarantee of future FPL performance.

| Dimension | Definition |
|---|---|
| Evaluation seasons | 2023–24, 2024–25, 2025–26 |
| Evaluated gameweeks | 37 per season |
| Decision timing | Chronological walk-forward; future target-gameweek outcomes are excluded |
| Actual scoring | Historical target points, captain doubling, and bench accounting |
| Transfer economy | Free transfers, affordability, club/position rules, and hit penalties |
| Net-point rule | `total_points − 4 × hits` |
| Persisted decisions | Captain ID, vice-captain ID, weekly points, captain points, and vice-captain points |
| Validation | Phase 16 comparison, full-loop, and model-variant validators |

## 2. Strategies

| Strategy | Decision signal |
|---|---|
| No transfer | Holds the initial squad and provides a conservative baseline. |
| Previous GW | Uses the previous gameweek signal. |
| Rolling average | Uses a rolling historical expected-points signal. |
| Historical-average xP | Uses a leakage-safe expanding historical player average. |
| Ridge xP | Uses a chronological Ridge model trained only on prior information. |
| ML + minutes | Adjusts the ML point signal by predicted expected minutes. |
| ML + availability | Adjusts ML xP using the recent appearance-rate availability proxy. |
| Simple highest xP | Uses the highest-xP benchmark without optional transfer activity. |
| AI manager | Uses the full manager decision layer with transfer economy. |

## 3. Three-season aggregate results

| Strategy | Total net points | Mean season net points | Total transfers | Total hits | Hit points lost |
|---|---:|---:|---:|---:|---:|
| Ridge xP | 5,705 | 1,901.7 | 95 | 0 | 0 |
| ML + minutes | 5,162 | 1,720.7 | 91 | 1 | 4 |
| Rolling average | 5,166 | 1,722.0 | 122 | 39 | 156 |
| ML + availability | 4,762 | 1,587.3 | 109 | 14 | 56 |
| Simple highest xP | 4,903 | 1,634.3 | 0 | 0 | 0 |
| Previous GW | 4,764 | 1,588.0 | 180 | 89 | 356 |
| AI manager | 4,653 | 1,551.0 | 100 | 15 | 60 |
| No transfer | 3,759 | 1,253.0 | 0 | 0 | 0 |

## 4. Season-by-season net results

| Strategy | 2023–24 | 2024–25 | 2025–26 |
|---|---:|---:|---:|
| Ridge xP | 1,812 | 2,007 | 1,886 |
| ML + minutes | 1,679 | 1,739 | 1,744 |
| Rolling average | 1,645 | 1,861 | 1,660 |
| ML + availability | 1,718 | 1,403 | 1,641 |
| Previous GW | 1,475 | 1,705 | 1,584 |
| Simple highest xP | 1,656 | 1,675 | 1,572 |
| AI manager | 1,609 | 1,513 | 1,531 |
| No transfer | 1,210 | 1,224 | 1,325 |

Ridge xP ranks first in each evaluated season. ML + minutes is the most stable secondary variant, while ML + availability shows the largest season-to-season sensitivity.

## 5. Detailed season records

### 2023–24

| Strategy | Total points | Net after hits | Transfers | Hits | Hit loss | Captain points | Vice-captain points |
|---|---:|---:|---:|---:|---:|---:|---:|
| Ridge xP | 1,812 | 1,812 | 23 | 0 | 0 | 332 | 210 |
| ML + minutes | 1,683 | 1,679 | 24 | 1 | 4 | 363 | 124 |
| ML + availability | 1,730 | 1,718 | 26 | 3 | 12 | 369 | 188 |
| Rolling average | 1,685 | 1,645 | 33 | 10 | 40 | 385 | 184 |
| Previous GW | 1,583 | 1,475 | 56 | 27 | 108 | 374 | 144 |
| No transfer | 1,210 | 1,210 | 0 | 0 | 0 | 266 | 158 |

### 2024–25

| Strategy | Total points | Net after hits | Transfers | Hits | Hit loss | Captain points | Vice-captain points |
|---|---:|---:|---:|---:|---:|---:|---:|
| Ridge xP | 2,007 | 2,007 | 36 | 0 | 0 | 507 | 254 |
| ML + minutes | 1,739 | 1,739 | 36 | 0 | 0 | 398 | 180 |
| ML + availability | 1,431 | 1,403 | 43 | 7 | 28 | 291 | 121 |
| Rolling average | 1,909 | 1,861 | 38 | 12 | 48 | 390 | 166 |
| Previous GW | 1,809 | 1,705 | 52 | 26 | 104 | 351 | 169 |
| No transfer | 1,224 | 1,224 | 0 | 0 | 0 | 228 | 150 |

### 2025–26

| Strategy | Total points | Net after hits | Transfers | Hits | Hit loss | Captain points | Vice-captain points |
|---|---:|---:|---:|---:|---:|---:|---:|
| Ridge xP | 1,886 | 1,886 | 36 | 0 | 0 | 457 | 194 |
| ML + minutes | 1,744 | 1,744 | 31 | 0 | 0 | 422 | 168 |
| ML + availability | 1,657 | 1,641 | 40 | 4 | 16 | 329 | 179 |
| Rolling average | 1,728 | 1,660 | 51 | 17 | 68 | 468 | 129 |
| Previous GW | 1,728 | 1,584 | 72 | 36 | 144 | 483 | 135 |
| No transfer | 1,325 | 1,325 | 0 | 0 | 0 | 402 | 118 |
