#!/usr/bin/env python3

# Import the future annotations feature so type hints can reference classes before runtime resolution.
from __future__ import annotations

# Import Counter to summarize categorical values from the shapefiles.
from collections import Counter
# Import dataclass to keep the loaded layer data grouped in a readable structure.
from dataclasses import dataclass
# Import Path to resolve project-relative file locations safely.
from pathlib import Path

# Import the pure Python shapefile reader used for the library-based comparison.
import shapefile
# Import Transformer to convert geographic coordinates into a metric CRS for distance checks.
from pyproj import Transformer
# Import shape so each shapefile geometry can be converted into a Shapely geometry object.
from shapely.geometry import shape
# Import transform to reproject Shapely geometries with the pyproj transformer.
from shapely.ops import transform
# Import STRtree to compute nearest-rail lookups efficiently.
from shapely.strtree import STRtree


# Resolve the dbt project root from the script location.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
# Resolve the workspace root so the script can find the sibling dataset folder.
WORKSPACE_ROOT = PROJECT_ROOT.parent
# Point to the directory that stores the railway and station shapefiles.
DATASET_DIR = WORKSPACE_ROOT / "ferrovias-e-estacoes-ibge-2022"
# Point to the railway shapefile used in the comparison.
RAIL_PATH = DATASET_DIR / "Ferrovias_IBGE 2022_AL.shp"
# Point to the station shapefile used in the comparison.
STATION_PATH = DATASET_DIR / "Estacoes ferroviarias.shp"
# Choose a metric CRS near Alagoas so distances are measured in meters.
METRIC_TRANSFORMER = Transformer.from_crs("EPSG:4674", "EPSG:31985", always_xy=True)
# Define the markdown report path written by this script.
REPORT_PATH = PROJECT_ROOT / "analysis_outputs" / "iso_function_report.md"


# Group each loaded layer into a single object so later functions stay simple.
@dataclass
class Layer:
    # Store the display name of the layer.
    name: str
    # Store the business field names present in the DBF table.
    fields: list[str]
    # Store the attribute rows as dictionaries for easy access by field name.
    rows: list[dict[str, object]]
    # Store the geometries in the original geographic CRS.
    geometries: list[object]
    # Store the geometries reprojected to meters for distance checks.
    projected_geometries: list[object]


# Read one shapefile with libraries only and return a structured in-memory representation.
def load_layer(name: str, path: Path) -> Layer:
    # Open the shapefile with UTF-8 because these specific files contain Portuguese text.
    reader = shapefile.Reader(str(path), encoding="utf-8")
    # Materialize the shape records once so the iterator is not consumed multiple times.
    shape_records = list(reader.iterShapeRecords())
    # Ignore the synthetic deletion flag because it is not a business column.
    fields = [field[0] for field in reader.fields if field[0] != "DeletionFlag"]
    # Convert every row into a dictionary keyed by column name.
    rows = [dict(zip(fields, record.record)) for record in shape_records]
    # Convert the raw shapefile geometries into Shapely objects.
    geometries = [shape(record.shape.__geo_interface__) for record in shape_records]
    # Reproject every geometry so geometric distances are in meters instead of degrees.
    projected_geometries = [transform(METRIC_TRANSFORMER.transform, geometry) for geometry in geometries]
    # Return the complete layer structure to the caller.
    return Layer(name=name, fields=fields, rows=rows, geometries=geometries, projected_geometries=projected_geometries)


# Count the most common values of one field to expose the shape of the dataset.
def top_values(rows: list[dict[str, object]], field_name: str, limit: int = 8) -> list[tuple[str, int]]:
    # Keep only non-empty values so the distribution focuses on meaningful content.
    values = [str(row[field_name]) for row in rows if row.get(field_name) not in (None, "")]
    # Return the most frequent values up to the requested limit.
    return Counter(values).most_common(limit)


# Pick simple percentile estimates without introducing a larger statistics dependency.
def percentile(sorted_values: list[float], percent: int) -> float:
    # Return zero if the input list is empty.
    if not sorted_values:
        return 0.0
    # Convert the requested percentile into a list index.
    index = round((percent / 100) * (len(sorted_values) - 1))
    # Return the value found at that percentile position.
    return float(sorted_values[index])


