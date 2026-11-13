"""Integrity record v2 for protected artifacts (P05 V6, V7; PR-02).

v1 (docs/p06-post-p02-integrity.sha256) hashed raw bytes, so a CRLF checkout and
an LF checkout of the same content gave different hashes. v2 hashes text files
(suffixes in TEXT_SUFFIXES) LF-normalised: every CRLF is replaced by LF, nothing
else changes. All other files (e.g. .png) are hashed as raw bytes.

Record rows:  <sha256_lf>  <status>  <path>  <authority>
  status    UNCHANGED_SINCE_V1  content equals the v1 row (v1 hash matches the
                                live content in LF or CRLF form)
            CHANGED_AUTHORIZED  a v1 path whose content changed since v1
            NEW_IN_V2           a protected or frozen path that v1 did not cover
                                (baseline = the commit the record was made at)
  authority "v1" for unchanged rows; otherwise every commit since the v1 base
            that touched the file (git log), mapped through AUTHORITY below.
            An unmapped commit stops the script.

    python scripts/integrity_record.py --print    # show the generated record (needs git)
    python scripts/integrity_record.py --write    # write docs/m1-integrity-v2.sha256 (needs git)
    python scripts/integrity_record.py --check    # verify live files; no git needed

--check exits 1 if any listed file is missing or its sha256 (computed as above)
differs from the record. Stdlib only.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V1_RECORD = ROOT / "docs" / "p06-post-p02-integrity.sha256"
V2_RECORD = ROOT / "docs" / "m1-integrity-v2.sha256"

V1_BASE = "b4ef009ab309372d1cd683145684a313696fa06a"      # v1 git_head
PUBLIC_BASE = "5b82915bf3d5be089c046f99b2d1b6b9133a34f0"  # tag v1.0-round2

# PROTECTED in P05a (in addition to the v1 paths). Explicit, so that a new file
# never enters the record silently.
PROTECTED = (
    "controlplane/intercept.py",
    "controlplane/manifest.py",
    "controlplane/decide.py",
    "schemas/manifest.schema.json",
    "manifests/discount_approval.yaml",
    "manifests/knowledge_assistant.yaml",
    "manifests/service_credit_approval.yaml",
    "manifests/servicing.yaml",
    "manifests/tau2_cancel_pending_order.yaml",
    "manifests/tau2_exchange_delivered_order_items.yaml",
    "manifests/tau2_modify_pending_order_address.yaml",
    "manifests/tau2_modify_pending_order_items.yaml",
    "manifests/tau2_modify_pending_order_payment.yaml",
    "manifests/tau2_return_delivered_order_items.yaml",
    "tests/test_manifest_hardening.py",
)

# FROZEN tracked files that v1 did not cover (P05a D-1).
FROZEN_EXTRA = (
    "bench/label.py",
    "bench/extraction_gold_v1.jsonl",
    "reports/README.md",
    "reports/evidence-ablation-absence.png",
    "reports/evidence-ablation-staleness.png",
    "reports/extraction-completeness-v1.json",
    "reports/extraction-completeness-v1.md",
    "reports/foundational-requirement-coverage-v1.json",
    "reports/foundational-requirement-coverage-v1.md",
    "reports/manifest-claim-coverage.md",
    "reports/tau2-bench.md",
    "reports/verification-coverage.md",
)

# Files with these suffixes are hashed LF-normalised; all others as raw bytes.
TEXT_SUFFIXES = (".py", ".md", ".json", ".jsonl", ".csv", ".yaml", ".yml", ".txt",
                 ".sha256", ".toml", ".sh", ".ps1")

# Commits after the v1 base that may change a protected file, and the decision
# that authorised each. Every commit that is already in PUBLIC_BASE maps to
# PUBLIC_LABEL (see _authority).
AUTHORITY = {
    "00ca015": "D-M1-01 (00ca015)",
    "356ec58": "D-M1-02 (356ec58)",
    "678b566": "P03 local commit, decision D10 (678b566)",
    "a5549b7": "P03 local commit, decision D10; P3-A (a5549b7)",
    "6c2ca5a": "P03 local commit, decision D10 (6c2ca5a)",
    "eed05d9": "P03 local commit, decision D10; P3-D to P3-G (eed05d9)",
}
PUBLIC_LABEL = "pre-M1 public history, in v1.0-round2 (5b82915)"

STATUSES = ("UNCHANGED_SINCE_V1", "CHANGED_AUTHORIZED", "NEW_IN_V2")


class RecordError(Exception):
    pass


def lf_bytes(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def is_text(path: str | Path) -> bool:
    return Path(path).suffix.lower() in TEXT_SUFFIXES


def normalised(path: Path) -> bytes:
    data = path.read_bytes()
    return lf_bytes(data) if is_text(path) else data


def sha256_lf(path: Path) -> str:
    """sha256 used by the record: LF-normalised for text suffixes, raw otherwise."""
    return hashlib.sha256(normalised(path)).hexdigest()


def _sha256_crlf(path: Path) -> str:
    if not is_text(path):
        return sha256_lf(path)
    return hashlib.sha256(normalised(path).replace(b"\n", b"\r\n")).hexdigest()


def read_v1() -> list[dict]:
    rows = []
    for line in V1_RECORD.read_bytes().decode("utf-8").replace("\r\n", "\n").split("\n"):
        if line and not line.startswith("#"):
            original, current, status, path, reason = line.split(maxsplit=4)
            rows.append({"original": original, "current": current, "status": status,
                         "path": path, "reason": reason})
    return rows


def read_v2(record: Path = V2_RECORD) -> list[dict]:
    rows = []
    for line in record.read_bytes().decode("utf-8").replace("\r\n", "\n").split("\n"):
        if line and not line.startswith("#"):
            sha, status, path, authority = line.split(maxsplit=3)
            rows.append({"sha256_lf": sha, "status": status, "path": path, "authority": authority})
    return rows


def planned_paths() -> list[str]:
    v1 = [r["path"] for r in read_v1()]
    return v1 + sorted({p for p in PROTECTED + FROZEN_EXTRA if p not in v1})


def _git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def _authority(commit: str) -> str:
    for short, label in AUTHORITY.items():
        if commit.startswith(short):
            return label
    in_public = subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor",
                                commit, PUBLIC_BASE]).returncode == 0
    if in_public:
        return PUBLIC_LABEL
    raise RecordError(f"commit {commit[:7]} is not mapped to a decision in AUTHORITY")


def generate() -> tuple[str, list[dict]]:
    head = _git("rev-parse", "HEAD")
    v1 = {r["path"]: r for r in read_v1()}
    rows = []
    for path in planned_paths():
        f = ROOT / path
        if not f.is_file():
            raise RecordError(f"missing: {path}")
        blob = subprocess.run(["git", "-C", str(ROOT), "cat-file", "blob", f"HEAD:{path}"],
                              check=True, capture_output=True).stdout
        if normalised(f) != (lf_bytes(blob) if is_text(path) else blob):
            raise RecordError(f"{path}: working file differs from HEAD; commit or revert first")
        commits = _git("log", "--format=%H", f"{V1_BASE}..HEAD", "--", path).split()
        labels = list(dict.fromkeys(_authority(c) for c in reversed(commits)))
        lf = sha256_lf(f)
        if path in v1:
            row = v1[path]
            if row["current"] in (lf, _sha256_crlf(f)):
                status, authority = "UNCHANGED_SINCE_V1", "v1"
            else:
                if not labels:
                    raise RecordError(f"{path}: changed since v1 but no commit touched it")
                status = "CHANGED_AUTHORIZED"
                prior = [f"v1: {row['reason']}"] if row["status"] == "AUTHORIZED_CHANGE" else []
                authority = "; ".join(prior + labels)
        else:
            status = "NEW_IN_V2"
            authority = "; ".join([f"baseline {head[:7]}"] + labels)
        rows.append({"sha256_lf": lf, "status": status, "path": path, "authority": authority})
    header = [
        "# M1 integrity record v2 (P05a; PR-02; decisions P05 V6, V7)",
        f"# created: {date.today().isoformat()}",
        f"# base commit: {head}",
        f"# v1 base: {V1_BASE} (docs/p06-post-p02-integrity.sha256, kept unchanged)",
        "# method: sha256; files with suffix " + " ".join(TEXT_SUFFIXES)
        + " are hashed with every CRLF replaced by LF (no other change); all other files as raw bytes",
        "# columns: sha256_lf  status  path  authority",
    ]
    text = "\n".join(header + [f"{r['sha256_lf']}  {r['status']}  {r['path']}  {r['authority']}"
                               for r in rows]) + "\n"
    return text, rows


def check(record: Path = V2_RECORD) -> list[str]:
    problems = []
    for row in read_v2(record):
        f = ROOT / row["path"]
        if row["status"] not in STATUSES:
            problems.append(f"{row['path']}: unknown status {row['status']}")
        if not f.is_file():
            problems.append(f"{row['path']}: missing")
        elif sha256_lf(f) != row["sha256_lf"]:
            problems.append(f"{row['path']}: sha256_lf differs from the record")
    return problems


def main(argv: list[str]) -> int:
    if argv not in (["--print"], ["--write"], ["--check"]):
        print(__doc__)
        return 2
    try:
        if argv == ["--check"]:
            problems = check()
            for p in problems:
                print("FAIL:", p)
            print("check:", "OK" if not problems else f"{len(problems)} problem(s)",
                  f"({len(read_v2())} rows)")
            return 1 if problems else 0
        text, rows = generate()
    except (RecordError, subprocess.CalledProcessError, OSError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    if argv == ["--write"]:
        V2_RECORD.write_bytes(text.encode("utf-8"))
        print(f"wrote {V2_RECORD.relative_to(ROOT).as_posix()} ({len(rows)} rows)")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
