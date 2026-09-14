# Minimal Research continuation, within the existing 90-minute pool

The user requested shorter Research within 20 minutes. The preceding probe returned in 816.734 seconds but failed the assumption/evidence-status invariant even after its one repair. It produced no canonical Research artifact. That failed run and its 3 requests / 24,572 known and charged tokens are preserved in `s3-research-20m-v1`.

The second refinement uses `research-minimal-v2` / `grounded-generation-v9-minimal-research` for shared Research generation. It generates exactly three core findings and three claim objects, with `unsupported_claims=[]`; evidence gaps remain in the claims' explicit dispositions and the at-most-three human-review questions. The full canonical reader retains historical larger artifacts. Do not prune old claim lineages to force old artifacts into this fresh-generation profile.

The prompt asks for complete short sentences (finding target 120 characters, rationale 90, summary 180), leaving room below the unchanged hard limits. It explicitly distinguishes unvalidated demand/growth assumptions from facts. A hard field bound can still yield a semantically incomplete sentence; neither a natural provider stop nor schema validation proves writing quality.

Repair diagnostics now identify the actual wire path and observed/expected evidence status for an assumption/projection, with a valid status-combination example. They do not mutate model output, upgrade unsupported evidence, or change the canonical state rules. The previous two raw failures both diagnose exactly `$.g4.claims[0].evidence_status`: observed `unsupported`, required `assumption`.

The production Research parent retains a 1200-second deadline shared with Critic and conditional revision. Other roles, all 13 final sections, complete Finance outputs, strict source-anchor checks, model identity and CPU placement remain unchanged. Research physical caps stay 640 body / 2304 grounding, subject to lower global caps.

This continuation is **only a Research generation component**, with a lower **900-second** overall probe limit taken from the already-approved pool's remaining **998.578 seconds**, **31 requests**, and **384,511 charged tokens**. The pool has already consumed 5 requests / 115,489 charged tokens / 4401.422 seconds. All-history use before this continuation is separately 21 requests / 412,058 charged tokens / 14594.905 seconds. The original unknown reservation of 85,923 tokens remains charged. The runner verifies the hashed result chain back to the independent 90-minute authorization and does not reset any counter.

No Critic, semantic revision, complete D, Gemini, formal S5 matrix or next work package is started by this probe. A complete Research artifact, if produced, is a candidate requiring semantic evidence/quality review; source-anchor existence does not prove that a quotation supports a claim. The prior probe's misaligned citations and unsupported market assertions are preserved in its quality audit.

Final tests, actual model outcome and preservation checks will be recorded in `HANDOFF.md` and `validation/`. Current source, before versions and all 3,622 old data/report files are frozen by hashes. Do not mix this prompt/profile with earlier formal experiment versions; re-freeze the S5 manifest before formal comparison.
