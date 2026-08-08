r"""Atlas host check: does this machine have everything the tool needs to run.

Why this exists. A clone plus a data root is not a runnable host. On the Meridian
migration on 8 August 2026 that assumption cost an hour, and pip reported a broken
install as a warning and exited zero, so nothing failed loudly. This exits non-zero
when something required is missing or broken, and it names what and where.

Run it as the last step of provisioning any host, and again after any pip install:

    py -3.12 check_env.py

Author: Avia Solutions.
"""
from __future__ import annotations
import importlib
import os
import sys

REPO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO)

FAILURES: list[str] = []
WARNINGS: list[str] = []


def fail(msg: str) -> None:
    FAILURES.append(msg)
    print("  FAIL  " + msg)


def warn(msg: str) -> None:
    WARNINGS.append(msg)
    print("  WARN  " + msg)


def ok(msg: str) -> None:
    print("  ok    " + msg)


# --- 1. interpreter and virtual environment ---------------------------------
print("\n1. Interpreter")
print(f"  python {sys.version.split()[0]} at {sys.executable}")
if sys.version_info < (3, 11):
    fail(f"python {sys.version_info.major}.{sys.version_info.minor}: 3.11 or later is required")
else:
    ok("version")
in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
if in_venv:
    ok("virtual environment: yes")
else:
    warn("virtual environment: NO, this is a shared Python. Installing one tool's "
         "dependencies here changes every other tool that uses this interpreter. "
         "The workstation runs several Avia tools, so give each one its own.")

# --- 2. required packages ----------------------------------------------------
print("\n2. Packages")
for mod in ("numpy", "pandas", "statsmodels", "duckdb", "openpyxl", "yaml"):
    try:
        m = importlib.import_module(mod)
        ok(f"{mod} {getattr(m, '__version__', '(no version attribute)')}")
    except Exception as e:
        fail(f"{mod}: {type(e).__name__}: {e}")

# --- 3. data roots -----------------------------------------------------------
print("\n3. Data roots (avia_forecast/paths.py)")
try:
    from avia_forecast import paths
except Exception as e:
    fail(f"cannot import avia_forecast.paths: {type(e).__name__}: {e}")
    paths = None

if paths is not None:
    for name, value, var in (
        ("global root", paths.GLOBAL, "AVIA_GLOBAL_ROOT"),
        ("store root", paths.AVIA, "AVIA_DB_ROOT"),
        ("Meridian app", paths.QSI_APP, "AVIA_QSI_APP"),
    ):
        if os.path.isdir(value):
            ok(f"{name}: {value}")
        else:
            fail(f"{name}: {value} does not exist. Set {var} to the right location.")

    print("\n4. Data the engine loads, and fails silently without")
    required = [
        (paths.DATA, "estimated_bG_by_country.json", "per-country income elasticity; "
         "without it every country falls back to the default"),
        (paths.DATA, "oef_gdp_pop_by_iso2.json", "OEF GDP and population; without it "
         "the forecast falls back to the regional growth default"),
        (paths.DATA, "aci_hub_calibration_2024.json", "per-airport connecting share"),
        (os.path.join(REPO, "data"), "airport_regress.json", "airport regression; this "
         "file is gitignored, so a fresh clone will not have it"),
        (os.path.join(REPO, "data"), "fare_index_constructed.json", "the fare index"),
        (os.path.join(REPO, "data"), "bt2_model_v1_2.pkl", "the promoted BT2 model"),
    ]
    for root, fn, why in required:
        p = os.path.join(root, fn)
        if os.path.isfile(p):
            ok(f"{fn}")
        else:
            fail(f"{fn} not at {p}: {why}")

    for label, p in (("OAG store", paths.OAG_DB), ("Sabre store", paths.SABRE_DB)):
        if os.path.isfile(p):
            ok(f"{label}: {p}")
        else:
            warn(f"{label} not at {p}. Ingest and the back-tests need it; the pilot "
                 f"forecast does not.")

# --- 5. configuration --------------------------------------------------------
print("\n5. Configuration")
try:
    from avia_forecast.config import assumptions, sources, regions
    a, s, r = assumptions(), sources(), regions()
    ok(f"assumptions book: {len(a)} top-level entries")
    ok(f"source register: {len(s)} entries")
    ok(f"regions: {len(r)} entries")
    store = (s.get("oag_schedules") or {}).get("store_path")
    if store and not os.path.isfile(store) and not os.environ.get("AVIA_OAG_STORE"):
        warn(f"sources.yaml oag_schedules.store_path points at {store}, which is not "
             f"here, and AVIA_OAG_STORE is not set")
except Exception as e:
    fail(f"configuration will not load: {type(e).__name__}: {e}")

# --- 6. smoke tests ----------------------------------------------------------
print("\n6. Smoke tests")
try:
    from avia_forecast import pipeline
    out = pipeline.run()
    ok(f"pilot pipeline ran: {type(out).__name__}")
except Exception as e:
    fail(f"pilot pipeline: {type(e).__name__}: {e}")

try:
    from avia_forecast.demand import core
    F = core.fare_path(100.0, [0.10, 0.0])
    ok(f"fare path: base 100 to {F[-1]:.2f} over two steps")
except Exception as e:
    fail(f"fare path: {type(e).__name__}: {e}")

try:
    import subprocess
    rc = subprocess.call([sys.executable, os.path.join(REPO, "scripts", "validate_repo.py")])
    if rc == 0:
        ok("repository check (the pre-commit hook) passes")
    else:
        fail("repository check failed; see the output above")
except Exception as e:
    fail(f"repository check would not run: {type(e).__name__}: {e}")

# --- verdict -----------------------------------------------------------------
print("\n" + "=" * 70)
if FAILURES:
    print(f"NOT READY: {len(FAILURES)} failure(s), {len(WARNINGS)} warning(s)")
    for f in FAILURES:
        print("  - " + f)
    sys.exit(1)
print(f"READY: 0 failures, {len(WARNINGS)} warning(s)")
if WARNINGS:
    for w in WARNINGS:
        print("  - " + w)
sys.exit(0)
