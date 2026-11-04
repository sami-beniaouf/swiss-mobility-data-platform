-- Singular test: delays outside a plausible range point to a parsing bug in the ingestion
-- (src/ingestion). Profiling (notebooks/05_bronze_profiling.ipynb) observed delays between
-- 0 and 58 minutes and no negative value: the API does not report early departures.
-- The upper bound leaves room for major disruptions. Returns offending rows; the test
-- fails if any are found.

select
    departure_id,
    station_id,
    departure_planned_utc,
    delay_min
from {{ ref('stg_transport__departures') }}
where delay_min < 0
   or delay_min > 300
