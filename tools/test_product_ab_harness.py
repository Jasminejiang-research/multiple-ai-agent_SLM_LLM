"""Offline tests for the transport-only comparison harness; no provider clients."""
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from contextlib import redirect_stdout
import io
import pytest

from run_product_ab import (Audit, BudgetAdmissionError, execute, read, request_bounds,
    admission_violations, arm_token_limit, selected_arms)


def test_selected_arms_supports_frozen_b_only_runs():
    assert selected_arms(['B']) == ['B']
    assert selected_arms() == ['A','B']
    with pytest.raises(ValueError):
        selected_arms(['B','B'])


def test_a_executor_keeps_plan_and_audit_as_distinct_files():
    source=Path(__file__).with_name('run_product_ab.py').read_text(encoding='utf-8')
    assert "arm_dir/'proposal.md'" in source
    assert "arm_dir/'audit_report.md'" in source
    assert "app.proposal_audit_to_markdown(proposal)" in source


def test_executor_records_product_audit_path_separately():
    source=Path(__file__).with_name('run_product_ab.py').read_text(encoding='utf-8')
    assert "audit_path=state.get('audit_path')" in source


class Config:
    def model_dump(self, **kwargs):
        return {'max_output_tokens': 16384}


class Response:
    usage_metadata = SimpleNamespace(prompt_token_count=100, candidates_token_count=200,
                                      thoughts_token_count=300, total_token_count=600)

    def model_dump(self, **kwargs):
        return {'text': '{}', 'usage_metadata': vars(self.usage_metadata)}


