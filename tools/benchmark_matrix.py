"""Measure whole-matrix diagnostics on deterministic 100/300/500-row systems."""
from __future__ import annotations

import json
from pathlib import Path
import random
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from benchcad3d2d.dependencies import analyze_dependencies
from benchcad3d2d.linear import solve


def benchmark():
    results = []
    for count in [100,300,500]:
        size = min(128,count//2)
        names = [f"p{i:03}" for i in range(size)]
        values = {name:i*3+7 for i,name in enumerate(names)}
        rows = [{"annotation_id":f"d{i:03}","terms":{name:1},"value":values[name]} for i,name in enumerate(names)]
        rng = random.Random(1947)
        for i in range(size,count):
            a,b = rng.sample(names,2)
            rows.append({"annotation_id":f"d{i:03}","terms":{a:1,b:-1},"value":values[a]-values[b]})
        start = perf_counter()
        dependencies = analyze_dependencies(values,{},rows)
        dependency_ms = 1000*(perf_counter()-start)
        start = perf_counter()
        solution = solve(values,{},rows)
        exact_ms = 1000*(perf_counter()-start)
        assert dependencies["coefficient_rank"] == solution["rank"] == size
        assert dependencies["dependency_count"] == count-size
        assert not solution["conflicts"]
        assert all(abs(s["value"]-values[n]) < 1e-9 for n,s in solution["variables"].items())
        results.append({"rows":count,"variables":size,"rank":size,"dependency_count":count-size,
                        "svd_diagnostics_ms":round(dependency_ms,3),"exact_solve_ms":round(exact_ms,3),
                        "note":"single local run, excludes drawing parsing/rendering; not a performance guarantee"})
    output = ROOT/".outputs/validation/matrix_scaling.json"
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(results,indent=2),encoding="utf-8")
    return results


if __name__ == "__main__":print(json.dumps(benchmark(),indent=2))
