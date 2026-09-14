"""Cumulative S5 smoke admission at each physical request, with durable audits."""
from __future__ import annotations

from copy import deepcopy
from math import isfinite
import re
from threading import Lock

from workflow.review_runtime import SharedBudgetStop


SMOKE_BUDGET_BASELINE_VERSION = "s5-smoke-budget-baseline-v1"
SMOKE_BUDGET_EPOCH_AUTHORIZATION_VERSION = "s5-smoke-budget-epoch-v1"
_METRICS = ("requests", "total_tokens", "cost_usd")
_UNCHANGED_SMOKE_LIMITS = {"requests": 54, "total_tokens": 480000, "cost_usd": 1.20}


def _spend(values, *, label):
    result = {}
    for key in _METRICS:
        value = values.get(key)
        valid = (type(value) in (int, float) and isfinite(value) and value >= 0
            if key == "cost_usd" else type(value) is int and value >= 0)
        if not valid:
            raise ValueError(f"{label}: invalid {key}")
        result[key] = round(value, 9) if key == "cost_usd" else value
    return result


def _add_spend(left, right):
    return {key: round(left[key] + right[key], 9) if key == "cost_usd"
        else left[key] + right[key] for key in _METRICS}


def resolve_smoke_budget_baseline(prior, authorization=None):
    """Partition preserved historical spend only under the explicit v20 authority.

    This pure function does not rewrite or reclassify any historical run. Its
    caller must independently verify the referenced authorization and summary
    file hashes before dispatch/freeze; the complete record inventory remains in
    ``prior``. Without the versioned approval every historical request counts.
    """
    lifetime = _spend(prior, label="lifetime smoke prior")
    zero = dict(requests=0, total_tokens=0, cost_usd=0.0)
    records = prior.get("records", [])
    if not isinstance(records, list):
        raise ValueError("smoke prior records must be a list")
    baseline = dict(version=SMOKE_BUDGET_BASELINE_VERSION, mode="lifetime",
        starts_at_experiment_version=None, authorization_record=None,
        lifetime_prior=dict(lifetime), active_prior=dict(lifetime),
        excluded_prior=dict(zero),
        active_record_paths=[record.get("path") for record in records],
        excluded_record_paths=[], history_preserved=True)
    if authorization is None:
        return baseline
    if not isinstance(authorization, dict):
        raise ValueError("explicit versioned smoke budget epoch authorization required")
    if (authorization.get("version") != SMOKE_BUDGET_EPOCH_AUTHORIZATION_VERSION
            or authorization.get("approved") is not True
            or type(authorization.get("starts_at_experiment_version")) is not int
            or authorization["starts_at_experiment_version"] != 20
            or authorization.get("preserve_lifetime_history") is not True
            or authorization.get("unchanged_hard_limits") != _UNCHANGED_SMOKE_LIMITS):
        raise ValueError("invalid v20 smoke budget epoch authorization or changed hard limits")
    provenance = authorization.get("authorization_record")
    if (not isinstance(provenance, dict)
            or not isinstance(provenance.get("path"), str)
            or not provenance["path"].lower().endswith(".json")
            or not re.fullmatch(r"[0-9a-f]{64}", str(provenance.get("sha256", "")))):
        raise ValueError("smoke budget epoch authorization record and SHA256 required")
    if prior.get("usage_incomplete") or prior.get("pending_attempt_ids"):
        raise ValueError("historical smoke usage unresolved; no epoch admission")
    aggregate, active, excluded = dict(zero), dict(zero), dict(zero)
    active_paths, excluded_paths, versions = [], [], set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("invalid historical smoke record")
        path = record.get("path", "")
        normalized = path.replace("\\", "/") if isinstance(path, str) else ""
        match = re.search(r"(?:^|/)s5-llm-only-v([1-9][0-9]*)/smoke_summary\.json$", normalized)
        if (match is None or ".." in normalized.split("/")
                or not re.fullmatch(r"[0-9a-f]{64}", str(record.get("sha256", "")))):
            raise ValueError("historical smoke record path and SHA256 required")
        version = int(match.group(1))
        if version in versions:
            raise ValueError("duplicate historical smoke experiment version")
        versions.add(version)
        if (record.get("usage_incomplete") or record.get("pending_attempt_ids")
                or record.get("usage_accounting", {}).get("usage_incomplete")
                or record.get("usage_accounting", {}).get("pending_attempt_ids")):
            raise ValueError("historical smoke usage unresolved; no epoch admission")
        spend = _spend(record, label=f"historical smoke v{version}")
        aggregate = _add_spend(aggregate, spend)
        if version >= 20:
            active = _add_spend(active, spend)
            active_paths.append(path)
        else:
            excluded = _add_spend(excluded, spend)
            excluded_paths.append(path)
    if 20 not in versions:
        raise ValueError("authorized v20 baseline must retain the v20 smoke summary")
    if aggregate != lifetime:
        raise ValueError("historical smoke inventory does not match lifetime totals")
    baseline.update(mode="authorized_epoch", starts_at_experiment_version=20,
        authorization_record=deepcopy(provenance), active_prior=active,
        excluded_prior=excluded, active_record_paths=active_paths,
        excluded_record_paths=excluded_paths)
    return baseline