class HarnessTests(unittest.TestCase):
    def test_v6_b_allowance_does_not_raise_a_allowance(self):
        limits={'llm_requests':28,'total_tokens':540000,'llm_cost_usd':0.8,
                'per_arm_total_tokens':240000,'arm_total_tokens':{'A':240000,'B':420000}}
        snapshot={'llm_requests':12,'total_tokens':191245,'llm_cost_usd':0.1826129,'arm_tokens':164854}
        bound={'total_bound':80805,'reserved_usd':0.1323759}
        assert admission_violations(snapshot,limits,bound,'B')==[]
        assert [v['metric'] for v in admission_violations(snapshot,limits,bound,'A')]==['arm_tokens']
        assert arm_token_limit(limits,'A')==240000

    def test_v6_b_still_respects_currency_and_combined_caps(self):
        limits={'llm_requests':28,'total_tokens':540000,'llm_cost_usd':0.8,
                'arm_total_tokens':{'A':240000,'B':420000}}
        snapshot={'llm_requests':12,'total_tokens':530000,'llm_cost_usd':0.79,'arm_tokens':164854}
        bound={'total_bound':80805,'reserved_usd':0.1323759}
        assert {v['metric'] for v in admission_violations(snapshot,limits,bound,'B')}=={'cost_usd','total_tokens'}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self.tmp.name)
        self.audit = Audit(self.directory, {'llm_requests': 3, 'total_tokens': 300000,
                                          'llm_cost_usd': 0.8, 'web_requests': 2})
        self.audit.arm = 'A'
        self.kwargs = dict(model='gemini-2.5-flash', contents='test', config=Config())
        self.quiet = redirect_stdout(io.StringIO())
        self.quiet.__enter__()

    def tearDown(self):
        self.quiet.__exit__(None,None,None)
        self.tmp.cleanup()

    def test_thinking_tokens_included(self):
        self.audit.generate(SimpleNamespace(generate_content=lambda **kw: Response()), **self.kwargs)
        self.assertAlmostEqual(self.audit.cost, (100*0.3+500*2.5)/1e6)
        self.assertEqual(self.audit.tokens, 600)
        self.assertEqual(self.audit.unresolved_reservation, 0)
        self.assertTrue((self.directory/'A/calls/001.response.json').exists())

    def test_no_dispatch_when_budget_insufficient(self):
        self.audit.limits['llm_cost_usd'] = 0.001
        with self.assertRaisesRegex(RuntimeError, 'before dispatch'):
            self.audit.generate(None, **self.kwargs)
        self.assertEqual(self.audit.requests, 0)

    def test_unknown_usage_blocks_further_dispatch(self):
        def fail(**kw):
            raise TimeoutError('test timeout')
        with self.assertRaises(TimeoutError):
            self.audit.generate(SimpleNamespace(generate_content=fail), **self.kwargs)
        self.assertTrue(self.audit.usage_incomplete)
        self.assertGreater(self.audit.unresolved_reservation, 0)
        with self.assertRaisesRegex(RuntimeError, 'Uncertain'):
            self.audit.generate(None, **self.kwargs)
        self.assertEqual(self.audit.requests, 1)

    def test_rejected_request_preserved_without_claiming_tokens(self):
        class Rejected(Exception):
            code = 400
        def fail(**kw):
            raise Rejected('invalid request')
        with self.assertRaises(Rejected):
            self.audit.generate(SimpleNamespace(generate_content=fail), **self.kwargs)
        self.assertFalse(self.audit.usage_incomplete)
        self.assertEqual(self.audit.tokens, 0)
        self.assertEqual(self.audit.requests, 1)
        self.assertTrue((self.directory/'A/calls/001.error.json').exists())

    def test_expired_deadline(self):
        self.audit.deadline = 0
        with self.assertRaisesRegex(RuntimeError, 'deadline'):
            self.audit.generate(None, **self.kwargs)
        self.assertEqual(self.audit.requests, 0)

    def test_request_count_gate(self):
        self.audit.requests = 3
        with self.assertRaisesRegex(RuntimeError, 'before dispatch'):
            self.audit.generate(None, **self.kwargs)

    def long_context(self):
        self.kwargs['contents'] = '德国宠物照护法律和商业假设' * 6500
        self.audit.tokens = 144164
        self.audit.cost = 0.1305584
        return SimpleNamespace(count_tokens=Mock(return_value=SimpleNamespace(total_tokens=35000)),
                               generate_content=Mock(return_value=Response()))

    def test_long_chinese_context_refines_bytes_without_raising_cap(self):
        delegate = self.long_context()
        initial = request_bounds(self.kwargs['contents'], Config().model_dump())
        self.assertGreater(self.audit.tokens+initial['total_bound'],300000)
        self.audit.generate(delegate, **self.kwargs)
        delegate.count_tokens.assert_called_once_with(model='gemini-2.5-flash',contents=self.kwargs['contents'])
        self.assertEqual(delegate.generate_content.call_count,1)
        self.assertEqual(self.audit.limits['total_tokens'],300000)
        self.assertEqual(self.audit.token_count_requests,1)

    def test_recorded_b_writer_request_replay(self):
        root = Path(__file__).resolve().parents[1]/'docs/comparisons/pet-trust-product-ab-20260911'
        if not (root/'B/calls/007.request.json').is_file():
            self.skipTest('historical pet-trust replay fixture is not part of the executed A/B repository scope')
        request = read(root/'B/calls/007.request.json')
        usage = read(root/'B/calls/007.response.json')['usage_metadata']
        self.audit.tokens, self.audit.cost = 144164, 0.1305584
        self.audit.limits.update(per_arm_total_tokens=240000,per_arm_requests=24)
        self.audit.arm_usage['A'] = dict(tokens=135150, requests=6)
        # Replay the recorded full prompt count as a conservative simulated
        # contents-count response. This is not a live count of blocked batch 3.
        config = SimpleNamespace(model_dump=lambda **kw:request['config'])
        delegate = SimpleNamespace(count_tokens=Mock(return_value=SimpleNamespace(total_tokens=usage['prompt_token_count'])))
        bound = self.audit.admit(delegate,dict(model=request['model'],contents=request['contents'],config=config))
        self.assertEqual(delegate.count_tokens.call_count,1)
        self.assertLess(self.audit.tokens+bound['total_bound'],300000)
        self.assertLess(135150+bound['total_bound'],240000)
        self.assertEqual(self.audit.requests,0)

    def test_real_token_limit_still_blocks_after_refinement(self):
        delegate = self.long_context()
        delegate.count_tokens.return_value.total_tokens = 200000
        with self.assertRaises(BudgetAdmissionError) as caught:
            self.audit.generate(delegate, **self.kwargs)
        self.assertIn('total_tokens',[v['metric'] for v in caught.exception.details['violations']])
        delegate.generate_content.assert_not_called()
        rejection = read(self.directory/'A/rejections/001.json')
        self.assertTrue(rejection['admission']['refined'])
        self.assertEqual(rejection['request']['contents'],self.kwargs['contents'])

    def test_refined_cost_limit_still_blocks(self):
        delegate = self.long_context()
        self.audit.cost = 0.79
        with self.assertRaises(BudgetAdmissionError) as caught:
            self.audit.generate(delegate, **self.kwargs)
        self.assertIn('cost_usd',[v['metric'] for v in caught.exception.details['violations']])
        delegate.generate_content.assert_not_called()

    def test_refined_arm_limit_still_blocks(self):
        delegate = self.long_context()
        self.audit.limits['per_arm_total_tokens'] = 240000
        self.audit.arm_usage['A'] = dict(tokens=220000,requests=0)
        with self.assertRaises(BudgetAdmissionError) as caught:
            self.audit.generate(delegate, **self.kwargs)
        self.assertIn('arm_tokens',[v['metric'] for v in caught.exception.details['violations']])
        delegate.generate_content.assert_not_called()

    def test_exhausted_actual_limit_does_not_count_or_generate(self):
        delegate = self.long_context()
        self.audit.tokens = 300000
        with self.assertRaises(BudgetAdmissionError):
            self.audit.generate(delegate, **self.kwargs)
        delegate.count_tokens.assert_not_called()
        delegate.generate_content.assert_not_called()

    def test_count_endpoint_failure_is_fail_closed(self):
        delegate = self.long_context()
        delegate.count_tokens.side_effect = TimeoutError('count failed')
        with self.assertRaises(BudgetAdmissionError) as caught:
            self.audit.generate(delegate, **self.kwargs)
        self.assertEqual(caught.exception.details['violations'][0]['metric'],'token_count_unavailable')
        delegate.generate_content.assert_not_called()
        self.assertFalse(self.audit.usage_incomplete)
        self.assertEqual(self.audit.requests,0)

    def test_missing_count_is_fail_closed(self):
        delegate = self.long_context()
        delegate.count_tokens.return_value.total_tokens = None
        with self.assertRaises(BudgetAdmissionError):
            self.audit.generate(delegate, **self.kwargs)
        delegate.generate_content.assert_not_called()

    def test_count_request_cap(self):
        delegate = self.long_context()
        self.audit.limits['token_count_requests'] = 0
        with self.assertRaises(BudgetAdmissionError):
            self.audit.generate(delegate, **self.kwargs)
        delegate.count_tokens.assert_not_called()

    def test_deadline_rechecked_after_counting(self):
        delegate = self.long_context()
        def expired(**kwargs):
            self.audit.deadline = 0
            return SimpleNamespace(total_tokens=35000)
        delegate.count_tokens.side_effect = expired
        with self.assertRaisesRegex(RuntimeError,'deadline'):
            self.audit.generate(delegate, **self.kwargs)
        delegate.generate_content.assert_not_called()

    def test_inconsistent_usage_blocks_next_arm(self):
        response = Response()
        response.usage_metadata = SimpleNamespace(prompt_token_count=100,candidates_token_count=200,
                                                  thoughts_token_count=300,total_token_count=5)
        with self.assertRaisesRegex(RuntimeError,'Inconsistent'):
            self.audit.generate(SimpleNamespace(generate_content=lambda **kw:response),**self.kwargs)
        self.assertTrue(self.audit.usage_incomplete)
        self.audit.arm = 'B'
        with self.assertRaisesRegex(RuntimeError,'Uncertain'):
            self.audit.generate(None,**self.kwargs)

    def test_started_run_cannot_reset_or_resume(self):
        (self.directory/'EXECUTION_STARTED.json').write_text('{}',encoding='utf-8')
        with self.assertRaisesRegex(FileExistsError,'cannot reset'):
            execute(Path('unused'),self.directory)

    def test_config_and_system_not_omitted_from_bound(self):
        small = request_bounds('x',Config().model_dump(),content_tokens=1)
        large = request_bounds('x',dict(max_output_tokens=16384,system_instruction='德国'*1000,
                                       response_schema={'description':'数据'*1000}),content_tokens=1)
        self.assertGreater(large['input_bound'],small['input_bound']+10000)

    def test_invalid_model_and_nontext_are_rejected(self):
        with self.assertRaises(ValueError):
            self.audit.generate(None,**dict(self.kwargs,model='unknown-model'))
        with self.assertRaises(ValueError):
            request_bounds(['not a text string'],Config().model_dump())

    def test_b_checker_does_not_treat_json_keys_as_source_ids(self):
        from check_product_b import referenced_source_ids
        section=dict(content='Text [source_123] [web-abc, web-def]',source_ids=['source_123'],
                     key_claims=[dict(text='Claim [web-xyz]',source_ids=['web-abc'],content_anchor='Text')])
        self.assertEqual(referenced_source_ids(section),{'source_123','web-abc','web-def','web-xyz'})

    def test_malformed_token_count_cannot_be_admitted(self):
        for count in (True,-1,0,'35000',1.5):
            with self.subTest(count=count), self.assertRaises(ValueError):
                request_bounds('test',Config().model_dump(),content_tokens=count)

    def test_missing_usage_locks_reservation(self):
        response=Response()
        response.usage_metadata=None
        response.model_dump=lambda **kw: {'text':'{}'}
        with self.assertRaisesRegex(RuntimeError,'Missing provider usage'):
            self.audit.generate(SimpleNamespace(generate_content=lambda **kw:response),**self.kwargs)
        self.assertTrue(self.audit.usage_incomplete)
        self.assertGreater(self.audit.unresolved_reservation,0)

    def test_repeated_small_requests_keep_real_cumulative_limits(self):
        response=Response()
        response.usage_metadata=SimpleNamespace(prompt_token_count=1000,candidates_token_count=3000,
                                               thoughts_token_count=1000,total_token_count=5000)
        delegate=SimpleNamespace(generate_content=Mock(return_value=response))
        for _ in range(3):
            self.audit.generate(delegate,**self.kwargs)
        with self.assertRaises(BudgetAdmissionError):
            self.audit.generate(delegate,**self.kwargs)
        self.assertEqual(delegate.generate_content.call_count,3)
        self.assertEqual(self.audit.tokens,15000)


if __name__ == '__main__':
    unittest.main()
