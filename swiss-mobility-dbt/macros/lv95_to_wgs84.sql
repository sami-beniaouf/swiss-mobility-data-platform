{#
  Swiss LV95 (EPSG:2056) to WGS84 (EPSG:4326), with the approximate formulas published by
  swisstopo ("Approximate formulas for the transformation between Swiss projection
  coordinates and WGS84"). Accuracy about 1 metre, enough for maps.

  Usage: {{ lv95_to_wgs84_lat('lv95_e', 'lv95_n') }}, {{ lv95_to_wgs84_lon('lv95_e', 'lv95_n') }}
#}

{# Auxiliary values: projection coordinates relative to Bern, in 1000 km #}
{% macro _lv95_y(e) %}(({{ e }} - 2600000.0) / 1000000.0){% endmacro %}
{% macro _lv95_x(n) %}(({{ n }} - 1200000.0) / 1000000.0){% endmacro %}

{% macro lv95_to_wgs84_lat(e, n) -%}
    {%- set y = _lv95_y(e) -%}
    {%- set x = _lv95_x(n) -%}
    (
        16.9023892
        + 3.238272 * {{ x }}
        - 0.270978 * {{ y }} * {{ y }}
        - 0.002528 * {{ x }} * {{ x }}
        - 0.0447   * {{ y }} * {{ y }} * {{ x }}
        - 0.0140   * {{ x }} * {{ x }} * {{ x }}
    ) * 100.0 / 36.0
{%- endmacro %}

{% macro lv95_to_wgs84_lon(e, n) -%}
    {%- set y = _lv95_y(e) -%}
    {%- set x = _lv95_x(n) -%}
    (
        2.6779094
        + 4.728982 * {{ y }}
        + 0.791484 * {{ y }} * {{ x }}
        + 0.1306   * {{ y }} * {{ x }} * {{ x }}
        - 0.0436   * {{ y }} * {{ y }} * {{ y }}
    ) * 100.0 / 36.0
{%- endmacro %}
