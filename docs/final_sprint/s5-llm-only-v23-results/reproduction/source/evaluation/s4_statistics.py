"""Frozen, descriptive n=2 paired summaries. No imputation or significance tests."""
from statistics import mean, median
import math

COMPARISONS = (("B","A"),("C","B"),("C","D"))
WEIGHTS = (.25,.20,.15,.15,.15,.10)


def metric_observed(row, metric):
    value=row.get(metric)
    return (type(value) in (int,float) and math.isfinite(value) and
            row.get(metric+"_state","observed")=="observed")


def academic_score(scores):
    if len(scores) != 6 or any(type(s) is not int or not 1 <= s <= 5 for s in scores):
        raise ValueError("six human integer scores in 1..5 required")
    return 100*sum(w*(s-1)/4 for w,s in zip(WEIGHTS,scores))


def quantile(values, q):
    values = sorted(values)
    at = (len(values)-1)*q
    lo, hi = math.floor(at),math.ceil(at)
    return values[lo]+(values[hi]-values[lo])*(at-lo)


def paired(rows, metric, *, direction="higher", comparisons=COMPARISONS):
    if direction not in ("higher","lower","descriptive"):
        raise ValueError("unknown direction")
    keyed = {}
    for row in rows:
        key = row["case_id"],row["condition"]
        if key in keyed:
            raise ValueError("duplicate canonical case/condition; repeated ratings are not runs")
        keyed[key] = row
    details, summaries = [], []
    cases = sorted({r["case_id"] for r in rows})
    for left,right in comparisons:
        differences = []
        improved = tied = worsened = 0
        for case in cases:
            lrow,rrow = keyed.get((case,left),{}),keyed.get((case,right),{})
            lv,rv = lrow.get(metric),rrow.get(metric)
            complete = metric_observed(lrow,metric) and metric_observed(rrow,metric)
            diff = lv-rv if complete else None
            effect = "missing"
            if complete:
                differences.append(diff)
                signed = diff if direction == "higher" else -diff
                effect = "descriptive" if direction == "descriptive" else "tied" if abs(diff)<1e-12 else "improved" if signed>0 else "worsened"
                improved += effect == "improved"
                tied += effect == "tied"
                worsened += effect == "worsened"
            details.append(dict(metric=metric,comparison=f"{left}-{right}",case_id=case,
                left_value=lv,right_value=rv,difference=diff,left_execution=lrow.get("execution","missing"),
                right_execution=rrow.get("execution","missing"),left_state=lrow.get(metric+"_state","missing"),
                right_state=rrow.get(metric+"_state","missing"),effect=effect))
        summaries.append(dict(metric=metric,comparison=f"{left}-{right}",complete_pairs=len(differences),
            planned_cases=len(cases),mean_difference=mean(differences) if differences else None,
            median_difference=median(differences) if differences else None,
            difference_iqr=quantile(differences,.75)-quantile(differences,.25) if differences else None,
            improved=improved if direction != "descriptive" else None,tied=tied if direction != "descriptive" else None,
            worsened=worsened if direction != "descriptive" else None,direction=direction,
            quartile_method="linear interpolation (type 7)",independent_unit="case_id"))
    return details,summaries


def condition_summary(rows, metrics):
    output = []
    for arm in "ABCD":
        cases = [r for r in rows if r["condition"] == arm]
        for metric in metrics:
            values = [r[metric] for r in cases if metric_observed(r,metric)]
            output.append(dict(condition=arm,metric=metric,mean=mean(values) if values else None,
                median=median(values) if values else None,valid_cases=len(values),planned_cases=len(cases),
                aggregation="equal weight of applicable case values; no pooling claim denominators"))
    return output
