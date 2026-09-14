# Evaluation Code

This package contains the project's formal metric computation, resource sampling, audit, export, and statistical utilities. It is retained as code provenance for the evaluation framework referenced by the metric specification.

The executed product-level A/B experiments in this repository were dispatched and reduced through `tools/run_product_ab.py` and `tools/summarize_product_ab.py`. Modules in this package may support broader protocol configurations; their presence does not imply that every supported or previously designed condition was executed. The repository README and `experiments/product_ab/README.md` define the executed scope.

The copied Python modules are source files only. Interpreter caches, local environments, credentials, and machine-specific runtime state are excluded. `audit_current_prompts.py` resolves the repository root relative to its own location so that it does not depend on the original workstation path.
