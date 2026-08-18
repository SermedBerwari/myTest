# Raw-Data Release Policy

The canonical validator remains strict and returns a warning status when player snapshot counts differ. For a newly introduced bootstrap player, unequal historical snapshot depth is expected and is not itself a data-integrity failure.

Phase 24 accepts this condition only when all of the following hold: the canonical validator reports zero errors; there are no missing or extra player directories; all latest bootstrap players have valid per-player snapshots; and every remaining warning is exactly `snapshot_coverage`.

Run the policy gate with:

```powershell
py scripts/evaluation/validate_release_data_policy.py --season 2026-27
```

This wrapper does not suppress errors or arbitrary warnings; it makes the exception explicit and auditable.
