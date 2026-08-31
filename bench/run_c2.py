"""P06 C2 harness. NOT executed by Claude Code -- prepared for manual
execution only. See reports/p06-c2-report.md for the exact command and the
GO/NO-GO verdict.

Loads the frozen configuration (bench/p06-c2-config.json), registers
ControlPlane's tau2 adapter via the public route
(bench/tau2_adapter.py::register_controlplane_domain), verifies the exact
40-task identity gate, pre-flight-validates all six governed manifests
BEFORE any model/provider call, then invokes tau2's own, unmodified
tau2.runner.batch.run_tasks() -- the same function tau2's own CLI (`tau2
run`) calls internally -- against the ControlPlane-wrapped retail
environment. Results are saved to a path distinct from C1; C1's files are
never opened by this script.

This script deliberately REFUSES TO START (exits before any LLM/provider
call) if any local pre-flight check fails. That refusal is intended
behaviour, not a bug to route around.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
CONTROLPLANE_ROOT = BENCH_DIR.parent
WORKSPACE_ROOT = CONTROLPLANE_ROOT.parents[2]
CONFIG_PATH = BENCH_DIR / "p06-c2-config.json"

sys.path.insert(0, str(BENCH_DIR))
sys.path.insert(0, str(CONTROLPLANE_ROOT))

from tau2_adapter import (  # noqa: E402
    TAU2_CONTROLPLANE_DOMAIN,
    load_c2_tasks,
    register_controlplane_domain,
)

from controlplane.manifest import ManifestBindingError, load_manifest  # noqa: E402

from tau2.data_model.simulation import TextRunConfig  # noqa: E402
from tau2.evaluator.evaluator import EvaluationType  # noqa: E402
from tau2.runner.batch import run_tasks  # noqa: E402


def _load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _preflight_manifests(manifest_files: list[str]) -> None:
    """Loads every governed manifest through the REAL controlplane loader
    before any model/provider call. Refuses to proceed on any failure --
    see this module's docstring."""
    failures: list[str] = []
    for path in manifest_files:
        name = Path(path).stem
        try:
            load_manifest(name)
            print(f"  OK    manifests/{name}.yaml")
        except ManifestBindingError as exc:
            failures.append(f"manifests/{name}.yaml: {exc}")
            print(f"  FAIL  manifests/{name}.yaml: {exc}")
    if failures:
        print(
            "\nPre-flight manifest validation FAILED for "
            f"{len(failures)}/{len(manifest_files)} manifest(s). Refusing to "
            "start C2 -- no model/provider call was made.",
            file=sys.stderr,
        )
        raise SystemExit(2)


def _preflight_api_key() -> None:
    if not os.environ.get("FEATHERLESS_API_KEY", "").strip():
        print(
            "FEATHERLESS_API_KEY is not set in the environment. Refusing to "
            "start C2 -- no model/provider call was made.",
            file=sys.stderr,
        )
        raise SystemExit(2)


def _configured_evaluation_type(config: dict) -> EvaluationType:
    """Resolve the frozen C1/C2 evaluation setting from the config artifact."""
    configured = config["evaluation"]["type"]
    try:
        return EvaluationType[configured]
    except KeyError as exc:
        raise ValueError(f"unknown tau2 evaluation type {configured!r}") from exc


def main() -> None:
    config = _load_config()

    print("=" * 70)
    print("P06 C2 -- ControlPlane-governed tau2-bench retail run")
    print("=" * 70)

    _preflight_api_key()

    print("\n== registering ControlPlane's public tau2 domain/resolver ==")
    register_controlplane_domain()
    print(f"  registered domain key: {TAU2_CONTROLPLANE_DOMAIN!r}")

    print("\n== task-set identity gate (frozen 40 task IDs) ==")
    task_ids = config["task_selection"]["task_ids"]
    tasks = load_c2_tasks(task_ids, task_split_name=config["task_selection"]["split"])
    print(f"  {len(tasks)}/{len(task_ids)} tasks loaded, exact set match confirmed")

    print("\n== manifest pre-flight (must pass before any model/provider call) ==")
    _preflight_manifests(config["controlplane_condition"]["manifests"])

    run_settings = config["run_settings"]
    model_cfg = config["model"]
    decoding = config["decoding"]
    evaluation_type = _configured_evaluation_type(config)

    run_config = TextRunConfig(
        domain=TAU2_CONTROLPLANE_DOMAIN,
        agent="llm_agent",
        user="user_simulator",
        llm_agent=model_cfg["benchmark_agent"],
        llm_args_agent=decoding["agent_llm_args"],
        llm_user=model_cfg["user_simulator"],
        llm_args_user=decoding["user_llm_args"],
        num_trials=config["k_num_trials"],
        max_steps=run_settings["max_steps"],
        max_errors=run_settings["max_errors"],
        max_concurrency=run_settings["concurrency"],
        seed=config["seed"],
        max_retries=run_settings["max_retries"],
        retry_delay=run_settings["retry_delay_s"],
        timeout=run_settings["timeout_s_per_task"],
    )

    save_path = (WORKSPACE_ROOT / config["output"]["path"]).resolve()
    save_path.parent.mkdir(parents=True, exist_ok=True)
    c1_path = (WORKSPACE_ROOT / config["output"]["c1_path_for_reference"]).resolve()
    assert save_path != c1_path, "C2 output path must never collide with C1's"

    print(f"\n== starting run_tasks(): {len(tasks)} tasks, domain={TAU2_CONTROLPLANE_DOMAIN!r} ==")
    print(f"   agent/user model: {model_cfg['benchmark_agent']}")
    print(f"   evaluation_type: {evaluation_type.name}")
    print(f"   save_path: {save_path}")
    print("   THIS IS THE FIRST POINT A REAL MODEL/PROVIDER CALL CAN OCCUR.\n")

    run_tasks(
        run_config,
        tasks,
        save_path=save_path,
        evaluation_type=evaluation_type,
        console_display=True,
    )


if __name__ == "__main__":
    main()
