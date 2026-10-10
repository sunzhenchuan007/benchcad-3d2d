"""Small exact-coefficient linear solver with component and proof reporting.

Only fixed datum anchors are substituted. GT variable values never enter solving.
Fraction arithmetic avoids numerical rank decisions for the supported linear IR.
Nominal equation consistency and agreement with GT have separate tolerances.
"""
from __future__ import annotations

from fractions import Fraction as F


def solve(variables, anchors, equations, consistency_tolerance=1e-6):
    names = sorted(variables)
    adjacency = {n: set() for n in names}
    normalized = []
    for equation in equations:
        terms = {n: F(str(c)) for n, c in equation["terms"].items() if c != 0}
        rhs = F(str(equation["value"]))
        for name in set(terms) & set(anchors):
            rhs -= terms.pop(name) * F(str(anchors[name]))
        for name in terms:
            if name not in variables:
                raise ValueError(f"Unknown variable: {name}")
            adjacency[name].update(set(terms) - {name})
        normalized.append((terms, rhs, equation["annotation_id"]))

    components = []
    seen = set()
    for name in names:
        if name in seen:
            continue
        todo = [name]; component = set()
        while todo:
            current = todo.pop()
            if current in component:
                continue
            component.add(current)
            todo.extend(adjacency[current] - component)
        seen.update(component)
        components.append(sorted(component))

    states = {}; ranks = []; conflicts = []
    # A datum-only equation can contradict the fixed frame and invalidates the system.
    global_conflicts = [aid for terms, rhs, aid in normalized
                        if not terms and abs(float(rhs)) > consistency_tolerance]
    for component in components:
        index = {name: i for i, name in enumerate(component)}
        rows = []
        for terms, rhs, aid in normalized:
            if set(terms) & set(component):
                rows.append(([terms.get(n, F(0)) for n in component] + [rhs], {aid: F(1)}))
        pivot = 0; pivots = {}
        for col in range(len(component)):
            selected = next((i for i in range(pivot, len(rows)) if rows[i][0][col]), None)
            if selected is None:
                continue
            rows[pivot], rows[selected] = rows[selected], rows[pivot]
            values, proof = rows[pivot]
            scale = values[col]
            rows[pivot] = ([v / scale for v in values], {k: v / scale for k, v in proof.items()})
            for i in range(len(rows)):
                if i == pivot or not rows[i][0][col]:
                    continue
                values, proof = rows[i]; factor = values[col]
                base_values, base_proof = rows[pivot]
                result_proof = dict(proof)
                for key, value in base_proof.items():
                    result_proof[key] = result_proof.get(key, F(0)) - factor * value
                rows[i] = ([a - factor * b for a, b in zip(values, base_values)],
                           {k: v for k, v in result_proof.items() if v})
            pivots[col] = pivot
            pivot += 1
        bad = [proof for values, proof in rows
               if not any(values[:-1]) and abs(float(values[-1])) > consistency_tolerance]
        inconsistent = bool(bad or global_conflicts)
        for proof in bad:
            conflicts.append({"variables": component, "annotation_ids": sorted(proof)})
        free = set(range(len(component))) - set(pivots)
        for name, col in index.items():
            underdetermined = col not in pivots or any(rows[pivots[col]][0][j] for j in free)
            if inconsistent:
                states[name] = {"status": "inconsistent", "proof": []}
            elif col not in pivots or any(rows[pivots[col]][0][j] for j in free):
                states[name] = {"status": "missing", "proof": []}
            else:
                values, proof = rows[pivots[col]]
                states[name] = {"status": "determined", "value": float(values[-1]),
                                "proof": sorted(proof)}
            states[name]["underdetermined"] = bool(underdetermined)
        ranks.append({"variables": component, "rank": len(pivots),
                      "augmented_rank": len(pivots)+int(bool(bad or global_conflicts)),
                      "nullity": len(component) - len(pivots), "inconsistent": inconsistent})
    return {"variables": states, "components": ranks, "conflicts": conflicts,
            "global_conflicts": global_conflicts, "rank": sum(c["rank"] for c in ranks),
            "augmented_rank": sum(c["rank"] for c in ranks)+int(bool(conflicts or global_conflicts))}


def check_values(solution, gt, tolerance):
    for name, item in solution["variables"].items():
        if item["status"] == "determined":
            expected = gt["variables"][name]["value"]
            allowed = tolerance["value_absolute_mm"] + tolerance["value_relative"] * abs(expected)
            item["expected"] = expected
            item["correct"] = abs(item["value"] - expected) <= allowed
            if not item["correct"]:
                item["status"] = "wrong"
    return solution