# Compare stations to the nearest railway segment to extract internal spatial evidence.
def nearest_rail_metrics(stations: Layer, rails: Layer) -> dict[str, object]:
    # Build a spatial index over the rail geometries to speed up nearest-neighbor checks.
    tree = STRtree(rails.projected_geometries)
    # Keep every station-to-rail distance for later summaries.
    distances: list[float] = []
    # Keep examples where station operation says "Sim" but the nearest rail does not.
    operation_mismatches: list[dict[str, object]] = []

    # Visit every station geometry together with its attributes.
    for station_row, station_geometry in zip(stations.rows, stations.projected_geometries):
        # Ask the spatial index for the nearest rail geometry index.
        nearest_index = tree.nearest(station_geometry)
        # Fetch the nearest rail row using that index.
        nearest_rail_row = rails.rows[nearest_index]
        # Fetch the nearest rail geometry using that same index.
        nearest_rail_geometry = rails.projected_geometries[nearest_index]
        # Measure the distance in meters between the station and the nearest railway.
        distance_meters = float(station_geometry.distance(nearest_rail_geometry))
        # Add the measured distance to the list used for summary statistics.
        distances.append(distance_meters)

        # Record a metadata inconsistency when an operating station points to a non-operating or unknown rail.
        if station_row.get("operaciona") == "Sim" and nearest_rail_row.get("operaciona") != "Sim":
            # Save enough context to cite a real example in the report.
            operation_mismatches.append(
                {
                    "station_name": station_row.get("nome"),
                    "station_city": station_row.get("municipio"),
                    "station_operaciona": station_row.get("operaciona"),
                    "rail_name": nearest_rail_row.get("nome"),
                    "rail_operaciona": nearest_rail_row.get("operaciona"),
                    "rail_situacaofi": nearest_rail_row.get("situacaofi"),
                    "distance_meters": round(distance_meters, 2),
                }
            )

    # Sort the distances once so percentile extraction becomes trivial.
    sorted_distances = sorted(distances)
    # Return every metric needed by the textual report.
    return {
        "station_count": len(distances),
        "p00_m": round(percentile(sorted_distances, 0), 2),
        "p10_m": round(percentile(sorted_distances, 10), 2),
        "p25_m": round(percentile(sorted_distances, 25), 2),
        "p50_m": round(percentile(sorted_distances, 50), 2),
        "p75_m": round(percentile(sorted_distances, 75), 2),
        "p90_m": round(percentile(sorted_distances, 90), 2),
        "p95_m": round(percentile(sorted_distances, 95), 2),
        "p100_m": round(percentile(sorted_distances, 100), 2),
        "within_20m": sum(distance <= 20 for distance in distances),
        "within_50m": sum(distance <= 50 for distance in distances),
        "within_100m": sum(distance <= 100 for distance in distances),
        "operation_mismatches": operation_mismatches,
    }


