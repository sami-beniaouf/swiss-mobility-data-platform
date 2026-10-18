-- Load script for the Oracle Autonomous AI Database (cloud hub).
-- Run once as ADMIN in Database Actions > SQL, with Run Script (F5).
-- Objects are created in the MOBILITY schema using schema-qualified names,
-- so the result does not depend on the session's current schema.
-- Same DDL and data as oracle/sql/*.sql (local Docker hub). Re-runnable: existing tables are dropped first.

DROP TABLE IF EXISTS mobility.stations;
DROP TABLE IF EXISTS mobility.cantons;
DROP TABLE IF EXISTS admin.stations;      -- leftovers from earlier attempts, if any
DROP TABLE IF EXISTS admin.cantons;

-- ===== 01_create_tables.sql =====
-- Reference tables of the "Oracle data hub".
-- Fabric copies them to the Lakehouse as oracle_cantons / oracle_stations
-- (see swiss-mobility-dbt/models/staging/_sources.yml).

CREATE TABLE mobility.cantons (
    canton_code      VARCHAR2(2)    NOT NULL,
    canton_name      VARCHAR2(100)  NOT NULL,
    language_region  VARCHAR2(20)   NOT NULL,
    CONSTRAINT pk_cantons PRIMARY KEY (canton_code),
    CONSTRAINT ck_cantons_language CHECK (
        language_region IN ('German', 'French', 'Italian', 'Bilingual', 'Multilingual')
    )
);

CREATE TABLE mobility.stations (
    station_id           VARCHAR2(20)   NOT NULL,   -- BPUIC/DIDOK, same id as transport.opendata.ch
    station_name         VARCHAR2(200)  NOT NULL,
    municipality_bfs_nr  NUMBER(5)      NOT NULL,   -- official BFS municipality number
    canton_code          VARCHAR2(2)    NOT NULL,
    lv95_e               NUMBER(10, 2)  NOT NULL,   -- EPSG:2056 easting
    lv95_n               NUMBER(10, 2)  NOT NULL,   -- EPSG:2056 northing
    updated_at           TIMESTAMP      DEFAULT SYSTIMESTAMP NOT NULL,
    CONSTRAINT pk_stations PRIMARY KEY (station_id),
    CONSTRAINT fk_stations_canton FOREIGN KEY (canton_code) REFERENCES mobility.cantons (canton_code),
    CONSTRAINT ck_stations_lv95 CHECK (
        lv95_e BETWEEN 2480000 AND 2840000 AND lv95_n BETWEEN 1070000 AND 1300000
    )
);

COMMENT ON TABLE mobility.stations IS 'Main Swiss railway stations used as reference for the departures API';
COMMENT ON TABLE mobility.cantons IS 'Swiss cantons with their official language region';

-- ===== 02_insert_cantons.sql =====
INSERT INTO mobility.cantons VALUES ('ZH', 'Zürich', 'German');
INSERT INTO mobility.cantons VALUES ('BE', 'Bern / Berne', 'Bilingual');
INSERT INTO mobility.cantons VALUES ('LU', 'Luzern', 'German');
INSERT INTO mobility.cantons VALUES ('UR', 'Uri', 'German');
INSERT INTO mobility.cantons VALUES ('SZ', 'Schwyz', 'German');
INSERT INTO mobility.cantons VALUES ('OW', 'Obwalden', 'German');
INSERT INTO mobility.cantons VALUES ('NW', 'Nidwalden', 'German');
INSERT INTO mobility.cantons VALUES ('GL', 'Glarus', 'German');
INSERT INTO mobility.cantons VALUES ('ZG', 'Zug', 'German');
INSERT INTO mobility.cantons VALUES ('FR', 'Fribourg / Freiburg', 'Bilingual');
INSERT INTO mobility.cantons VALUES ('SO', 'Solothurn', 'German');
INSERT INTO mobility.cantons VALUES ('BS', 'Basel-Stadt', 'German');
INSERT INTO mobility.cantons VALUES ('BL', 'Basel-Landschaft', 'German');
INSERT INTO mobility.cantons VALUES ('SH', 'Schaffhausen', 'German');
INSERT INTO mobility.cantons VALUES ('AR', 'Appenzell Ausserrhoden', 'German');
INSERT INTO mobility.cantons VALUES ('AI', 'Appenzell Innerrhoden', 'German');
INSERT INTO mobility.cantons VALUES ('SG', 'St. Gallen', 'German');
INSERT INTO mobility.cantons VALUES ('GR', 'Graubünden / Grischun / Grigioni', 'Multilingual');
INSERT INTO mobility.cantons VALUES ('AG', 'Aargau', 'German');
INSERT INTO mobility.cantons VALUES ('TG', 'Thurgau', 'German');
INSERT INTO mobility.cantons VALUES ('TI', 'Ticino', 'Italian');
INSERT INTO mobility.cantons VALUES ('VD', 'Vaud', 'French');
INSERT INTO mobility.cantons VALUES ('VS', 'Valais / Wallis', 'Bilingual');
INSERT INTO mobility.cantons VALUES ('NE', 'Neuchâtel', 'French');
INSERT INTO mobility.cantons VALUES ('GE', 'Genève', 'French');
INSERT INTO mobility.cantons VALUES ('JU', 'Jura', 'French');

COMMIT;

-- ===== 03_insert_stations.sql =====
-- Station ids and WGS84 coordinates from transport.opendata.ch (/v1/locations),
-- converted to LV95 with the swisstopo approximation formulas (~1 m accuracy).

INSERT INTO mobility.stations (station_id, station_name, municipality_bfs_nr, canton_code, lv95_e, lv95_n) VALUES ('8504300', 'Biel/Bienne', 371, 'BE', 2585151.73, 1220231.08);
INSERT INTO mobility.stations (station_id, station_name, municipality_bfs_nr, canton_code, lv95_e, lv95_n) VALUES ('8507000', 'Bern', 351, 'BE', 2600037.33, 1199748.79);
INSERT INTO mobility.stations (station_id, station_name, municipality_bfs_nr, canton_code, lv95_e, lv95_n) VALUES ('8503000', 'Zürich HB', 261, 'ZH', 2683212.09, 1248029.61);
INSERT INTO mobility.stations (station_id, station_name, municipality_bfs_nr, canton_code, lv95_e, lv95_n) VALUES ('8504221', 'Neuchâtel', 6458, 'NE', 2561746.61, 1205197.48);
INSERT INTO mobility.stations (station_id, station_name, municipality_bfs_nr, canton_code, lv95_e, lv95_n) VALUES ('8501120', 'Lausanne', 5586, 'VD', 2537874.64, 1152042.74);
INSERT INTO mobility.stations (station_id, station_name, municipality_bfs_nr, canton_code, lv95_e, lv95_n) VALUES ('8501008', 'Genève', 6621, 'GE', 2499967.85, 1118469.78);
INSERT INTO mobility.stations (station_id, station_name, municipality_bfs_nr, canton_code, lv95_e, lv95_n) VALUES ('8500010', 'Basel SBB', 2701, 'BS', 2611363.00, 1266308.94);
INSERT INTO mobility.stations (station_id, station_name, municipality_bfs_nr, canton_code, lv95_e, lv95_n) VALUES ('8504100', 'Fribourg/Freiburg', 2196, 'FR', 2578046.18, 1183594.04);
INSERT INTO mobility.stations (station_id, station_name, municipality_bfs_nr, canton_code, lv95_e, lv95_n) VALUES ('8504314', 'La Chaux-de-Fonds', 6421, 'NE', 2553490.86, 1216556.65);
INSERT INTO mobility.stations (station_id, station_name, municipality_bfs_nr, canton_code, lv95_e, lv95_n) VALUES ('8500109', 'Delémont', 6711, 'JU', 2593310.00, 1245689.06);
INSERT INTO mobility.stations (station_id, station_name, municipality_bfs_nr, canton_code, lv95_e, lv95_n) VALUES ('8505000', 'Luzern', 1061, 'LU', 2666223.16, 1211382.38);
INSERT INTO mobility.stations (station_id, station_name, municipality_bfs_nr, canton_code, lv95_e, lv95_n) VALUES ('8505300', 'Lugano', 5192, 'TI', 2716838.99, 1096004.72);
INSERT INTO mobility.stations (station_id, station_name, municipality_bfs_nr, canton_code, lv95_e, lv95_n) VALUES ('8500218', 'Olten', 2581, 'SO', 2635441.47, 1244669.72);
INSERT INTO mobility.stations (station_id, station_name, municipality_bfs_nr, canton_code, lv95_e, lv95_n) VALUES ('8501506', 'Sion', 6266, 'VS', 2593869.35, 1119569.86);
INSERT INTO mobility.stations (station_id, station_name, municipality_bfs_nr, canton_code, lv95_e, lv95_n) VALUES ('8509000', 'Chur', 3901, 'GR', 2759397.02, 1191227.64);
INSERT INTO mobility.stations (station_id, station_name, municipality_bfs_nr, canton_code, lv95_e, lv95_n) VALUES ('8506302', 'St. Gallen', 3203, 'SG', 2745711.96, 1254277.91);

COMMIT;

-- ===== checks =====
SELECT COUNT(*) AS cantons FROM mobility.cantons;      -- 26
SELECT COUNT(*) AS stations FROM mobility.stations;    -- 16
SELECT station_name FROM mobility.stations WHERE station_id = '8504221';   -- Neuchâtel
