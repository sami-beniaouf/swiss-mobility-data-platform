-- Singular test: every station converted to WGS84 must fall inside the bounding box of
-- Switzerland (latitude 45.8 to 47.9, longitude 5.9 to 10.6). A point outside it means a
-- wrong LV95 coordinate in the hub or an error in the conversion macro.

select station_id, station_name, latitude, longitude
from {{ ref('dim_station') }}
where latitude  not between 45.8 and 47.9
   or longitude not between 5.9 and 10.6