class CumulativeSmokeBudget:
    """Keep unknown calls charged at their reservation and stop subsequent calls."""

    version = "s5-cumulative-physical-smoke-budget-v1"

    def __init__(self, prior, limits, *, input_price=.30, output_price=2.50,
                 authorization=None):
        self.baseline = resolve_smoke_budget_baseline(prior, authorization)
        if authorization is not None and (limits != _UNCHANGED_SMOKE_LIMITS
                or input_price != .30 or output_price != 2.50):
            raise ValueError("authorized smoke epoch cannot change hard limits or token prices")
        self.prior = dict(self.baseline["active_prior"])
        self.limits = dict(limits)
        self.input_price, self.output_price = input_price, output_price
        self._charged = dict(requests=0, prompt_tokens=0, output_tokens=0,
                             total_tokens=0, cost_usd=0.0)
        self._known = dict(self._charged)
        self._pending = {}
        self._incomplete = False
        self._lock = Lock()

    def _check(self, estimated_tokens):
        if type(estimated_tokens) is not int or estimated_tokens < 0:
            raise ValueError("non-negative integer physical token reservation required")
        if self._incomplete or self._pending:
            raise SharedBudgetStop("prior smoke physical usage unresolved; reservation retained")
        attempted = dict(requests=self.prior["requests"] + self._charged["requests"] + 1,
            total_tokens=self.prior["total_tokens"] + self._charged["total_tokens"] + estimated_tokens,
            cost_usd=self.prior["cost_usd"] + self._charged["cost_usd"] +
                estimated_tokens * self.output_price / 1_000_000)
        if any(attempted[key] > self.limits[key] + (1e-12 if key == "cost_usd" else 0)
               for key in attempted):
            raise SharedBudgetStop("cumulative smoke hard-limit reservation failed before physical dispatch")

    def check_request(self, *, estimated_tokens):
        with self._lock:
            self._check(estimated_tokens)

    def reserve_request(self, *, attempt_id, estimated_tokens, journal):
        with self._lock:
            self._check(estimated_tokens)
            if attempt_id in self._pending:
                raise ValueError("duplicate cumulative smoke reservation")
            reservation_cost = round(estimated_tokens * self.output_price / 1_000_000, 9)
            self._pending[attempt_id] = (estimated_tokens, reservation_cost)
            self._charged["requests"] += 1
            self._charged["total_tokens"] += estimated_tokens
            self._charged["cost_usd"] = round(self._charged["cost_usd"] + reservation_cost, 9)
            audit = dict(version=self.version, attempt_id=attempt_id, status="reserved_before_dispatch",
                reservation_tokens=estimated_tokens, reservation_cost_usd=reservation_cost,
                prior=dict(self.prior), current_charged=dict(self._charged), hard_limits=dict(self.limits),
                budget_baseline=deepcopy(self.baseline))
        journal.emit("cumulative_smoke_budget", audit)

    def record_usage(self, *, attempt_id, event, journal):
        with self._lock:
            estimate, reserved_cost = self._pending.pop(attempt_id)
            values = [event.get(key) for key in ("prompt_tokens", "output_tokens", "total_tokens")]
            complete = all(type(value) is int and value >= 0 for value in values)
            prompt, output, total = values
            complete = complete and total >= prompt + output
            if complete:
                cost = round((prompt * self.input_price + (total - prompt) * self.output_price) / 1_000_000, 9)
                self._charged["total_tokens"] += total - estimate
                self._charged["cost_usd"] = round(self._charged["cost_usd"] + cost - reserved_cost, 9)
                for key, value in zip(("prompt_tokens", "output_tokens", "total_tokens"), values):
                    self._known[key] += value
                self._known["requests"] += 1
                self._known["cost_usd"] = round(self._known["cost_usd"] + cost, 9)
                self._charged["prompt_tokens"] += prompt
                self._charged["output_tokens"] += output
            else:
                # Even a known total with unknown input/output leaves billing uncertain.
                # Retain at least the full original byte-based reservation in every case.
                known_total = total if type(total) is int and total >= 0 else 0
                charge = max(estimate, known_total,
                    sum(value for value in (prompt, output) if type(value) is int and value >= 0))
                self._charged["total_tokens"] += charge - estimate
                self._charged["cost_usd"] = round(self._charged["cost_usd"] +
                    charge * self.output_price / 1_000_000 - reserved_cost, 9)
                self._incomplete = True
            audit = dict(version=self.version, attempt_id=attempt_id,
                status="actual_usage" if complete else "reservation_retained_usage_incomplete",
                current_charged=dict(self._charged),
                actual_complete_usage=dict(self._known), usage_incomplete=self._incomplete,
                budget_baseline=deepcopy(self.baseline))
        journal.emit("cumulative_smoke_budget", audit)

    def snapshot(self):
        with self._lock:
            return dict(version=self.version, charged=dict(self._charged),
                budget_baseline=deepcopy(self.baseline),
                active_cumulative=_add_spend(self.prior, self._charged),
                lifetime_cumulative=_add_spend(self.baseline["lifetime_prior"], self._charged),
                actual_complete_usage=dict(self._known),
                usage_incomplete=self._incomplete or bool(self._pending),
                pending_attempt_ids=sorted(self._pending),
                actual_field_basis=("conservative_charged_usage_not_actual_expense"
                    if self._incomplete or self._pending else "actual_complete_usage"),
                accounting_basis="actual_usage_or_retained_conservative_physical_reservation")
