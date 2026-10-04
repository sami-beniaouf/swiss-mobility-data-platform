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
    s.lv95_n
from stations s
left join cantons c
    on s.canton_code = c.canton_code
