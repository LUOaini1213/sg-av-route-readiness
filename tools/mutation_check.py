"""Mutation check: break the code on purpose and confirm the test suite notices.

A passing suite only counts as evidence if it can fail. Each mutant below changes one
line of real logic. The script first runs the suite on the unmodified code (it must
pass), then applies each mutant in turn, runs the suite, and restores the file. A mutant
that still passes is "survived" and means a test is missing. The run fails if any
mutant survives or the baseline fails. Results go to results/mutation.json.

    python tools/mutation_check.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "avready"

MUTANTS = [
    ("common.py", "d = (b_out - b_in + 180.0) % 360.0 - 180.0", "d = (b_in - b_out + 180.0) % 360.0 - 180.0",
     "turn sign flipped (left/right swapped)"),
    ("common.py", "math.atan2(x1 - x0, y1 - y0)", "math.atan2(y1 - y0, x1 - x0)", "bearing measured from east"),
    ("network.py", "        if cross > 0 and cost < best_left[1]:", "        if cross < 0 and cost < best_left[1]:",
     "kerb side taken as the right-hand side"),
    ("network.py", '[seq[0]["edge"][1]] if route.get("loop", True) else list(seq[0]["edge"])',
     'list(seq[0]["edge"])', "loop closure double-counts the first stop edge"),
    ("network.py", '    if v == "-1":\n        return -1', '    if v == "-1":\n        return 1',
     "reversed one-way treated as forward"),
    ("profile.py", "        if segs and acc < target_m / 2:", "        if segs and acc < target_m / 4:",
     "short tail no longer merged"),
    ("profile.py", "    return max(1, total // 2) if total else None", "    return total if total else None",
     "two-way lanes not split by direction"),
    ("profile.py", 'if c in ("zebra", "uncontrolled", "marked", "unmarked", "informal")',
     'if c in ("uncontrolled", "marked", "unmarked", "informal")', "zebra crossings not counted as uncontrolled"),
    ("profile.py", "    return (b.x - a.x) * (p.y - a.y) - (b.y - a.y) * (p.x - a.x) > 0",
     "    return (b.x - a.x) * (p.y - a.y) - (b.y - a.y) * (p.x - a.x) < 0", "bus stops on the wrong kerb"),
    ("profile.py", "                if j not in seen and math.dist(pts[k], pts[j]) < radius:",
     "                if j not in seen and math.dist(pts[k], pts[j]) < radius / 2:", "cluster radius halved"),
    ("profile.py", 'kind = "u_turn" if abs(ang) >= 150 else ("right" if ang > 0 else "left")',
     'kind = "u_turn" if abs(ang) >= 150 else ("left" if ang > 0 else "right")', "turn labels swapped"),
    ("profile.py", '        rad = cfg["buffers_m"]["junction_signal"]', "        rad = 5.0",
     "signal search radius ignored"),
    ("profile.py", "        if not at_junction and abs(ang) < 150:", "        if False:",
     "road bends counted as junction turns"),
    ("risk.py", "    return sum(1 for b in bands if value >= b)", "    return sum(1 for b in bands if value > b)",
     "likelihood thresholds made exclusive"),
    ("risk.py", "        if score >= threshold:", "        if score > threshold:", "rating thresholds made exclusive"),
    ("risk.py", '                "score": L * S,', '                "score": L + S,', "score added instead of multiplied"),
    ("speedbands.py", "    return mid.where(df[\"SpeedBand\"] != 8, band8)", "    return mid",
     "band 8 midpoint not substituted"),
    ("speedbands.py", "        std = float(a.std(ddof=0))", "        std = float(a.std(ddof=1))",
     "sample instead of population std"),
    ("speedbands.py", "    return ts.weekday() in win[\"days\"] and time(h0, m0) <= ts.time() <= time(h1, m1)",
     "    return ts.weekday() in win[\"days\"] and time(h0, m0) < ts.time() <= time(h1, m1)",
     "operating window start excluded"),
    ("speedbands.py", "    if day in SG_PUBLIC_HOLIDAYS:\n        return False", "    if False:\n        return False",
     "public holidays treated as service days"),
    ("kpi.py", '(include_planned or e["category"] != "planned")', "True",
     "planned disengagements counted"),
    ("kpi.py", "    ok = sum(1 for t in ops if early <= _minutes(t[\"scheduled_departure\"], t[\"actual_departure\"]) <= late)",
     "    ok = sum(1 for t in ops if early < _minutes(t[\"scheduled_departure\"], t[\"actual_departure\"]) < late)",
     "on-time window bounds excluded"),
    ("kpi.py", "    return None if auto + man == 0 else man / (auto + man)", "    return None if auto == 0 else man / auto",
     "manual share over autonomous km only"),
    ("kpi.py", '    return None if not trips else sum(1 for t in trips if t["status"] == "operated") / len(trips)',
     '    return None if not trips else 1.0', "availability always 100%"),
    ("geocode.py", '        for test in (lambda r: q in (r["SEARCHVAL"], r["BUILDING"]),\n                     lambda r: r["SEARCHVAL"].startswith(q) or r["BUILDING"].startswith(q)):',
     '        for test in (lambda r: q in r["SEARCHVAL"] or q in r["BUILDING"],):',
     "substring match picks the wrong building"),
    ("trace.py", "    line = dark & ~blobs", "    line = dark", "stop markers left in the trace"),
    ("trace.py", "            M = _affine_fit(pix[keep], roads[i[keep]])", "            M = M",
     "no road-matching refinement"),
    ("network.py", "        w[(u, v)] = d[\"weight\"] * (1.0 + (OFF_TRACE_PENALTY - 1.0) * min(1.0, excess / TRACE_RAMP))",
     "        w[(u, v)] = d[\"weight\"]", "published map ignored when routing"),
]


def run_tests() -> bool:
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider"], cwd=ROOT,
                       capture_output=True, text=True)
    return r.returncode == 0


def main() -> int:
    if not run_tests():
        print("baseline suite fails; fix that first")
        return 1
    results = []
    for fname, old, new, desc in MUTANTS:
        path = SRC / fname
        text = path.read_text(encoding="utf-8")
        if text.count(old) != 1:
            print(f"mutant anchor not found exactly once in {fname}: {old[:60]!r}")
            return 1
        path.write_text(text.replace(old, new), encoding="utf-8")
        try:
            passed = run_tests()
        finally:
            path.write_text(text, encoding="utf-8")
        status = "SURVIVED" if passed else "killed"
        results.append({"file": fname, "mutant": desc, "status": status})
        print(f"{status:8s} {fname}: {desc}")
    killed = sum(r["status"] == "killed" for r in results)
    out = {"baseline": "passed", "mutants": len(results), "killed": killed, "results": results}
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "mutation.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"{killed}/{len(results)} mutants killed")
    return 0 if killed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
