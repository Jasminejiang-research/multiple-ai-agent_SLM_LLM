"""Synthetic-only conversion to the stage wire formats; never used by providers."""
from copy import deepcopy
from workflow.two_stage_generation import project_body, _at


def synthetic_stage_payload(schema, canonical_data):
    stage = getattr(schema, "__generation_stage__", None)
    canonical = getattr(schema, "__canonical_schema__", schema)
    canonical_data = {key:deepcopy(canonical_data[key]) for key in canonical.model_fields if key in canonical_data}
    if stage == "body":
        return project_body(canonical, canonical_data)
    if stage != "grounding":
        return canonical_data
    plan = schema.__selection_plan__
    result = {}
    for group, info in plan.groups.items():
        path = info["path"]
        parent = _at(canonical_data, path[:-1])
        annotation_schema = schema.model_fields[group].annotation
        value = {key:deepcopy(parent[key]) for key in annotation_schema.model_fields if key != "claims"}
        value["claims"] = []
        for claim in parent.get(path[-1], []):
            selection = deepcopy(claim)
            anchor = selection.pop("content_anchor")
            selection["body_span_id"] = next(k for k in info["body_span_ids"] if plan.body_spans[k]["text"] == anchor)
            selection["evidence_span_ids"] = [next(k for k,v in plan.evidence_spans.items() if v == a)
                                                for a in selection.pop("source_anchors")]
            selection.pop("source_ids")
            value["claims"].append(selection)
        result[group] = value
    return result
