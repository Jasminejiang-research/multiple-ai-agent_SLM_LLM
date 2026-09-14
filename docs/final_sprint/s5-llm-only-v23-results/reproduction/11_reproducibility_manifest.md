# S5 reproducibility capture

frozen_configuration_captured

Actual source bytes include uncommitted changes, tests, Modelfile, prompts, schemas, and config files. The JSON manifest records hashes, Git status, runtime, inputs and pending gates. This command grants no budget, input approval, configuration freeze or execution authorization.

Verify: python -B -m evaluation.s5 verify-snapshot --snapshot <this directory>
