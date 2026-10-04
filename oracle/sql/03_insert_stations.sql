-- Station ids and WGS84 coordinates from transport.opendata.ch (/v1/locations),
-- converted to LV95 with the swisstopo approximation formulas (~1 m accuracy).

WHENEVER SQLERROR EXIT FAILURE

INSERT INTO stations (station_id, station_name, municipality_bfs_nr, canton_code, lv95_e, lv95_n) VALUES ('8504300', 'Biel/Bienne', 371, 'BE', 2585151.73, 1220231.08);
INSERT INTO stations (station_id, station_name, municipality_bfs_nr, canton_code, lv95_e, lv95_n) VALUES ('8507000', 'Bern', 351, 'BE', 2600037.33, 1199748.79);
INSERT INTO stations (station_id, station_name, municipality_bfs_nr, canton_code, lv95_e, lv95_n) VALUES ('8503000', 'Zürich HB', 261, 'ZH', 2683212.09, 1248029.61);
INSERT INTO stations (station_id, station_name, municipality_bfs_nr, canton_code, lv95_e, lv95_n) VALUES ('8504221', 'Neuchâtel', 6458, 'NE', 2561746.61, 1205197.48);
INSERT INTO stations (station_id, station_name, municipality_bfs_nr, canton_code, lv95_e, lv95_n) VALUES ('8501120', 'Lausanne', 5586, 'VD', 2537874.64, 1152042.74);
INSERT INTO stations (station_id, station_name, municipality_bfs_nr, canton_code, lv95_e, lv95_n) VALUES ('8501008', 'Genève', 6621, 'GE', 2499967.85, 1118469.78);
INSERT INTO stations (station_id, station_name, municipality_bfs_nr, canton_code, lv95_e, lv95_n) VALUES ('8500010', 'Basel SBB', 2701, 'BS', 2611363.00, 1266308.94);
INSERT INTO stations (station_id, station_name, municipality_bfs_nr, canton_code, lv95_e, lv95_n) VALUES ('8504100', 'Fribourg/Freiburg', 2196, 'FR', 2578046.18, 1183594.04);
INSERT INTO stations (station_id, station_name, municipality_bfs_nr, canton_code, lv95_e, lv95_n) VALUES ('8504314', 'La Chaux-de-Fonds', 6421, 'NE', 2553490.86, 1216556.65);
INSERT INTO stations (station_id, station_name, municipality_bfs_nr, canton_code, lv95_e, lv95_n) VALUES ('8500109', 'Delémont', 6711, 'JU', 2593310.00, 1245689.06);
INSERT INTO stations (station_id, station_name, municipality_bfs_nr, canton_code, lv95_e, lv95_n) VALUES ('8505000', 'Luzern', 1061, 'LU', 2666223.16, 1211382.38);
INSERT INTO stations (station_id, station_name, municipality_bfs_nr, canton_code, lv95_e, lv95_n) VALUES ('8505300', 'Lugano', 5192, 'TI', 2716838.99, 1096004.72);
INSERT INTO stations (station_id, station_name, municipality_bfs_nr, canton_code, lv95_e, lv95_n) VALUES ('8500218', 'Olten', 2581, 'SO', 2635441.47, 1244669.72);
INSERT INTO stations (station_id, station_name, municipality_bfs_nr, canton_code, lv95_e, lv95_n) VALUES ('8501506', 'Sion', 6266, 'VS', 2593869.35, 1119569.86);
INSERT INTO stations (station_id, station_name, municipality_bfs_nr, canton_code, lv95_e, lv95_n) VALUES ('8509000', 'Chur', 3901, 'GR', 2759397.02, 1191227.64);
INSERT INTO stations (station_id, station_name, municipality_bfs_nr, canton_code, lv95_e, lv95_n) VALUES ('8506302', 'St. Gallen', 3203, 'SG', 2745711.96, 1254277.91);

COMMIT;
EXIT