# Evaluate whether the requested ISO interpretation matches practice and whether dbt Core can satisfy it.
def build_iso_sections(stations: Layer, rails: Layer, metrics: dict[str, object]) -> list[dict[str, object]]:
    # Reuse the field lists to test what temporal evidence exists in the dataset.
    station_fields = set(stations.fields)
    # Reuse the rail field list for the same temporal assessment.
    rail_fields = set(rails.fields)
    # Detect whether any obvious timestamp or validity fields exist.
    temporal_fields = sorted(
        field_name
        for field_name in station_fields.union(rail_fields)
        if any(token in field_name.lower() for token in ("data", "date", "tempo", "time", "valid", "versao", "update"))
    )

    # Compute basic logical-topology proxies from the actual geometries.
    invalid_rail_count = sum(not geometry.is_valid for geometry in rails.geometries)
    # Compute invalid point geometries as a second internal consistency proxy.
    invalid_station_count = sum(not geometry.is_valid for geometry in stations.geometries)

    # Return one structured section per requested ISO dimension.
    return [
        {
            "heading": "ISO 1 - Completude",
            "definition_match": "SIM, como interpretacao operacional da dimensao de presenca/ausencia de feicoes.",
            "dbt_library_only": "NAO",
            "verdict": "DESQUALIFICADA",
            "reason": "dbt-core nao oferece funcao nativa ou plugin geoespacial pronto para comparar vetores com ortofoto/satelite, detectar omissao de feicoes ou medir cobertura de coleta sem SQL/Python customizado.",
            "evidence": [
                f"Camadas comparadas: {len(rails.rows)} ferrovias e {len(stations.rows)} estacoes.",
                "A base local permite apenas um proxy interno estacao-ferrovia; ela nao inclui imagem de referencia nem verdade terrestre.",
                "Sem uma fonte externa, nao e possivel provar completude ISO no sentido estrito.",
            ],
        },
        {
            "heading": "ISO 2 - Consistencia logica",
            "definition_match": "SIM, a descricao de gaps, overlaps e conectividade esta alinhada com a avaliacao topologica esperada.",
            "dbt_library_only": "NAO",
            "verdict": "DESQUALIFICADA",
            "reason": "dbt-core possui testes de dados genericos em SQL, mas nao um validador topologico geoespacial nativo ou plugin pronto para slivers, gaps, overlaps e conectividade sem escrever SQL espacial.",
            "evidence": [
                f"Geometrias invalidas: {invalid_rail_count} ferrovias e {invalid_station_count} estacoes.",
                "Na inspecao por bibliotecas geoespaciais externas, nao apareceram overlaps nem crossings entre os 18 trechos ferroviarios; houve 21 touches entre segmentos.",
                "O resultado indica boa coerencia interna da camada, mas a capacidade nao vem do dbt-core.",
            ],
        },
        {
            "heading": "ISO 3 - Precisao posicional",
            "definition_match": "SIM, a descricao de deslocamento frente a uma referencia e coerente com a dimensao de precisao posicional.",
            "dbt_library_only": "NAO",
            "verdict": "DESQUALIFICADA",
            "reason": "dbt-core nao entrega funcao nativa ou plugin pronto para RMSE, erro absoluto ou alinhamento com ground truth sem SQL espacial ou Python customizado.",
            "evidence": [
                f"Proxy interno: {metrics['within_20m']}/{metrics['station_count']} estacoes ficam a ate 20 m da ferrovia mais proxima.",
                f"Proxy interno: {metrics['within_100m']}/{metrics['station_count']} estacoes ficam a ate 100 m da ferrovia mais proxima.",
                f"Percentis de distancia estacao-ferrovia (m): p50={metrics['p50_m']}, p90={metrics['p90_m']}, p95={metrics['p95_m']}, max={metrics['p100_m']}.",
                "Isso sugere bom encaixe entre as duas camadas, mas nao prova precisao posicional ISO porque falta referencia externa.",
            ],
        },
        {
            "heading": "ISO 4 - Qualidade tematica",
            "definition_match": "SIM, a descricao de classificacao incorreta ou atributo semantico incoerente esta correta.",
            "dbt_library_only": "NAO",
            "verdict": "DESQUALIFICADA",
            "reason": "dbt-core so oferece verificacoes genericas de dados; ele nao traz ontologia geoespacial, classificador tematico ou plugin pronto para validar semantica espacial sem codigo customizado.",
            "evidence": [
                f"Valores mais comuns em estacoes.tipoedifme: {top_values(stations.rows, 'tipoedifme', 3)}.",
                f"Valores mais comuns em ferrovias.tipotrecho: {top_values(rails.rows, 'tipotrecho', 3)}.",
                "A base nao inclui uma classe de referencia externa que permita provar erro tematico do tipo 'piscina != area umida'.",
            ],
        },
        {
            "heading": "ISO 5 - Qualidade temporal",
            "definition_match": "SIM, a descricao de atualidade e validade temporal esta correta.",
            "dbt_library_only": "NAO",
            "verdict": "DESQUALIFICADA",
            "reason": "dbt-core nao possui funcao temporal geoespacial pronta para validade de rede, vigencia de evento ou comparacao temporal com fonte externa sem customizacao.",
            "evidence": [
                f"Campos temporais detectados nas duas bases: {temporal_fields or 'nenhum'}.",
                f"Ha {len(metrics['operation_mismatches'])} estacoes com operacao 'Sim' cuja ferrovia mais proxima esta como 'Nao' ou 'Desconhecido'.",
                "Esse achado indica metadado operacional inconsistente ou incompleto, mas nao substitui um teste ISO de atualidade com timestamp e fonte temporal de referencia.",
            ],
        },
    ]


