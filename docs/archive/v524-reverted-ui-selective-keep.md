# Pre Icarus v5.24 reverted UI selective keep

This build uses the Pre Icarus v5.22 UI as the base and keeps only three v5.24 enhancements:

1. Persisted theme selector: Neon Cockpit / Clean Dark via `localStorage`.
2. Turn-by-turn Decision Reasoning feed, populated from action history plus `/api/career/decision-trace/latest?limit=160`.
3. Career History aptitude labels mapped with the actual scale: `1=G, 2=F, 3=E, 4=D, 5=C, 6=B, 7=A, 8=S`.

No v5.24 Build & Config modal, Run Feed re-layout, duplicate-history removal, TP Restore copy cleanup, or Sync button removal was retained.
