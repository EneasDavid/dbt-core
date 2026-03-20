{{ config(enabled=false) }}

-- This file is intentionally disabled.
-- Reading "Ferrovias_IBGE 2022_AL.shp" in dbt would require SQL spatial functions such as ST_Read(...)
-- or a custom adapter/plugin loader, which violates the "no custom SQL" rule used in this assessment.

select 1 as placeholder_ferrovias
