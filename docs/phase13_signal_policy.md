# Phase 13 Signal Policy

The canonical signal normalizer is `scripts/decision/intelligence_signals.py`. It accepts only signals timestamped at or before the decision deadline and rejects stale signals older than the configured freshness window. When several sources disagree, status severity is resolved by priority: suspension, injury, doubtful, available, then unknown. The normalized record retains signal counts, source counts, and a contradiction flag.

The normalized `availability` field flows into the Phase 10 decision layer. Available players receive an availability factor of 1.0, doubtful players receive 0.5, and injured, suspended, out, or unknown players receive 0.0. Fixture and xP calculations are not rewritten by news text; intelligence only changes the explicit availability adjustment and ranking eligibility.

The normalized availability also flows into the Phase 12 manager engine. Unknown, doubtful, injured, suspended, out, and unavailable players cannot be current-squad or transfer-in candidates. Consequently, external intelligence can restrict a decision or reduce its score, but cannot invent expected points or override the mathematical optimizer.

Return-from-injury signals are represented by a later `fit` or `available` signal, subject to the same deadline and freshness checks. The record remains auditable because the selected status, signal priority, source count, signal count, and contradiction flag are retained.
