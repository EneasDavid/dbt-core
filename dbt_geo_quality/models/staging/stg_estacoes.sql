{{ config(enabled=false) }}

-- This file is intentionally disabled.
-- Reading "Estacoes ferroviarias.shp" in dbt would require SQL spatial functions such as ST_Read(...)
-- or a custom adapter/plugin loader, which violates the "no custom SQL" rule used in this assessment.

select 1 as placeholder_estacoes
