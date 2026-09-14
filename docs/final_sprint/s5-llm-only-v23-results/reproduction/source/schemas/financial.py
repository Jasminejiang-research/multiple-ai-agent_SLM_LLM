"""Numeric provenance contract; arithmetic rules live in workflow.finance_contract."""
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator, model_validator

from schemas.evidence import StrictModel


class FinancialValue(StrictModel):
    value_id: str
    value: Decimal | None
    unit: str
    currency: str | None
    period: str
    origin: Literal["user_input", "external_benchmark", "calculated_result", "assumption"]
    input_ids: list[str]
    source_ids: list[str]
    formula_id: str | None
    rounding_policy: Literal["money_2dp_half_up", "ratio_4dp_half_up", "integer_exact", "exact"]
    status: Literal["value", "not_applicable"]
    reason: str | None

    @field_validator("value", mode="before")
    @classmethod
    def finite_decimal(cls, value):
        if value is not None and (isinstance(value, bool) or not Decimal(str(value)).is_finite()):
            raise ValueError("numeric values must be finite and not boolean")
        return value

    @model_validator(mode="after")
    def validate_origin(self):
        if (self.value is None) != (self.status == "not_applicable"):
            raise ValueError("only not_applicable values are null")
        if self.status == "not_applicable" and not self.reason:
            raise ValueError("not_applicable requires a reason")
        if self.origin == "calculated_result" and (not self.formula_id or not self.input_ids):
            raise ValueError("calculated values require a formula and input IDs")
        if self.origin != "calculated_result" and (self.formula_id or self.input_ids):
            raise ValueError("non-calculated values cannot carry a formula")
        if self.origin == "external_benchmark" and not self.source_ids:
            raise ValueError("external benchmark requires source IDs")
        return self
