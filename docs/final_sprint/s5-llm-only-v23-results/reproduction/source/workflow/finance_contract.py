"""Decimal recomputation of the two S0 case scenarios, with no unit conversion."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP, localcontext
from typing import Callable

from schemas.financial import FinancialValue

FINANCE_VERSION = "s0-case-formulas-v1"
D = Decimal

# Expected units, currencies and periods are frozen by S0 CASE_REVIEW/briefs.
EDU_INPUTS = {
    "starting_cash": ("USD", "USD", "opening"),
    "subscription_price": ("USD/customer/month", "USD", "month"),
    "variable_cost": ("USD/customer/month", "USD", "month"),
    "fixed_operating_cost": ("USD/month", "USD", "month"),
    "marketing_cost": ("USD/month", "USD", "month"),
    "one_time_setup": ("USD", "USD", "launch"),
    "months": ("months", None, "scenario"),
}
RING_INPUTS = {
    "starting_cash": ("USD", "USD", "opening"),
    **{key: ("USD/device", "USD", "sale") for key in (
        "hardware_price", "unit_manufacturing_cost", "unit_logistics_cost", "unit_warranty_return_reserve")},
    **{key: ("USD/subscriber/month", "USD", "month") for key in (
        "subscription_price", "subscription_variable_cost")},
    "subscription_attach_rate": ("fraction", None, "year_1"),
    "average_paid_subscription_months": ("months/subscriber", None, "year_1"),
    "fixed_launch_cost": ("USD", "USD", "year_1"),
    "marketing_cost": ("USD", "USD", "year_1"),
}


@dataclass(frozen=True)
class Formula:
    key: str
    inputs: tuple[str, ...]
    expression: str
    calculate: Callable
    unit: str = "USD"
    currency: str | None = "USD"
    period: str = "year_1"
    rounding: str = "money_2dp_half_up"


def _break_even(cost, contribution):
    return (cost / contribution).to_integral_value(rounding=ROUND_CEILING) if contribution > 0 else None


EDU_FORMULAS = (
    Formula("monthly_revenue", ("volume", "subscription_price"), "N * price", lambda n, p: n*p, "USD/month", period="month"),
    Formula("monthly_variable_cost", ("volume", "variable_cost"), "N * variable_cost", lambda n, c: n*c, "USD/month", period="month"),
    Formula("monthly_contribution", ("volume", "subscription_price", "variable_cost"), "N * (price - variable_cost)", lambda n, p, c: n*(p-c), "USD/month", period="month"),
    Formula("monthly_operating_result", ("monthly_contribution", "fixed_operating_cost", "marketing_cost"), "contribution - fixed - marketing", lambda c, f, m: c-f-m, "USD/month", period="month"),
    Formula("annual_cash_change", ("months", "monthly_operating_result", "one_time_setup"), "months * monthly_result - setup", lambda n, r, s: n*r-s),
    Formula("ending_cash", ("starting_cash", "annual_cash_change"), "starting_cash + cash_change", lambda c, r: c+r),
    Formula("break_even_users", ("fixed_operating_cost", "marketing_cost", "subscription_price", "variable_cost"), "ceil((fixed + marketing) / (price - variable_cost)); denominator <= 0: not_applicable", lambda f, m, p, c: _break_even(f+m, p-c), "customers", None, "monthly average over 12 months", "integer_exact"),
)
RING_FORMULAS = (
    Formula("hardware_revenue", ("volume", "hardware_price"), "U * hardware_price", lambda n, p: n*p),
    Formula("hardware_variable_cost", ("volume", "unit_manufacturing_cost", "unit_logistics_cost", "unit_warranty_return_reserve"), "U * (manufacturing + logistics + reserve)", lambda n, m, l, w: n*(m+l+w)),
    Formula("subscription_paid_months", ("volume", "subscription_attach_rate", "average_paid_subscription_months"), "U * attach_rate * paid_months", lambda n, a, m: n*a*m, "subscriber-months", None, rounding="exact"),
    Formula("subscription_revenue", ("subscription_paid_months", "subscription_price"), "paid_months * subscription_price", lambda n, p: n*p),
    Formula("subscription_variable_cost_total", ("subscription_paid_months", "subscription_variable_cost"), "paid_months * variable_cost", lambda n, c: n*c),
    Formula("annual_contribution", ("hardware_revenue", "hardware_variable_cost", "subscription_revenue", "subscription_variable_cost_total"), "hardware_revenue - hardware_cost + subscription_revenue - subscription_cost", lambda a, b, c, d: a-b+c-d),
    Formula("annual_cash_change", ("annual_contribution", "fixed_launch_cost", "marketing_cost"), "contribution - fixed - marketing", lambda c, f, m: c-f-m),
    Formula("ending_cash", ("starting_cash", "annual_cash_change"), "starting_cash + cash_change", lambda c, r: c+r),
    Formula("break_even_units", ("fixed_launch_cost", "marketing_cost", "hardware_price", "unit_manufacturing_cost", "unit_logistics_cost", "unit_warranty_return_reserve", "subscription_attach_rate", "average_paid_subscription_months", "subscription_price", "subscription_variable_cost"), "ceil((fixed + marketing) / ((price - manufacturing - logistics - reserve) + attach_rate * months * (subscription_price - subscription_cost))); denominator <= 0: not_applicable", lambda f,m,p,c,l,w,a,n,s,v: _break_even(f+m,(p-c-l-w)+a*n*(s-v)), "devices", None, rounding="integer_exact"),
)


def _round(value: Decimal | None, policy: str):
    if value is None:
        return None
    quantum = {"money_2dp_half_up": D(".01"), "ratio_4dp_half_up": D(".0001")}.get(policy)
    return value.quantize(quantum, rounding=ROUND_HALF_UP) if quantum else value


class FinanceContract:
    """An immutable brief-derived reference; candidate outputs never set the rules."""
    def __init__(self, case_id: str, brief: dict, allowed_source_ids: set[str]):
        if case_id not in ("ai_education", "intelligent_ring"):
            raise ValueError("no frozen finance formulas for this case")
        self.case_id = case_id
        self.formulas = EDU_FORMULAS if case_id == "ai_education" else RING_FORMULAS
        specs = EDU_INPUTS if case_id == "ai_education" else RING_INPUTS
        raw = brief["financial_inputs"]
        volume_key = "average_paying_users" if case_id == "ai_education" else "units_sold"
        volume_spec = ("customers", None, "monthly average over 12 months") if case_id == "ai_education" else ("devices", None, "year_1")
        values = {}
        for key, spec in {**specs, **{f"{volume_key}.{s}": volume_spec for s in ("low", "base", "high")}}.items():
            original = raw[volume_key] if key.startswith(volume_key + ".") else raw[key]
            if (original["unit"], original.get("currency"), original["period"]) != spec:
                raise ValueError(f"unit/currency/period mismatch for input {key}")
            value = original[key.split(".")[1]] if "." in key else original["value"]
            numeric = D(str(value))
            if isinstance(value, bool) or not numeric.is_finite() or numeric < 0:
                raise ValueError(f"invalid input {key}")
            if set(original.get("source_ids", [])) - allowed_source_ids:
                raise ValueError("financial input source outside allowlist")
            policy = "integer_exact" if key.startswith(volume_key + ".") or key == "months" else "exact"
            if policy == "integer_exact" and numeric != numeric.to_integral_value():
                raise ValueError("count inputs must be integers")
            values[key] = FinancialValue(value_id=key, value=numeric, unit=spec[0], currency=spec[1], period=spec[2],
                origin=original["origin"], input_ids=[], source_ids=original.get("source_ids", []), formula_id=None,
                rounding_policy=policy, status="value", reason=None)
        if case_id == "ai_education" and values["months"].value != 12:
            raise ValueError("frozen scenario requires 12 months")
        if case_id == "intelligent_ring" and (values["subscription_attach_rate"].value > 1 or values["average_paid_subscription_months"].value > 12):
            raise ValueError("invalid subscription rate or duration")
        self._inputs = {key: row.model_dump(mode="json") for key, row in values.items()}
        self._expected = {}
        with localcontext() as ctx:
            ctx.prec = 40
            for scenario in ("low", "base", "high"):
                numeric_values = {k: v.value for k, v in values.items()}
                numeric_values["volume"] = values[f"{volume_key}.{scenario}"].value
                output_keys = set()
                for formula in self.formulas:
                    result = formula.calculate(*(numeric_values[k] for k in formula.inputs))
                    numeric_values[formula.key] = result
                    input_ids = [f"{volume_key}.{scenario}" if k == "volume" else f"{scenario}.{k}" if k in output_keys else k for k in formula.inputs]
                    output_keys.add(formula.key)
                    row = FinancialValue(value_id=f"{scenario}.{formula.key}", value=_round(result, formula.rounding),
                        unit=formula.unit, currency=formula.currency, period=formula.period, origin="calculated_result",
                        input_ids=input_ids, source_ids=[], formula_id=f"{FINANCE_VERSION}/{case_id}/{formula.key}",
                        rounding_policy=formula.rounding, status="value" if result is not None else "not_applicable",
                        reason=None if result is not None else "nonpositive_contribution_denominator")
                    self._expected[row.value_id] = row.model_dump(mode="json")

    def expected_values(self) -> list[FinancialValue]:
        """For deterministic verification and fixtures, not model-generated results."""
        return [FinancialValue.model_validate(v) for v in self._expected.values()]

    @property
    def value_ids(self) -> set[str]:
        return set(self._inputs) | set(self._expected)

    def prompt_spec(self) -> dict:
        return {"version": FINANCE_VERSION, "inputs": list(self._inputs.values()),
                "required_results": [{k: v for k, v in row.items() if k not in ("value", "status", "reason")} for row in self._expected.values()],
                "formulas": [{"key": f.key, "inputs": f.inputs, "expression": f.expression} for f in self.formulas],
                "rules": "Use unrounded Decimal intermediates. Money: 2dp HALF_UP, tolerance 0.01; ratios: 0.0001; counts exact. Do not infer a forecast from assumptions."}

    def validate(self, rows: list[FinancialValue]) -> None:
        by_id = {row.value_id: row for row in rows}
        if len(by_id) != len(rows) or set(by_id) != set(self._expected):
            raise ValueError("finance ledger must contain each frozen result exactly once")
        for key, data in self._expected.items():
            expected = FinancialValue.model_validate(data)
            actual = by_id[key]
            if actual.model_dump(exclude={"value"}) != expected.model_dump(exclude={"value"}):
                raise ValueError(f"finance metadata/provenance mismatch: {key}")
            if expected.value is None:
                if actual.value is not None:
                    raise ValueError(f"expected not_applicable: {key}")
                continue
            tolerance = {"money_2dp_half_up": D(".01"), "ratio_4dp_half_up": D(".0001")}.get(expected.rounding_policy, D(0))
            if actual.value is None or abs(actual.value - expected.value) > tolerance:
                raise ValueError(f"finance recomputation mismatch: {key}")
            if expected.rounding_policy == "integer_exact" and actual.value != actual.value.to_integral_value():
                raise ValueError(f"count must be exact integer: {key}")
            if _round(actual.value, actual.rounding_policy) != actual.value:
                raise ValueError(f"rounding mismatch: {key}")
