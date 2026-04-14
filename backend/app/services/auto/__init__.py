"""Auto URL pipeline (Phase 2 auto-accumulation MVP).

See ``docs/superpowers/specs/2026-04-11-auto-url-pipeline-design.md`` for the
full design.

The package is intentionally narrow: each module owns one concern and the
``AutoPipelineRunner`` orchestrates them. Nothing in this package is allowed
to silently swallow failures or substitute heuristic data for missing LLM
output — every error must propagate to the audit log and the URL state
machine so the user can act on it the next morning.
"""