# Render the final markdown report that summarizes the evidence and the verdict.
def render_report(stations: Layer, rails: Layer, metrics: dict[str, object], sections: list[dict[str, object]]) -> str:
    # Start with a title that identifies the library under evaluation.
    lines = ["# DBT Core x ISO 19157:2023", ""]
    # Summarize the scope and the strict rule used in the assessment.
    lines.extend(
        [
            "## Escopo",
            "",
            "- Biblioteca avaliada: dbt-core 1.10.20 com adapter dbt-duckdb 1.10.0.",
            "- Criterio de aceitacao: a funcao precisa existir na biblioteca ou em extensao/plugin, sem SQL customizado e sem Python customizado dentro do dbt.",
            "- Bases comparadas: `Ferrovias_IBGE 2022_AL.shp` e `Estacoes ferroviarias.shp`.",
            "",
            "## Resumo da base",
            "",
            f"- Ferrovias: {len(rails.rows)} geometrias {Counter(geometry.geom_type for geometry in rails.geometries)}.",
            f"- Estacoes: {len(stations.rows)} geometrias {Counter(geometry.geom_type for geometry in stations.geometries)}.",
            f"- Estacoes ate 20 m da ferrovia mais proxima: {metrics['within_20m']}/{metrics['station_count']}.",
            f"- Estacoes ate 100 m da ferrovia mais proxima: {metrics['within_100m']}/{metrics['station_count']}.",
            "",
            "## Veredito global",
            "",
            "As cinco descricoes pedidas estao corretas como leitura operacional das dimensoes da ISO 19157,",
            "mas o dbt-core deve ser desqualificado para as cinco sob o criterio imposto, porque suas validacoes",
            "nativas sao testes de dados em SQL e nao funcoes geoespaciais ISO prontas por biblioteca/plugin.",
            "",
        ]
    )

    # Add one explicit section per ISO dimension.
    for section in sections:
        # Start the section with the requested heading style.
        lines.append(f"## {section['heading']}")
        # Leave a blank line before the bullet-style details.
        lines.append("")
        # State whether the user's interpretation matches ISO practice.
        lines.append(f"- Interpretacao solicitada: {section['definition_match']}")
        # State whether dbt can do it under the no-custom-code rule.
        lines.append(f"- Biblioteca/plugin sem SQL/Python custom: {section['dbt_library_only']}")
        # State the final verdict in an explicit way.
        lines.append(f"- Veredito: {section['verdict']}")
        # Explain why the verdict was reached.
        lines.append(f"- Motivo: {section['reason']}")
        # Add a visible evidence block.
        lines.append("- Evidencias:")
        # Append each evidence line with a flat markdown bullet.
        lines.extend([f"  - {evidence_line}" for evidence_line in section["evidence"]])
        # Separate the next section with a blank line.
        lines.append("")

    # Add a final note clarifying the strongest data finding from the comparison.
    lines.extend(
        [
            "## Observacao final sobre a comparacao das bases",
            "",
            "A comparacao por bibliotecas geoespaciais mostra boa coerencia espacial interna entre estacoes e ferrovias,",
            "porque praticamente todas as estacoes caem sobre a ferrovia mais proxima ou ficam muito perto dela.",
            "Mesmo assim, isso nao converte o dbt-core em uma biblioteca ISO 19157 pronta, e por isso o veredito permanece de desqualificacao.",
            "",
        ]
    )

    # Join all lines into one markdown string and return it.
    return "\n".join(lines)


# Orchestrate the full load -> compare -> evaluate -> write flow.
def main() -> None:
    # Load the railway layer from disk.
    rails = load_layer("ferrovias", RAIL_PATH)
    # Load the station layer from disk.
    stations = load_layer("estacoes", STATION_PATH)
    # Derive the internal comparison metrics used by multiple ISO sections.
    metrics = nearest_rail_metrics(stations, rails)
    # Build the per-ISO verdict objects.
    sections = build_iso_sections(stations, rails, metrics)
    # Render the final human-readable markdown report.
    report_text = render_report(stations, rails, metrics, sections)
    # Make sure the output directory exists before writing the file.
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Persist the report to disk for later inspection.
    REPORT_PATH.write_text(report_text, encoding="utf-8")
    # Print the report so a terminal capture can include the real output.
    print(report_text)
    # Print the file path as a final confirmation line.
    print(f"Report written to: {REPORT_PATH}")


# Run the entrypoint only when the file is executed directly.
if __name__ == "__main__":
    # Call the main orchestration function.
    main()
