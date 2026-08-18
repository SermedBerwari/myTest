# Phase 15 Weekly Automation Contract

Canonical command: `py scripts/run_weekly_canonical.py --season 2026-27 --gw 1 [--squad path]`. Required inputs are a valid 15-player squad configuration, the target season and gameweek, live availability/intelligence signals, the canonical feature dataset, and registered model artifacts.

The command executes input lineage, pipeline scoring, availability integration, squad optimization, manager recommendation, and output validation stages. It publishes `weekly_automation_summary_canonical.json` only after the output passes the exact-15-player and net-of-hit checks. `weekly_automation_output_manifest.json` records the run ID, timestamps, model version, feature version, input SHA-256 values, output SHA-256 value, stage statuses, and failure details when a stage fails.

The canonical pipeline was run twice for 2026-27 GW1. Both runs completed with `PASS` status and all three wrapper stages passed. The run ID changes per execution while the decision output remains governed by the same model and feature lineage.
