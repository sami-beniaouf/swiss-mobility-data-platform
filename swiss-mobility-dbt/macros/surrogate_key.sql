{#
  T-SQL surrogate key (MD5 hex, 32 chars).
  Written by hand instead of dbt_utils to stay independent of cross-db shims.
  Usage: {{ surrogate_key(['col_a', 'col_b']) }}
#}
{% macro surrogate_key(columns) -%}
    convert(
        varchar(32),
        hashbytes(
            'MD5',
            concat_ws('|',
                {%- for col in columns %}
                coalesce(cast({{ col }} as varchar(200)), '_null_'){% if not loop.last %},{% endif %}
                {%- endfor %}
            )
        ),
        2
    )
{%- endmacro %}
