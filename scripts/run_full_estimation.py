"""One command: full rebuild of the served data bundles from the engine. Author: Avia Solutions.

Requires the data root (E:\\Avia\\Global on John's machine; the resolver finds it). Steps, in order:
  1. per-airport regression diagnostics (airport_regress.json) - the gated elasticity ladder reads it
  2. connecting throughput measured from Sabre legs (connecting_sabre_2024.json)
  3. dashboard bundle - RUNS THE ENGINE (gated per-airport elasticities, connecting-residual
     reconciliation, ACI-based coverage, adding-up checks) -> dashboard.json
  3. cockpit bundle (gated applied elasticity + provenance) -> cockpit.json
  4. BUM candidates -> bum_candidates.json
  5. validity gate: every served JSON parses and no absolute sandbox paths remain
Every write is atomic with a parse-back check, so an interrupted run cannot truncate a served file.
(world.json/airports.json/meta.json for the simple viewer are optional: add build_webapp_data.py if needed.)
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def step(name, script, *args):
    print("\n=== " + name + " ===")
    subprocess.run([sys.executable, os.path.join(HERE, script), *args], check=True)


step("1/6 per-airport regression diagnostics", "estimate_airport_diagnostics.py")
step("2/6 connecting (leg-measured from Sabre)", "build_connecting_sabre.py")
step("3/6 dashboard bundle (engine run)", "build_dashboard_data.py")
step("4/6 cockpit bundle", "build_cockpit_data.py")
step("5/6 BUM candidates", "build_bum_candidates.py")

print("\n=== 6/6 validity gate ===")
rc = subprocess.run([sys.executable, os.path.join(HERE, "validate_repo.py")]).returncode
if rc != 0:
    print("\nREBUILD PRODUCED INVALID JSON - see the lines above. The served files were NOT overwritten\n"
          "with anything invalid (atomic writes), so the previous state is intact. Fix and re-run.")
    sys.exit(rc)
print("\nRebuild complete and validated. Refresh the dashboard and the cockpit.")
