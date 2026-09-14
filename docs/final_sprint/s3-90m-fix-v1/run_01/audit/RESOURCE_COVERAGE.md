# Retrospective resource coverage correction

The original result.json is preserved unchanged. Its resource status `passed`
only means no observed sample triggered the previous RAM/pagefile conditions.
It does **not** certify continuous coverage: the maximum sample gap was
2423.437 seconds. Windows power events confirm Modern Standby, with three
reported sleep durations totalling 2989.447614 seconds (about 49m49s).

The run hit its shared 5400-second deadline during its only structure repair.
The controller reports failed/WallClockExceeded even though deadline_fired is
false (the client clock stopped first). 5405.172 seconds includes cleanup.
Full D was not started. No valid complete plan was generated. The known first
grounding response ended naturally and failed claim identity consistency, not
reference-array duplication. CPU throughput including standby is not a valid
estimate of continuously active inference throughput.
