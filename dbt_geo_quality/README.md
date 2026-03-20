## DBT Core x ISO 19157:2023

This project was initialized to test whether `dbt-core` can cover the 5 ISO 19157:2023 dimensions requested for the local dataset:

- `ferrovias-e-estacoes-ibge-2022/Ferrovias_IBGE 2022_AL.shp`
- `ferrovias-e-estacoes-ibge-2022/Estacoes ferroviarias.shp`

## Important constraint used in this assessment

The acceptance rule is strict:

- the function must exist in the library itself, or in an extension/plugin of that library
- the function must not depend on custom SQL logic
- the function must not depend on custom Python logic inside dbt

Under that rule, this repository is expected to show evidence and to disqualify dimensions that cannot be achieved natively by `dbt-core` + adapter/plugin support.

## Files added for the assessment

- `profiles.yml`: local DuckDB profile with the `spatial` extension enabled
- `models/staging/*.sql`: documentation placeholders that explain why shapefile ingestion would require SQL or custom code
- `scripts/generate_iso_function_report.py`: library-based comparison of the two shapefiles and ISO verdict generation
- `scripts/generate_terminal_iso_outputs.py`: captures real terminal output into `analysis_outputs/out.txt`

## Run

```bash
./.venv/bin/python dbt_geo_quality/scripts/generate_terminal_iso_outputs.py
```

## Expected result

The project should confirm that the requested five dimensions are conceptually aligned with ISO practice, but `dbt-core` should be disqualified for all five under the "library/plugin only, no custom SQL/Python" rule.
