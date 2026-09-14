"""Offline saved-response runtime wiring; these are not experimental API calls."""
import pytest

from evaluation.s5_llm_only import run_config
from schemas.compact_wire import Finance8Wire
from workflow.compact_protocol import GEMINI_8192_FINANCE_CAPACITY_CONFIG_VERSION, evidence_catalog
from workflow.llm_client import StructuredOutputValidationError
from workflow.review_events import EventJournal
from workflow.review_runtime import BoundedClient, PhysicalResponse
from test_s5_finance_partition import load_saved


@pytest.mark.parametrize("old_config", [False, True])
def test_saved_finance_runtime_repairs_only_current_configuration(tmp_path, old_config):
    context, _, raw = load_saved()
    class SavedResponseProvider:
        provider = "gemini"
        model_exact_id = "gemini-2.5-flash"
        calls = 0
        def invoke(self, request):
            self.calls += 1
            return PhysicalResponse(raw, usage_raw={"synthetic": True},
                prompt_tokens=10, output_tokens=10, total_tokens=20)
    config = run_config("B", "smoke")
    if old_config:
        config = config.model_copy(update={"config_version": GEMINI_8192_FINANCE_CAPACITY_CONFIG_VERSION})
    provider = SavedResponseProvider()
    journal = EventJournal(tmp_path / "replay", "offline-replay")
    client = BoundedClient(provider, config, journal)
    client.begin_node("finance")
    def invoke():
        with client.attempt_scope(logical_task_id="finance.replay", role="finance",
                task_purpose="generate", purpose="generate", batch_number=None,
                schema_sha256="0" * 64, packet_sha256=context.packet_sha256):
            return client.generate_structured_once("offline replay", Finance8Wire,
                repair_evidence_catalog=evidence_catalog(context.packet),
                repair_financial_ids=set(context.finance.value_ids))
    if old_config:
        with pytest.raises(StructuredOutputValidationError):
            invoke()
    else:
        output = invoke()
        assert [len(note.claims) for note in output.economics] == [8, 2]
        call = [event["payload"] for event in journal.events if event["kind"] == "call"][-1]
        operations = [change["op"] for change in call["mechanical_repair_diff"]]
        assert operations.count("discard_invalid_source_recency_score") == 19
        assert operations.count("partition_existing_finance_note_claims") == 1
        assert call["raw_output"] == raw
    assert provider.calls == 1
