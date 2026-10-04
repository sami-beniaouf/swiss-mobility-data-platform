select distinct
    {{ surrogate_key(['category', 'line_number', 'operator']) }}   as line_key,
    category,
    line_number,
    operator,
    transport_mode
from {{ ref('int_departures__enriched') }}
