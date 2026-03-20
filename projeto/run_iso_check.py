#!/usr/bin/env python3

# Projeto minimo: roda DBT Core, compara as duas camadas e grava tudo em out.txt.
from __future__ import annotations

from collections import Counter
from itertools import combinations
import os
from pathlib import Path
import subprocess

import shapefile
from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform
from shapely.strtree import STRtree


PROJECT_DIR = Path(__file__).resolve().parent
ROOT_DIR = PROJECT_DIR.parent
DATA_DIR = ROOT_DIR / "base_dados"
OUT_PATH = PROJECT_DIR / "out.txt"
DBT_BIN = ROOT_DIR / ".venv" / "bin" / "dbt"
TRANSFORMER = Transformer.from_crs("EPSG:4674", "EPSG:31985", always_xy=True)


def run_command(title: str, command: list[str], extra_env: dict[str, str] | None = None) -> str:
    env = None
    if extra_env:
        env = dict(os.environ)
        env.update(extra_env)
    result = subprocess.run(command, cwd=str(PROJECT_DIR), capture_output=True, text=True, env=env)
    return "\n".join(
        [
            f"=== {title} ===",
            "",
            "$ " + " ".join(command),
            "",
            "--- STDOUT ---",
            result.stdout.rstrip() or "(no stdout)",
            "",
            "--- STDERR ---",
            result.stderr.rstrip() or "(no stderr)",
            "",
            "--- EXIT CODE ---",
            str(result.returncode),
            "",
        ]
    )


def percentile(values: list[float], percent: int) -> float:
    if not values:
        return 0.0
    index = round((percent / 100) * (len(values) - 1))
    return round(float(values[index]), 2)


def main() -> None:
    rail_reader = shapefile.Reader(str(DATA_DIR / "Ferrovias_IBGE 2022_AL.shp"), encoding="utf-8")
    station_reader = shapefile.Reader(str(DATA_DIR / "Estacoes ferroviarias.shp"), encoding="utf-8")

    rail_shapes = list(rail_reader.iterShapeRecords())
    station_shapes = list(station_reader.iterShapeRecords())

    rail_fields = [field[0] for field in rail_reader.fields if field[0] != "DeletionFlag"]
    station_fields = [field[0] for field in station_reader.fields if field[0] != "DeletionFlag"]

    rail_rows = [dict(zip(rail_fields, item.record)) for item in rail_shapes]
    station_rows = [dict(zip(station_fields, item.record)) for item in station_shapes]

    rail_geometries = [shape(item.shape.__geo_interface__) for item in rail_shapes]
    station_geometries = [shape(item.shape.__geo_interface__) for item in station_shapes]

    rail_projected = [transform(TRANSFORMER.transform, geometry) for geometry in rail_geometries]
    station_projected = [transform(TRANSFORMER.transform, geometry) for geometry in station_geometries]

    tree = STRtree(rail_projected)
    distances = []
    temporal_mismatches = 0

    for station_row, station_geometry in zip(station_rows, station_projected):
        nearest_index = tree.nearest(station_geometry)
        nearest_rail_row = rail_rows[nearest_index]
        distance = float(station_geometry.distance(rail_projected[nearest_index]))
        distances.append(distance)

        if station_row.get("operaciona") == "Sim" and nearest_rail_row.get("operaciona") != "Sim":
            temporal_mismatches += 1

    distances.sort()

    invalid_rails = sum(not geometry.is_valid for geometry in rail_geometries)
    invalid_stations = sum(not geometry.is_valid for geometry in station_geometries)
    touch_pairs = sum(1 for left, right in combinations(rail_projected, 2) if left.touches(right))
    station_types = Counter(str(row["tipoedifme"]) for row in station_rows if row.get("tipoedifme") not in (None, "")).most_common(3)
    rail_types = Counter(str(row["tipotrecho"]) for row in rail_rows if row.get("tipotrecho") not in (None, "")).most_common(3)
    temporal_fields = sorted(
        field_name
        for field_name in set(rail_fields).union(station_fields)
        if any(token in field_name.lower() for token in ("data", "date", "tempo", "time", "valid", "versao", "update"))
    )

    parts = [
        "# Projeto DBT Core simplificado",
        "",
        run_command("DBT VERSION", [str(DBT_BIN), "--version"]),
        run_command(
            "DBT DEBUG",
            [
                str(DBT_BIN),
                "debug",
                "--project-dir",
                str(PROJECT_DIR),
                "--profiles-dir",
                str(PROJECT_DIR),
                "--log-level-file",
                "none",
            ],
            {"DBT_LOG_PATH": "/tmp/dbt_core_flat_logs", "DBT_TARGET_PATH": "/tmp/dbt_core_flat_target"},
        ),
        "=== ISO RESULTADO ===",
        "",
        "Biblioteca avaliada: dbt-core com dbt-duckdb.",
        "Bases comparadas: Ferrovias_IBGE 2022_AL.shp x Estacoes ferroviarias.shp.",
        "",
        f"Resumo rapido: {len(rail_rows)} ferrovias, {len(station_rows)} estacoes, {sum(d <= 20 for d in distances)}/{len(distances)} estacoes ate 20 m da ferrovia mais proxima, {sum(d <= 100 for d in distances)}/{len(distances)} ate 100 m.",
        "",
        "ISO 1 - Completude",
        "SIM para a definicao conceitual.",
        "DESQUALIFICADA para dbt-core sob a regra sem SQL/Python custom.",
        "Motivo: sem imagem de referencia ou plugin pronto de deteccao de omissao.",
        "",
        "ISO 2 - Consistencia logica",
        "SIM para a definicao conceitual.",
        "DESQUALIFICADA para dbt-core sob a regra sem SQL/Python custom.",
        f"Evidencia da base: {invalid_rails} ferrovias invalidas, {invalid_stations} estacoes invalidas, {touch_pairs} contatos entre trechos ferroviarios.",
        "",
        "ISO 3 - Precisao posicional",
        "SIM para a definicao conceitual.",
        "DESQUALIFICADA para dbt-core sob a regra sem SQL/Python custom.",
        f"Evidencia da base: p50={percentile(distances, 50)} m, p90={percentile(distances, 90)} m, p95={percentile(distances, 95)} m, max={percentile(distances, 100)} m.",
        "",
        "ISO 4 - Qualidade tematica",
        "SIM para a definicao conceitual.",
        "DESQUALIFICADA para dbt-core sob a regra sem SQL/Python custom.",
        f"Evidencia da base: tipos de estacao mais comuns {station_types}; tipos de ferrovia mais comuns {rail_types}.",
        "",
        "ISO 5 - Qualidade temporal",
        "SIM para a definicao conceitual.",
        "DESQUALIFICADA para dbt-core sob a regra sem SQL/Python custom.",
        f"Evidencia da base: campos temporais explicitos {temporal_fields or 'nenhum'}; {temporal_mismatches} estacoes com operacao 'Sim' ligadas a ferrovia 'Nao' ou 'Desconhecido'.",
        "",
        "Veredito final",
        "As 5 descricoes da ISO fazem sentido, mas o dbt-core nao entrega nenhuma delas pronto como biblioteca/plugin geoespacial sem codigo customizado.",
        "",
    ]

    OUT_PATH.write_text("\n".join(parts), encoding="utf-8")
    print(OUT_PATH.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
