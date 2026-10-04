-- Grain: one scheduled departure at one station.

select
    departure_id,
    station_id,
    {{ surrogate_key(['category', 'line_number', 'operator']) }}   as line_key,
    cast(convert(varchar(8), departure_date_local, 112) as int)     as date_key,
    departure_planned_local,
    departure_hour_local,
    destination,
    platform,
    delay_min,
    has_realtime,
    is_punctual
from {{ ref('int_departures__enriched') }}
