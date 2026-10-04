-- Singular test: delays outside a plausible range point to a parsing bug in the
-- ingestion notebook. Returns offending rows; the test fails if any are found.

select
    departure_id,
    station_id,
    departure_planned_utc,
    delay_min
from {{ ref('stg_transport__departures') }}
where delay_min < -10
   or delay_min > 600
