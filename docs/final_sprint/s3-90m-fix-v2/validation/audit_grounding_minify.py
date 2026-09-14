"""Read-only reconstruction of JSON formatting cost from one saved real response.

No provider calls; writes only new audit outputs beside this script by default.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

from tokenizers import Tokenizer


DEFAULT_REPO = Path('C:/Users/JasmineJiang/Projects/multiple-ai-agent_SLM_LLM')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f'Duplicate raw JSON key: {key}')
        value[key] = item
    return value


def walk(value, path=()):
    yield path, value
    if isinstance(value, dict):
        for key, item in value.items():
            yield from walk(item, path + (key,))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from walk(item, path + (index,))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=DEFAULT_REPO)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    run = args.repo / 'docs/final_sprint/s3-90m-fix-v1/run_01'
    paths = dict(
        raw_response=run / 'audit/02_research_generate.raw.txt',
        service_usage=run / 'audit/02_research_generate.usage.json',
        event_log=run / 'probe/research_probe/events.jsonl',
        tokenizer=args.repo / 'docs/final_sprint/s3-v1/setup/tokenizer.json',
        tokenizer_provenance=args.repo / 'docs/final_sprint/s3-v1/setup/tokenizer_provenance.json',
    )
    fingerprints = {key: dict(path=str(path.resolve()), sha256=digest(path), bytes=path.stat().st_size)
                    for key, path in paths.items()}
    raw = paths['raw_response'].read_text(encoding='utf-8')
    data = json.loads(raw, object_pairs_hook=unique_object)
    usage = json.loads(paths['service_usage'].read_text(encoding='utf-8'))
    events = [json.loads(line) for line in paths['event_log'].read_text(encoding='utf-8').splitlines()]
    provenance = json.loads(paths['tokenizer_provenance'].read_text(encoding='utf-8-sig'))
    assert 'g1' in data and usage['done'] is True and usage['done_reason'] == 'stop'
    compact = json.dumps(data, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    assert json.loads(compact, object_pairs_hook=unique_object) == data
    tokenizer = Tokenizer.from_file(str(paths['tokenizer']))
    tokens = lambda text: len(tokenizer.encode(text, add_special_tokens=False).ids)
    before, after = tokens(raw), tokens(compact)
    service_output = usage['eval_count']
    decode_seconds = usage['eval_duration'] / 1e9
    decode_rate = service_output / decode_seconds
    origin_events = []
    for event in events:
        matches = [list(path) for path, value in walk(event['payload'])
                   if isinstance(value, str) and value == raw]
        if matches:
            origin_events.append(dict(event_id=event['event_id'], kind=event['kind'],
                occurred_at_utc=event['occurred_at_utc'], exact_text_paths=matches))
    assert origin_events, 'Archived response must match an exact string in the source event log'
    assert all(digest(paths[key]) == item['sha256'] for key, item in fingerprints.items()), 'Input changed during audit'
    result = dict(
        audit_version='saved-grounding-json-format-v1', created_at_utc=datetime.now(timezone.utc).isoformat(),
        case_id='ai_education', logical_task_id='research.v1', generation_stage='grounding',
        model_calls=0, source_files=fingerprints, exact_response_events=origin_events,
        tokenizer_provenance=provenance,
        reproduction=dict(executable=sys.executable, script=str(Path(__file__).resolve()),
            script_sha256=digest(Path(__file__)),
            argv=['-B', str(Path(__file__).resolve()), '--repo', str(args.repo.resolve()), '--output', str(args.output.resolve())]),
        service_measurement=dict(prompt_eval_count=usage['prompt_eval_count'], output_tokens=service_output,
            finish_reason=usage['done_reason'], total_seconds=usage['total_duration']/1e9,
            prefill_seconds=usage['prompt_eval_duration']/1e9, decode_seconds=decode_seconds,
            generation_tokens_per_second=decode_rate, decode_fraction=usage['eval_duration']/usage['total_duration']),
        offline_comparison=dict(raw_characters=len(raw), compact_characters=len(compact),
            raw_reencoded_tokens=before, compact_reencoded_tokens=after,
            token_difference=before-after, fraction_of_raw_reencoded_tokens=(before-after)/before,
            service_minus_raw_reencoded_tokens=service_output-before,
            json_values_equal=True, duplicate_raw_keys=False,
            annotation_groups=len(data), claim_occurrences=sum(len(group['claims']) for group in data.values()),
            compact_utf8_sha256=hashlib.sha256(compact.encode('utf-8')).hexdigest()),
        hypothetical_projection=dict(saved_decode_seconds_if_generation_rate_unchanged=(before-after)/decode_rate,
            actual_new_request_measured=False),
        limitations=[
            '6000 versus 6055 is offline re-encoding versus service-reported generation usage, not two conflicting service measurements.',
            'The 55-token difference is not attributed to EOS, special tokens, or other causes without direct evidence.',
            'Only JSON formatting changes. Every parsed field, string, metadata value, claim and reference remains unchanged.',
            'The saved response failed canonical claim-identity validation. JSON equivalence does not make it a valid plan.',
            'The time projection holds the measured decode rate constant; it is not actual model time saved, a latency guarantee, or proof of a full plan within 90 minutes.',
            'Schema format bytes are not counted as input tokens. No provider call or historical artifact mutation is performed.',
        ],
    )
    args.output.mkdir(parents=True, exist_ok=True)
    json_path = args.output / 'grounding_minify_audit.json'
    report_path = args.output / 'GROUNDING_MINIFY_AUDIT.md'
    for path in (json_path, report_path):
        if path.exists():
            raise FileExistsError(f'Refusing to replace audit output: {path}')
    with json_path.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    report = f'''# Saved grounding JSON formatting audit

This is a read-only offline comparison of the first Research grounding response from `s3-90m-fix-v1/run_01`. No model was called, and the historical response remains unchanged.

| Metric | Original response | Equivalent compact JSON |
|---|---:|---:|
| Characters | {len(raw):,} | {len(compact):,} |
| Saved official tokenizer, no special tokens | {before:,} | {after:,} |

The service separately reported **{service_output:,} generated tokens**, with {decode_seconds:.3f} seconds decoding ({decode_rate:.3f} tokens/second). Offline re-encoding gives {before:,}; the {service_output-before}-token difference is **unattributed**. It is not assumed to be EOS or special tokens.

Removing only JSON formatting whitespace reduces offline tokens by **{before-after:,} ({(before-after)/before:.2%})**. All JSON values, {sum(len(group['claims']) for group in data.values())} claim occurrences, metadata, references and strings remain equal. Duplicate raw object keys are rejected before comparison. The original response still failed claim-identity validation; this experiment does not repair it.

At the first request's unchanged decode rate, this reduction would correspond to approximately **{(before-after)/decode_rate:.1f} seconds**. This is a hypothetical projection, not measured savings or proof of a complete D plan within 90 minutes.

Source response, usage, event-log and tokenizer/provenance paths and SHA-256 values, exact source event IDs, metric definitions and the full reproduction command are in [grounding_minify_audit.json](grounding_minify_audit.json). The script refuses to overwrite its audit outputs; reproduce into a fresh directory:

```powershell
& '{sys.executable}' -B '{Path(__file__).resolve()}' --repo '{args.repo.resolve()}' --output '<fresh-audit-directory>'
```
'''
    with report_path.open('x', encoding='utf-8') as stream:
        stream.write(report)
    print(json.dumps(dict(report=str(report_path), json=str(json_path), json_sha256=digest(json_path),
        offline_comparison=result['offline_comparison'], hypothetical_projection=result['hypothetical_projection']), indent=2))


if __name__ == '__main__':
    main()
