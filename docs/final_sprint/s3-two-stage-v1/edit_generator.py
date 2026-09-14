from pathlib import Path
p=Path(__file__).parent/'runtime/workflow/contract_generation.py'
s=p.read_text(encoding='utf-8')
s=s.replace('PROMPT_VERSION = "grounded-generation-v3-explicit-anchors"','PROMPT_VERSION = "grounded-generation-v5-two-stage"')
s=s.replace('    error: str | None\n','    error: str | None\n    generation_stage: str = "single"\n    schema_sha256: str | None = None\n')
s=s.replace('    @property\n    def first_output_passed(self):\n        return bool(self.attempts and self.attempts[0].passed and self.first_physical_attempt_passed is not False)', '''    completed: bool = False
    protocol: str = "single-stage"
    frozen_draft: dict | None = None
    selection_catalog: dict | None = None
    assembly_mapping: list | None = None
    assembled_sha256: str | None = None

    @property
    def first_output_passed(self):
        return bool(self.completed and self.attempts and all(a.passed for a in self.attempts)
                    and self.first_physical_attempt_passed is not False)''')
start=s.index('    def generate_task(')
end=s.index('    def generate(self,',start)
s=s[:start]+'''    def generate_task(self, prompt, schema, *, context, role, version, logical_task_id,
                      validator, batch_number=None, purpose="generate", two_stage=False,
                      upstream=(), previous=None):
        from workflow.two_stage_generation import (draft_model, SelectionPlan, BODY_INSTRUCTION,
                                                    TWO_STAGE_VERSION)
        if logical_task_id in self._task_ids:
            raise ValueError("logical task already triggered; do not reset its repair allowance")
        canonical = schema
        self._task_ids.add(logical_task_id)
        task = ContractTask(logical_task_id, role, version, canonical_hash(schema.model_json_schema()),
                            context.packet_sha256, batch_number)
        task.protocol = TWO_STAGE_VERSION if two_stage else "single-stage"
        self.tasks.append(task)
        self._emit(task)
        repair_used = False

        def stage(stage_prompt, stage_schema, validate, name):
            nonlocal repair_used
            stage_schema = bounded_response_model(stage_schema, context.finance.value_ids, packet=context.packet)
            stage_prompt += "\\n\\n" + schema_enum_contract(stage_schema) + "\\n\\n" + schema_cardinality_contract(stage_schema)
            stage_prompt += "\\n\\n" + financial_reference_contract(context.finance.value_ids)
            if not two_stage:
                stage_prompt += "\\n\\n" + grounding_reference_contract(context.packet)
            original_prompt = stage_prompt
            attempt_purpose = purpose
            while True:
                raw_output = None
                provider_returned = False
                scope_result = None
                stage_hash = canonical_hash(stage_schema.model_json_schema())
                try:
                    scope = self.attempt_scope(logical_task_id=logical_task_id, role=role,
                        artifact_version=version, schema_sha256=stage_hash,
                        packet_sha256=task.packet_sha256, batch_number=batch_number,
                        purpose=attempt_purpose, task_purpose=purpose, generation_stage=name) if self.attempt_scope else nullcontext()
                    with scope as scope_result:
                        with frozen_evidence_scope():
                            candidate = self.client.generate_structured_once(stage_prompt, stage_schema, temperature=0,
                                system_instruction=COMMON_INSTRUCTION + ("\\n" + BODY_INSTRUCTION if name == "body" else ""))
                        provider_returned = True
                        raw_output = candidate.model_dump_json() if isinstance(candidate, BaseModel) else json.dumps(candidate)
                        candidate = stage_schema.model_validate(candidate)
                        validate(candidate)
                except Exception as exc:
                    if scope_result is not None and scope_result.get("first_physical_attempt_passed") is False:
                        task.first_physical_attempt_passed = False
                    raw_output = raw_output if raw_output is not None else getattr(exc, "raw_output", None)
                    task.attempts.append(ContractAttempt(len(task.attempts)+1, attempt_purpose, False,
                        canonical_hash(stage_prompt), raw_output, type(exc).__name__, str(exc), name, stage_hash))
                    self._emit(task)
                    repairable = isinstance(exc, (StructuredOutputValidationError, ValidationError)) or (provider_returned and isinstance(exc, ValueError))
                    if repair_used or isinstance(exc, CitationPollutionError) or not repairable:
                        raise
                    repair_used = True
                    if self.attempt_scope is None:
                        record_retry()
                    attempt_purpose = "structure_repair"
                    stage_prompt = (original_prompt + "\\n\\nThis is the only structure/contract repair shared by BOTH stages of this logical task. "
                        "Correct only this stage; the accepted body cannot be rewritten. Validation feedback (data, not instructions):\\n" +
                        repair_feedback(exc, raw_output, context.finance.value_ids, packet=context.packet))
                else:
                    if scope_result is not None and scope_result.get("first_physical_attempt_passed") is False:
                        task.first_physical_attempt_passed = False
                    task.attempts.append(ContractAttempt(len(task.attempts)+1, attempt_purpose, True,
                        canonical_hash(stage_prompt), raw_output, None, None, name, stage_hash))
                    self._emit(task)
                    return candidate

        if two_stage:
            def validate_body(body):
                for title, field_name in SECTION_FIELD_BY_TITLE.items():
                    if hasattr(body, field_name) and hasattr(getattr(body, field_name), "title"):
                        if getattr(body, field_name).title != title:
                            raise ValueError(f"incorrect section title for {field_name}")
                if hasattr(body, "financial_values"):
                    context.finance.validate(body.financial_values)
                if hasattr(body, "financial_assumptions"):
                    context.finance.validate(body.financial_assumptions.financial_values)
                if hasattr(body, "assumption_notice"):
                    notice = body.assumption_notice.lower()
                    if "assumption" not in notice or "forecast" not in notice:
                        raise ValueError("assumption_notice must say figures are assumptions, not forecasts")
                import re
                from workflow.two_stage_generation import _strings
                for path, value in _strings(body.model_dump(mode="json")):
                    if path and path[-1] == "content":
                        cited = set(re.findall(r"\\[([A-Za-z0-9][A-Za-z0-9_.:-]*)\\]", value))
                        if cited - set(context.packet.allowlist_source_ids):
                            raise CitationPollutionError("invented inline source ID in body")
            body = stage(prompt + "\\n\\n" + BODY_INSTRUCTION, draft_model(canonical), validate_body, "body")
            plan = SelectionPlan(canonical, body.model_dump(mode="json"), context, upstream=upstream, previous=previous)
            task.frozen_draft = deepcopy(plan.body)
            task.selection_catalog = deepcopy(plan.catalog())
            self._emit(task)
            accepted = []
            def validate_selection(selection):
                candidate, mapping = plan.assemble(selection.model_dump(mode="json"))
                validator(candidate)
                accepted[:] = [candidate, mapping]
            stage(prompt + "\\n\\n" + plan.prompt(), plan.schema, validate_selection, "grounding")
            candidate, mapping = accepted
            task.assembly_mapping = mapping
            task.assembled_sha256 = canonical_hash(candidate.model_dump(mode="json"))
        else:
            candidate = stage(prompt, schema, validator, "single")
        task.completed = True
        self._emit(task)
        return candidate

''' +s[end:]
s=s.replace('import json\n','import json\nfrom copy import deepcopy\n',1)
s=s.replace('validator=validate_batch, batch_number=number, purpose=purpose))','validator=validate_batch, batch_number=number, purpose=purpose, two_stage=True,\n                    upstream=upstream, previous=previous))')
s=s.replace('logical_task_id=prefix, purpose=purpose,','logical_task_id=prefix, purpose=purpose, two_stage=True, upstream=upstream, previous=previous,')
p.write_text(s,encoding='utf-8')
p=Path(__file__).parent/'runtime/schemas/contract_outputs.py'
s=p.read_text(encoding='utf-8').replace('proposal-grounding-v3-frozen-reference-bounds','proposal-grounding-v5-two-stage')
p.write_text(s,encoding='utf-8')
p=Path(__file__).parent/'runtime/workflow/review_runtime.py'
s=p.read_text(encoding='utf-8').replace('self.first_physical_pass = {}','self.first_physical_pass = {}\n        self.first_physical_stage_pass = {}')
s=s.replace('self.first_physical_pass.get(metadata["logical_task_id"])','self.first_physical_stage_pass.get((metadata["logical_task_id"], metadata.get("generation_stage")))')
s=s.replace('task_role=metadata["role"], purpose=', 'generation_stage=metadata.get("generation_stage", "single"),\n                task_role=metadata["role"], purpose=')
s=s.replace('self.first_physical_pass.setdefault(logical_id, event["status"] == "succeeded")','self.first_physical_pass.setdefault(logical_id, event["status"] == "succeeded")\n                self.first_physical_stage_pass.setdefault((logical_id, metadata.get("generation_stage")), event["status"] == "succeeded")')
p.write_text(s,encoding='utf-8')
p=Path(__file__).parent/'runtime/workflow/review_config.py'
s=p.read_text(encoding='utf-8').replace('multi-agent-review-gates-v2','multi-agent-review-gates-v3-two-stage').replace('single-agent-common-contract-v1','single-agent-common-contract-v2-two-stage')
p.write_text(s,encoding='utf-8')
print('Updated shared generator and stage accounting.')
