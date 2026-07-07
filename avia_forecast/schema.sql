-- Avia Global Aviation Forecast - database schema (Data Architecture 2.1-2.2)
-- Author: Avia Solutions. Local SQLite; large fact frames also mirrored to parquet.

-- ---- Reference tables (2.1) ----
CREATE TABLE IF NOT EXISTS airports (
  iata TEXT PRIMARY KEY, icao TEXT, country TEXT, world_region TEXT,
  catchment_group_id TEXT, hub_flag INTEGER, base_year_conx_share REAL,
  segment_mapping TEXT, modelled_from_vintage TEXT
);
CREATE TABLE IF NOT EXISTS countries (
  country TEXT PRIMARY KEY, region TEXT, maturity_class TEXT, currency TEXT
);
CREATE TABLE IF NOT EXISTS region_map_external (
  model_region TEXT, scheme TEXT, external_region TEXT   -- GMF/CMO/IATA (7.4)
);
CREATE TABLE IF NOT EXISTS catchments (
  catchment_group_id TEXT, iata TEXT
);
-- Two-field design (Capacity Register - Design and Sourcing v0.1). One row per
-- airport; k_grade selects which capacity kind exists. practical_capacity kept
-- as the engine-facing derived annual K (pax/yr), so downstream code that reads
-- practical_capacity is unchanged.
CREATE TABLE IF NOT EXISTS capacity_register (
  iata TEXT, year INTEGER,
  k_grade TEXT,
  declared_mvts_per_hr REAL,
  operating_hours REAL,
  seats_per_mvt REAL, load_factor REAL,
  design_annual_pax_m REAL,
  k_annual_pax_m REAL,
  peak_spreading REAL,
  practical_capacity REAL,
  committed_steps TEXT,
  development_step TEXT, source_id TEXT, confidence_grade TEXT, notes TEXT
);
CREATE TABLE IF NOT EXISTS events (
  iata TEXT, year INTEGER, event_type TEXT, magnitude_note TEXT,
  treatment_flag TEXT   -- TEMPORARY (single-year dummy) | STRUCTURAL (level shift)
);
CREATE TABLE IF NOT EXISTS sources (
  source_id TEXT PRIMARY KEY, name TEXT, url TEXT, licence_class TEXT,
  redistribution_rights TEXT, refresh_cycle TEXT, cost TEXT, contact TEXT
);

-- ---- Fact tables (2.2), tidy contract (Method Spec 2.2) ----
CREATE TABLE IF NOT EXISTS traffic_history (
  iata TEXT, dest_region TEXT, direction TEXT, metric TEXT, year INTEGER,
  value REAL, source_id TEXT, synthetic_flag INTEGER, revision_date TEXT
);
CREATE TABLE IF NOT EXISTS drivers (
  geography TEXT, metric TEXT, scenario TEXT, year INTEGER,
  value REAL, source_id TEXT, vintage TEXT
);
CREATE TABLE IF NOT EXISTS forecasts (
  iata TEXT, dest_region TEXT, direction TEXT, metric TEXT, year INTEGER,
  scenario TEXT, vintage TEXT, constrained_flag INTEGER, value REAL
);
CREATE TABLE IF NOT EXISTS assumptions_book (
  parameter TEXT, scenario TEXT, vintage TEXT, value TEXT
);
CREATE TABLE IF NOT EXISTS change_log (
  date TEXT, author TEXT, description TEXT, affected_outputs TEXT, approval TEXT
);

-- Estimation test trail (Elasticity Design 8): one row per cell per vintage.
CREATE TABLE IF NOT EXISTS estimation_trail (
  iata TEXT, dest_region TEXT, direction TEXT, vintage TEXT,
  level INTEGER, bG REAL, bF REAL, gamma REAL, se_bG REAL, se_bF REAL,
  t_bG REAL, t_bF REAL, r2 REAL, durbin_watson REAL, n_obs INTEGER,
  spec_used TEXT, T1 INTEGER, T2 INTEGER, T3 INTEGER, T4 INTEGER, T5 INTEGER, T6 INTEGER,
  bG_implied REAL, t6_window TEXT,
  bG_applied REAL, bF_applied REAL, clipped INTEGER, reason_code TEXT
);
