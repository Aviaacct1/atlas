"""One command: full per-airport estimation diagnostics, then rebuild the dashboard and cockpit
bundles. Requires the data root (E: on John's machine / the mounted Global drive). Author: Avia Solutions."""
import os, sys, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
def step(name, *cmd):
    print("\n=== " + name + " ===")
    subprocess.run([sys.executable, os.path.join(HERE, cmd[0]), *cmd[1:]], check=True)
step("1/3 per-airport regression diagnostics", "estimate_airport_diagnostics.py")
step("2/3 dashboard bundle", "build_dashboard_data.py")
step("3/3 cockpit bundle", "build_cockpit_data.py")
print("\nDone. The Econometrics tab now shows real R2, t and observed scatter per airport.")
