"""Batch row-dependency analysis using NumPy/LAPACK SVD and left nullspaces.

No chronology, deletion, path enumeration or custom factorization. A witness y
with y.T A = 0 identifies a dependency set; y.T b diagnoses its consistency.
Witness bases need not be sparse/minimal. Counts and participating rows do not
depend on which annotation a factorization happens to process first.
"""
from __future__ import annotations


def analyze_dependencies(variables, anchors, equations, tolerance=1e-6, rank_rcond=1e-12):
    import numpy as np

    names = sorted(variables)
    ordered = sorted(equations, key=lambda e: (e["annotation_id"], sorted(e["terms"].items()), e["value"]))
    matrix = np.zeros((len(ordered), len(names)))
    values = np.zeros(len(ordered))
    for i, equation in enumerate(ordered):
        matrix[i] = [equation["terms"].get(n,0) for n in names]
        values[i] = equation["value"]-sum(equation["terms"].get(n,0)*v for n,v in anchors.items())
    unseen = set(range(len(ordered)))
    certificates = []; components = []; involved = set(); rank = 0
    while unseen:
        todo = [min(unseen)]; row_ids = set(); columns = set()
        while todo:
            i = todo.pop()
            if i in row_ids:continue
            row_ids.add(i); unseen.discard(i)
            new_columns = set(np.flatnonzero(matrix[i]))-columns
            columns.update(new_columns)
            if new_columns:
                todo.extend(j for j in unseen if any(matrix[j,c] for c in new_columns))
        rows = sorted(row_ids); cols = sorted(columns)
        block = matrix[np.ix_(rows,cols)]
        # Positive row scaling removes arbitrary equation coefficient magnitudes.
        scale = np.linalg.norm(block, axis=1)
        scale[scale == 0] = 1
        block = block/scale[:,None]
        u, singular, vh = np.linalg.svd(block, full_matrices=True)
        threshold = rank_rcond*(float(singular[0]) if len(singular) else 1)
        block_rank = int(np.count_nonzero(singular > threshold))
        rank += block_rank
        left = u[:,block_rank:]
        # The nullspace projector identifies ALL interchangeable participating
        # rows, rather than labeling one row as the newly added culprit.
        participation = np.sum(left*left, axis=1)
        involved.update(ordered[rows[i]]["annotation_id"] for i,v in enumerate(participation) if v > rank_rcond)
        for column in range(left.shape[1]):
            witness = left[:,column]/scale
            witness /= np.max(np.abs(witness))
            active = np.flatnonzero(np.abs(witness) > rank_rcond)
            if witness[active[0]] < 0:witness = -witness
            residual = float(witness @ values[rows])
            certificates.append({
                "kind": "conflict" if abs(residual) > tolerance else "redundant",
                "annotation_ids": sorted({ordered[rows[i]]["annotation_id"] for i in active}),
                "weighted_value_residual_mm": residual,
                "coefficient_residual": float(np.max(np.abs(witness @ matrix[rows]))),
                "chain_combination": [{"annotation_id":ordered[rows[i]]["annotation_id"],
                                       "row_index":rows[i],"coefficient":float(witness[i])} for i in active],
            })
        components.append({"variables":[names[i] for i in cols],"row_count":len(rows),
                           "coefficient_rank":block_rank,"dependency_count":len(rows)-block_rank})
    return {"coefficient_rank":rank,"constraint_row_count":len(ordered),
            "dependency_count":len(ordered)-rank,"certificates":certificates,
            "participating_annotation_ids": sorted(involved),"components":components,
            "rank_rcond":rank_rcond,"engine":"numpy.linalg.svd (LAPACK gesdd)",
            "basis":"whole-matrix left-nullspace dependencies; annotation order is not blame; witnesses are not necessarily minimal"}
