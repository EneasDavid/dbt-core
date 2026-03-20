{{ config(enabled=false) }}

-- This file is intentionally disabled.
-- A native dbt Core model cannot inspect local shapefile metadata without SQL or custom Python.
-- Keeping the placeholder makes the limitation visible in the project structure requested by the user.

select 1 as placeholder_dataset_metadata
