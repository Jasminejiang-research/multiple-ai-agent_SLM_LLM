# Planned experiment status

Independent unit: case_id; n=2. These tables preserve all eight planned slots and failure/missing states.

Approved LLM-only branch: report B−A and C−B only. C−D is unavailable because both D rows are fixed as not_run_preflight_no_go; no successful subset or imputation is substituted.

Quality and claim results require human review. Empty values are not zero. Synthetic runs cannot support scientific conclusions.

| Metric | Comparison | Pairs | Mean difference | Median | IQR | Improved / tied / worsened |

|---|---|---:|---:|---:|---:|---|

| completion | B-A | 2 | 0.5 | 0.5 | 0.5 | 1 / 1 / 0 |

| completion | C-B | 2 | -1 | -1.0 | 0.0 | 0 / 0 / 2 |

| mvp30_material | B-A | 2 | 0.5 | 0.5 | 0.5 | 1 / 1 / 0 |

| mvp30_material | C-B | 2 | -1 | -1.0 | 0.0 | 0 / 0 / 2 |

| valid_plan60 | B-A | 2 | 0.5 | 0.5 | 0.5 | 1 / 1 / 0 |

| valid_plan60 | C-B | 2 | -1 | -1.0 | 0.0 | 0 / 0 / 2 |

| first_mvp30_material_seconds | B-A | 1 | 39.063 | 39.063 | 0.0 | 0 / 0 / 1 |

| first_mvp30_material_seconds | C-B | 0 | missing | missing | missing | 0 / 0 / 0 |

| first_contract | B-A | 2 | 0.333333 | 0.333333 | 0.5 | 1 / 0 / 1 |

| first_contract | C-B | 2 | -0.547619 | -0.547619 | 0.285714 | 0 / 0 / 2 |

| handoff | B-A | 0 | missing | missing | missing | 0 / 0 / 0 |

| handoff | C-B | 2 | -0.615873 | -0.615873 | 0.326984 | 0 / 0 / 2 |

| review_token_share | B-A | 0 | missing | missing | missing | missing / missing / missing |

| review_token_share | C-B | 2 | 0.076158 | 0.076158 | 0.188123 | missing / missing / missing |

| first_valid_plan_seconds | B-A | 1 | 42.953 | 42.953 | 0.0 | 0 / 0 / 1 |

| first_valid_plan_seconds | C-B | 0 | missing | missing | missing | 0 / 0 / 0 |

| request_count | B-A | 2 | 5 | 5.0 | 0.0 | 0 / 0 / 2 |

| request_count | C-B | 2 | 0 | 0.0 | 4.0 | 1 / 0 / 1 |

| total_tokens | B-A | 2 | 27809 | 27809.0 | 1473.0 | 0 / 0 / 2 |

| total_tokens | C-B | 2 | -11361 | -11361.0 | 16590.0 | 1 / 0 / 1 |

| transport_retry_count | B-A | 2 | 0 | 0.0 | 0.0 | 0 / 2 / 0 |

| transport_retry_count | C-B | 2 | 0 | 0.0 | 0.0 | 0 / 2 / 0 |

| peak_ram_bytes | B-A | 2 | 966113280 | 966113280.0 | 792819712.0 | 0 / 0 / 2 |

| peak_ram_bytes | C-B | 2 | -783341568 | -783341568.0 | 772057088.0 | 2 / 0 / 0 |

| peak_vram_bytes | B-A | 2 | 0 | 0.0 | 0.0 | 0 / 2 / 0 |

| peak_vram_bytes | C-B | 2 | 0 | 0.0 | 0.0 | 0 / 2 / 0 |

| peak_pagefile_bytes | B-A | 2 | 0 | 0.0 | 0.0 | 0 / 2 / 0 |

| peak_pagefile_bytes | C-B | 2 | 987136 | 987136.0 | 987136.0 | 0 / 1 / 1 |

| academic_quality | B-A | 0 | missing | missing | missing | 0 / 0 / 0 |

| academic_quality | C-B | 0 | missing | missing | missing | 0 / 0 / 0 |

| claim_grounding | B-A | 0 | missing | missing | missing | 0 / 0 / 0 |

| claim_grounding | C-B | 0 | missing | missing | missing | 0 / 0 / 0 |

| assumption_transparency | B-A | 0 | missing | missing | missing | 0 / 0 / 0 |

| assumption_transparency | C-B | 0 | missing | missing | missing | 0 / 0 / 0 |

| high_impact_unsupported | B-A | 0 | missing | missing | missing | 0 / 0 / 0 |

| high_impact_unsupported | C-B | 0 | missing | missing | missing | 0 / 0 / 0 |



Proportions are computed within case first, then equal-weighted. Review-token share has no improvement direction.

Memory is local host sampled usage (cloud hardware unavailable); partial telemetry is marked. Provider totals include returned thinking; visible output is separate.

Vega-Lite specifications are offline artifacts for Streamlit. Standalone HTML previews require access to the renderer CDN.
