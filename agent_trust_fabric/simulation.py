"""Reproducible, synthetic multi-agent scenario experiments.

The model is deliberately small and inspectable. It is not a forecast until its
parameters and outcomes have been validated against observations from the same
population and decision context.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass, replace
from typing import Any

MODEL_VERSION = "0.1.0"
MAX_WORK = 2_000_000  # population * steps * runs * arms


def _number(value: Any, name: str, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if not low <= value <= high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return float(value)


def _integer(value: Any, name: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f"{name} must be an integer between {low} and {high}")
    return value


def _keys(obj: Any, name: str, allowed: set[str], required: set[str]) -> dict:
    if not isinstance(obj, dict):
        raise ValueError(f"{name} must be an object")
    missing, extra = required - obj.keys(), obj.keys() - allowed
    if missing or extra:
        raise ValueError(f"{name} has missing keys {sorted(missing)} or unknown keys {sorted(extra)}")
    return obj


@dataclass(frozen=True)
class Parameters:
    quality: float
    price: float
    marketing: float
    failure_rate: float
    unit_cost: float
    revenue_per_active: float


@dataclass(frozen=True)
class Segment:
    name: str
    share: float
    interest: float
    price_sensitivity: float
    peer_influence: float
    quality_sensitivity: float
    churn: float


@dataclass(frozen=True)
class Intervention:
    name: str
    start_step: int
    changes: dict[str, float]


def _parameters(raw: Any) -> Parameters:
    fields = {"quality", "price", "marketing", "failure_rate", "unit_cost", "revenue_per_active"}
    obj = _keys(raw, "baseline", fields, fields)
    return Parameters(
        quality=_number(obj["quality"], "quality", 0, 1),
        price=_number(obj["price"], "price", 0, 10),
        marketing=_number(obj["marketing"], "marketing", 0, 1),
        failure_rate=_number(obj["failure_rate"], "failure_rate", 0, 1),
        unit_cost=_number(obj["unit_cost"], "unit_cost", 0, 1000),
        revenue_per_active=_number(obj["revenue_per_active"], "revenue_per_active", 0, 1000),
    )


def validate_scenario(raw: Any) -> dict:
    """Reject ambiguous or unbounded experiments before allocating work."""
    keys = {"schema_version", "scenario_id", "population", "steps", "runs", "seed", "network", "initial_adoption", "segments", "baseline", "interventions", "observations"}
    obj = _keys(raw, "scenario", keys, keys - {"observations"})
    if obj["schema_version"] != "0.1.0":
        raise ValueError("unsupported schema_version")
    if not isinstance(obj["scenario_id"], str) or not 1 <= len(obj["scenario_id"]) <= 100:
        raise ValueError("scenario_id must be a nonempty string of at most 100 characters")
    population = _integer(obj["population"], "population", 10, 5000)
    steps = _integer(obj["steps"], "steps", 1, 100)
    runs = _integer(obj["runs"], "runs", 1, 200)
    _integer(obj["seed"], "seed", 0, 2**32 - 1)
    network = _keys(obj["network"], "network", {"neighbors", "rewire_probability"}, {"neighbors", "rewire_probability"})
    neighbors = _integer(network["neighbors"], "neighbors", 2, min(30, population - 1))
    if neighbors % 2:
        raise ValueError("network.neighbors must be even")
    _number(network["rewire_probability"], "rewire_probability", 0, 1)
    _number(obj["initial_adoption"], "initial_adoption", 0, 1)
    segments = obj["segments"]
    if not isinstance(segments, list) or not 1 <= len(segments) <= 20:
        raise ValueError("segments must contain 1-20 entries")
    seen: set[str] = set()
    total = 0.0
    for item in segments:
        segment_keys = {"name", "share", "interest", "price_sensitivity", "peer_influence", "quality_sensitivity", "churn"}
        s = _keys(item, "segment", segment_keys, segment_keys)
        if not isinstance(s["name"], str) or not s["name"] or s["name"] in seen:
            raise ValueError("segment names must be nonempty and unique")
        seen.add(s["name"])
        total += _number(s["share"], "share", 0, 1)
        for field, low, high in (("interest", -5, 5), ("price_sensitivity", 0, 5), ("peer_influence", 0, 5), ("quality_sensitivity", 0, 5), ("churn", 0, 1)):
            _number(s[field], field, low, high)
    if not math.isclose(total, 1, abs_tol=1e-8):
        raise ValueError("segment shares must sum to one")
    base = _parameters(obj["baseline"])
    interventions = obj["interventions"]
    if not isinstance(interventions, list) or len(interventions) > 5:
        raise ValueError("interventions must contain at most five arms")
    names = {"baseline"}
    for item in interventions:
        arm = _keys(item, "intervention", {"name", "start_step", "changes"}, {"name", "start_step", "changes"})
        if not isinstance(arm["name"], str) or not arm["name"] or arm["name"] in names:
            raise ValueError("intervention names must be nonempty, unique, and not baseline")
        names.add(arm["name"])
        _integer(arm["start_step"], "start_step", 1, steps)
        changes = _keys(arm["changes"], "changes", set(Parameters.__dataclass_fields__), set())
        if not changes:
            raise ValueError("intervention changes cannot be empty")
        for field, value in changes.items():
            low, high = ((0, 1) if field in {"quality", "marketing", "failure_rate"} else (0, 10) if field == "price" else (0, 1000))
            _number(value, f"changes.{field}", low, high)
        replace(base, **changes)
    work = population * steps * runs * (1 + len(interventions))
    if work > MAX_WORK:
        raise ValueError(f"experiment exceeds {MAX_WORK:,} agent-steps; reduce population, steps, runs, or arms")
    if "observations" in obj:
        observations = obj["observations"]
        if not isinstance(observations, list) or not observations:
            raise ValueError("observations must be a nonempty array")
        observed_steps: set[int] = set()
        for observation in observations:
            o = _keys(observation, "observation", {"step", "active_share"}, {"step", "active_share"})
            step = _integer(o["step"], "observation.step", 1, steps)
            if step in observed_steps:
                raise ValueError("observation steps must be unique")
            observed_steps.add(step)
            _number(o["active_share"], "observation.active_share", 0, 1)
    return obj


def _network(size: int, degree: int, rewire: float, rng: random.Random) -> list[list[int]]:
    """Undirected ring lattice with rewired edge endpoints."""
    graph = [set() for _ in range(size)]
    edges = [(i, (i + distance) % size) for i in range(size) for distance in range(1, degree // 2 + 1)]
    for source, target in edges:
        if rng.random() < rewire:
            for _ in range(size * 2):
                candidate = rng.randrange(size)
                if candidate != source and candidate not in graph[source]:
                    target = candidate
                    break
            else:
                # The validated maximum degree is far below population size,
                # but keep a deterministic fallback for pathological graphs.
                candidates = [j for j in range(size) if j != source and j not in graph[source]]
                target = rng.choice(candidates)
        graph[source].add(target)
        graph[target].add(source)
    return [sorted(peers) for peers in graph]


def _sample_segments(segments: list[Segment], size: int, rng: random.Random) -> list[Segment]:
    return rng.choices(segments, weights=[s.share for s in segments], k=size)


def _sigmoid(value: float) -> float:
    return 1 / (1 + math.exp(-max(-20, min(20, value))))


def _quantile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    point = (len(ordered) - 1) * fraction
    low = math.floor(point)
    weight = point - low
    return ordered[low] * (1 - weight) + ordered[min(low + 1, len(ordered) - 1)] * weight


def _summary(values: list[float]) -> dict[str, float]:
    return {"mean": sum(values) / len(values), "p05": _quantile(values, 0.05), "p95": _quantile(values, 0.95)}


def _run_arm(segments: list[Segment], graph: list[list[int]], initial: list[bool], draws: list[list[tuple[float, float]]], base: Parameters, intervention: Intervention | None) -> dict:
    active = initial.copy()
    series = []
    total_resolutions = 0.0
    total_value = 0.0
    for step, step_draws in enumerate(draws, start=1):
        params = replace(base, **intervention.changes) if intervention and step >= intervention.start_step else base
        next_active = active.copy()
        new, lost = 0, 0
        for i, agent in enumerate(segments):
            peers = graph[i]
            peer_share = sum(active[j] for j in peers) / len(peers) if peers else 0
            if active[i]:
                churn_probability = min(1.0, agent.churn + params.failure_rate * 0.5)
                if step_draws[i][0] < churn_probability:
                    next_active[i] = False
                    lost += 1
            else:
                utility = agent.interest + agent.quality_sensitivity * (params.quality - 0.5) - agent.price_sensitivity * params.price + agent.peer_influence * (peer_share - 0.5) + params.marketing
                if step_draws[i][0] < _sigmoid(utility):
                    next_active[i] = True
                    new += 1
        active = next_active
        count = sum(active)
        # A second common draw models whether each active user's request resolves.
        resolutions = sum(1 for i, enabled in enumerate(active) if enabled and step_draws[i][1] < params.quality * (1 - params.failure_rate))
        value = count * (params.revenue_per_active - params.unit_cost)
        total_resolutions += resolutions
        total_value += value
        series.append({"step": step, "active": count, "active_share": count / len(active), "new": new, "lost": lost, "resolutions": resolutions, "net_value": value})
    return {"series": series, "final_active_share": series[-1]["active_share"], "total_resolutions": total_resolutions, "total_net_value": total_value}


def simulate(raw: Any) -> dict:
    """Run paired baseline and intervention arms with common random draws."""
    scenario = validate_scenario(raw)
    encoded = json.dumps(scenario, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    digest = hashlib.sha256(encoded).hexdigest()
    base = _parameters(scenario["baseline"])
    segments = [Segment(**item) for item in scenario["segments"]]
    arms = [None] + [Intervention(**item) for item in scenario["interventions"]]
    outcomes: dict[str, list[dict]] = {"baseline" if arm is None else arm.name: [] for arm in arms}
    for run in range(scenario["runs"]):
        rng = random.Random(scenario["seed"] + run)
        agents = _sample_segments(segments, scenario["population"], rng)
        graph = _network(scenario["population"], scenario["network"]["neighbors"], scenario["network"]["rewire_probability"], rng)
        initial = [rng.random() < scenario["initial_adoption"] for _ in agents]
        draws = [[(rng.random(), rng.random()) for _ in agents] for _ in range(scenario["steps"])]
        for arm in arms:
            name = "baseline" if arm is None else arm.name
            outcomes[name].append(_run_arm(agents, graph, initial, draws, base, arm))
    summaries = {}
    for name, trials in outcomes.items():
        summaries[name] = {
            "final_active_share": _summary([trial["final_active_share"] for trial in trials]),
            "total_resolutions": _summary([trial["total_resolutions"] for trial in trials]),
            "total_net_value": _summary([trial["total_net_value"] for trial in trials]),
            "trajectory": [{"step": step + 1, "active_share": _summary([trial["series"][step]["active_share"] for trial in trials])} for step in range(scenario["steps"])],
        }
    effects = {}
    for arm in scenario["interventions"]:
        name = arm["name"]
        effects[name] = {metric: _summary([outcomes[name][i][metric] - outcomes["baseline"][i][metric] for i in range(scenario["runs"])]) for metric in ("final_active_share", "total_resolutions", "total_net_value")}
    result: dict[str, Any] = {
        "model_version": MODEL_VERSION,
        "scenario_id": scenario["scenario_id"],
        "scenario_sha256": digest,
        "seed": scenario["seed"],
        "runs": scenario["runs"],
        "agent_steps": scenario["population"] * scenario["steps"] * scenario["runs"] * len(arms),
        "interpretation": "Synthetic scenario distribution; p05/p95 are run quantiles, not confidence intervals or validated forecasts.",
        "arms": summaries,
        "paired_effects": effects,
    }
    if "observations" in scenario:
        observations = scenario["observations"]
        baseline_series = summaries["baseline"]["trajectory"]
        model_errors = [abs(baseline_series[o["step"] - 1]["active_share"]["mean"] - o["active_share"]) for o in observations]
        naive_errors = [abs(scenario["initial_adoption"] - o["active_share"]) for o in observations]
        result["backtest"] = {
            "scope": "baseline arm only; observations supplied by scenario author, provenance not verified",
            "points": len(observations),
            "model_mae": sum(model_errors) / len(model_errors),
            "static_initial_share_mae": sum(naive_errors) / len(naive_errors),
        }
    return result
