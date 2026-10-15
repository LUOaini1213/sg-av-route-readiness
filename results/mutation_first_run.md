# Mutation check, first run (2026-10-15)

The first run of `tools/mutation_check.py` failed: 26 of 29 mutants were killed and 3 survived.

| Mutant | Why it survived | Fix |
|---|---|---|
| `cut_segments`: short tail merged only if under a quarter of the target, not half | the only tail in the test (50 m) is under both limits | added a 100 m tail case |
| `route_turns`: road bends (no junction) counted as turns | no test had a bend away from a junction | added `test_bend_without_junction_is_not_a_turn` |
| `band_speed`: band 8's open top (999) left in the midpoint | equivalent mutant: band 8 is replaced by its fixed speed anyway, so the `< 900` filter was dead code | removed the dead line and the mutant |

The second run is in `mutation.json`.
