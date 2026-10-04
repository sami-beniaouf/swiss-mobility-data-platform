-- Reference tables of the "Oracle data hub".
-- Fabric copies them to the Lakehouse as oracle_cantons / oracle_stations
-- (see swiss-mobility-dbt/models/staging/_sources.yml).

WHENEVER SQLERROR EXIT FAILURE

CREATE TABLE cantons (
    canton_code      VARCHAR2(2)    NOT NULL,
    canton_name      VARCHAR2(100)  NOT NULL,
    language_region  VARCHAR2(20)   NOT NULL,
    CONSTRAINT pk_cantons PRIMARY KEY (canton_code),
    CONSTRAINT ck_cantons_language CHECK (
        language_region IN ('German', 'French', 'Italian', 'Bilingual', 'Multilingual')
    )
);

CREATE TABLE stations (
    station_id           VARCHAR2(20)   NOT NULL,   -- BPUIC/DIDOK, same id as transport.opendata.ch
    station_name         VARCHAR2(200)  NOT NULL,
    municipality_bfs_nr  NUMBER(5)      NOT NULL,   -- official BFS municipality number
    canton_code          VARCHAR2(2)    NOT NULL,
    lv95_e               NUMBER(10, 2)  NOT NULL,   -- EPSG:2056 easting
    lv95_n               NUMBER(10, 2)  NOT NULL,   -- EPSG:2056 northing
    updated_at           TIMESTAMP      DEFAULT SYSTIMESTAMP NOT NULL,
    CONSTRAINT pk_stations PRIMARY KEY (station_id),
    CONSTRAINT fk_stations_canton FOREIGN KEY (canton_code) REFERENCES cantons (canton_code),
    CONSTRAINT ck_stations_lv95 CHECK (
        lv95_e BETWEEN 2480000 AND 2840000 AND lv95_n BETWEEN 1070000 AND 1300000
    )
);

COMMENT ON TABLE stations IS 'Main Swiss railway stations used as reference for the departures API';
COMMENT ON TABLE cantons IS 'Swiss cantons with their official language region';

EXIT
