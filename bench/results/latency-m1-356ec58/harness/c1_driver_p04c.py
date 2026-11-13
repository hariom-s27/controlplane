"""P04c variant of the P04b C1 driver. Changes vs c1_driver.py: base dir is _work/p04c;
only MODE=plain is accepted (no in-process patches); optional N / WARMUP args (default
L.N_CALLS / L.WARMUP, i.e. 1050 / 50); optional CAPTURE=1 (Part C verdict check only)
wraps bench.latency._one_call pass-through to record (case_id, intervention) per timed
call. Part E runs with CAPTURE=0 -> no wrapper around timed calls.

Usage: python [-I] c1_driver_p04c.py <COPY_DIR> plain <OUT_JSON> <LABEL> [N] [WARMUP] [CAPTURE]
P04b MODEs kept below for the diff only; N1/N2 are rejected:
  N1 DIAGNOSTIC: controlplane.manifest._validate_structural -> no-op (in this process only)
  N2 DIAGNOSTIC: controlplane.intercept.load_manifest -> cache keyed by (path, st_mtime_ns, st_size);
                 controlplane.manifest._validate_structural -> validator built once
No file in any copy is changed. Never calls build_report / --write. Writes only OUT_JSON.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

COPY = Path(sys.argv[1]).resolve()
MODE = sys.argv[2]
OUT = Path(sys.argv[3]).resolve()
LABEL = sys.argv[4]
LAB = Path(r"D:\sem_iitk\sem9\comp\_work\p04c").resolve()
assert MODE == "plain", "P04c: no in-process patches"
N_ARG = int(sys.argv[5]) if len(sys.argv) > 5 else None
WARMUP_ARG = int(sys.argv[6]) if len(sys.argv) > 6 else None
CAPTURE = len(sys.argv) > 7 and sys.argv[7] == "1"
assert COPY.is_relative_to(LAB)
sys.path.insert(0, str(COPY))

bad = [k for k in os.environ if "API_KEY" in k.upper() or "_TOKEN" in k.upper()]
assert not bad, f"ABORT: secret-like env vars present: {bad}"
assert os.environ.get("HF_HUB_OFFLINE") == "1" and os.environ.get("TRANSFORMERS_OFFLINE") == "1"
assert Path(tempfile.gettempdir()).resolve().is_relative_to(LAB), tempfile.gettempdir()
assert OUT.is_relative_to(LAB)

import controlplane  # noqa: E402

print("controlplane.__file__ =", controlplane.__file__, "| tempdir =", tempfile.gettempdir(),
      "| isolated =", sys.flags.isolated, "| dont_write_bytecode =", sys.dont_write_bytecode)
assert Path(controlplane.__file__).resolve().is_relative_to(COPY)

import bench.latency as L  # noqa: E402
import controlplane.intercept as intercept  # noqa: E402
import controlplane.manifest as M  # noqa: E402

assert Path(L.__file__).resolve().is_relative_to(COPY)
patched = []
if MODE == "N1":
    M._validate_structural = lambda data, name: None
    patched.append("controlplane.manifest._validate_structural -> no-op")
elif MODE == "N2":
    import jsonschema

    _validator = jsonschema.validators.validator_for(M._json_schema())(M._json_schema())

    def _validate_structural_once(data, name):
        instance = {k: v for k, v in data.items() if k != "_name"}
        try:
            _validator.validate(instance)
        except jsonschema.ValidationError as e:
            raise M.ManifestBindingError(f"manifests/{name}.yaml: structural schema violation: {e.message}") from e

    M._validate_structural = _validate_structural_once
    _orig_load = intercept.load_manifest
    _cache = {}

    def _cached_load_manifest(name):
        p = M.MANIFESTS_DIR / f"{name}.yaml"
        st = os.stat(p)
        key = (str(p), st.st_mtime_ns, st.st_size)
        hit = _cache.get(key)
        if hit is None:
            hit = _cache[key] = _orig_load(name)
        return hit

    intercept.load_manifest = _cached_load_manifest
    patched += ["controlplane.manifest._validate_structural -> prebuilt validator.validate",
                "controlplane.intercept.load_manifest -> cache[(path, st_mtime_ns, st_size)]"]
print("patched:", patched or "none")

captured = []
if CAPTURE:
    _orig_one_call = L._one_call

    def _capture_one_call(case, action):
        row = _orig_one_call(case, action)
        captured.append({"case_id": case["id"], "intervention": row["intervention"]})
        return row

    L._one_call = _capture_one_call
    patched.append("CAPTURE: bench.latency._one_call pass-through recorder (verdict check only)")

cfg = L.CONFIGS[0]
assert cfg["name"] == "C1_hhem_off_seq" and cfg["c3"] == "off" and cfg["concurrency"] == 1
cases = L.B.load_cases()
n_calls = N_ARG if N_ARG is not None else L.N_CALLS
warmup = WARMUP_ARG if WARMUP_ARG is not None else L.WARMUP
res = L.run_config(cfg, cases, n_calls=n_calls, warmup=warmup, cold_start_ms={"value": None, "config": None})
if CAPTURE:
    res["per_call"] = captured
st = res["stages"]
sum_p50 = sum((st[s]["p50"] or 0) for s in L.STAGES)
sum_mean = sum((st[s]["mean"] or 0) for s in L.STAGES)
e = res["end_to_end"]
res.update({
    "label": LABEL, "mode": MODE, "patched": patched, "copy": str(COPY), "tempdir": tempfile.gettempdir(),
    "python_isolated": sys.flags.isolated, "dont_write_bytecode": sys.dont_write_bytecode,
    "sum_stage_p50": round(sum_p50, 2), "gap_mean": round(e["mean"] - sum_mean, 2),
    "gap_p50": round(e["p50"] - sum_p50, 2),
})
if MODE == "N2":
    res["n2_cache_entries"] = len(_cache)
OUT.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
print(json.dumps({"label": LABEL, "n": res["n"], "p50": e["p50"], "p95": e["p95"], "p99": e["p99"], "max": e["max"],
                  "sum_stage_p50": res["sum_stage_p50"], "gap_mean": res["gap_mean"],
                  "sig_ok": res["all_signatures_valid"], "interventions": res["intervention_distribution"]}))
