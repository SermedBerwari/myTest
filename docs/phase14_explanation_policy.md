# Phase 14 Explanation Policy

The mathematical decision layer is authoritative. The explanation layer receives structured facts and returns narrative fields only; it must not change expected points, ranks, transfers, captaincy, budget, squad membership, or net-of-hit arithmetic.

The explanation contract preserves warnings and uncertainty verbatim, identifies the evidence source, and rejects malformed decisions such as a captain outside the starting XI, mismatched transfer counts, or inconsistent net-of-hit arithmetic. It does not invent statistics and does not produce new FPL recommendations.

Natural-language wording is derived only from the supplied structured facts. If the decision layer recommends no transfer, the explanation states that no transfer is recommended; if the net gain is positive, the explanation reports the supplied net gain after hits.
