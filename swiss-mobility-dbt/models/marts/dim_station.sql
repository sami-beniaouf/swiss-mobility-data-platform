with stations as (

    select * from {{ ref('stg_oracle__stations') }}

),

cantons as (

    select * from {{ ref('stg_oracle__cantons') }}

)

select
    s.station_id,
    s.station_name,
    s.municipality_bfs_nr,
    s.canton_code,
    coalesce(c.canton_name, 'Unknown')      as canton_name,
    coalesce(c.language_region, 'Unknown')  as language_region,
    s.lv95_e,
    s.lv95_n,
    -- WGS84 for map visuals (Power BI expects latitude/longitude)
    cast({{ lv95_to_wgs84_lat('s.lv95_e', 's.lv95_n') }} as decimal(9, 6))  as latitude,
    cast({{ lv95_to_wgs84_lon('s.lv95_e', 's.lv95_n') }} as decimal(9, 6))  as longitude
from stations s
left join cantons c
    on s.canton_code = c.canton_code
