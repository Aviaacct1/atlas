"""ingest/ - one adapter per source (Data Architecture 5.1).
Each adapter writes to traffic_history/drivers with source ids and validation
(non-negative, continuity, unit checks). Adapters are the only code that knows
source formats. Author: Avia Solutions.
"""
