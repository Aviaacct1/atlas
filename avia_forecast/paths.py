"""Central data-root resolver. Author: Avia Solutions.

Every data location the engine and the build scripts read resolves through here, so the
code runs on any machine. Resolution order per root:
  1. environment variable (set these on a server or CI to point anywhere);
  2. the Windows working locations on John's machine;
  3. the Cowork sandbox mount (so it still runs inside a build session).
The first path that exists wins; if none exist yet, the first candidate (the Windows
default) is returned, so a fresh machine points at the intended location.

Override examples (Windows):  set AVIA_GLOBAL_ROOT=D:\Avia\Global
                              set AVIA_DB_ROOT=C:\Avia
                              set AVIA_QSI_APP=C:\...\Avia QSI Tool\app
"""
import os


def _first(cands):
    for c in cands:
        if c and os.path.exists(c):
            return c
    return cands[0]


GLOBAL = os.environ.get("AVIA_GLOBAL_ROOT") or _first([
    r"E:\Avia\Global",
    "/sessions/relaxed-friendly-bohr/mnt/Global",
])
AVIA = os.environ.get("AVIA_DB_ROOT") or _first([
    r"C:\Avia",
    "/sessions/relaxed-friendly-bohr/mnt/Avia",
])
QSI_APP = os.environ.get("AVIA_QSI_APP") or _first([
    r"C:\Users\Carte\OneDrive\Documents\Claude\Projects\Avia QSI Tool\app",
    "/sessions/relaxed-friendly-bohr/mnt/Avia QSI Tool/app",
])

DATA = os.path.join(GLOBAL, "data")
OEF_DIR = os.path.join(GLOBAL, "OEF")
ACI_DIR = os.path.join(GLOBAL, "ACI")
ACI_DECRYPT = os.path.join(DATA, "aci_decrypted")
SABRE_DB = os.path.join(AVIA, "sabre.duckdb")
OAG_DB = os.path.join(AVIA, "oag.duckdb")
QSI_REF = os.path.join(QSI_APP, "reference_tables", "airport_city_country.csv")
PREAGG = os.path.join(QSI_APP, "preagg.duckdb")
OEF_GDP_XLSX = os.path.join(OEF_DIR, "OEF GDP Forecast 31Jul2024 - GDP per CAP added (AR 08Oct2024).xlsx")
