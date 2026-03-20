#!/usr/bin/env python3

# Ativa anotações de tipo adiadas para manter compatibilidade melhor com Python 3.9.
from __future__ import annotations

# Importa Counter para contar categorias como tipos de estação e tipos de ferrovia.
from collections import Counter
# Importa combinations para comparar cada par de trechos ferroviários.
from itertools import combinations
# Importa os para copiar variáveis de ambiente antes de chamar o dbt.
import os
# Importa Path para montar caminhos de arquivos de forma mais segura.
from pathlib import Path
# Importa subprocess para executar comandos de terminal como `dbt debug`.
import subprocess

# Importa a biblioteca que lê shapefiles.
import shapefile
# Importa Transformer para converter coordenadas geográficas em coordenadas métricas.
from pyproj import Transformer
# Importa shape para transformar a geometria lida do shapefile em objeto Shapely.
from shapely.geometry import shape
# Importa transform para reprojetar geometrias usando o Transformer.
from shapely.ops import transform
# Importa STRtree para buscar a ferrovia mais próxima de cada estação.
from shapely.strtree import STRtree


# Descobre a pasta onde este script está salvo.
PROJECT_DIR = Path(__file__).resolve().parent
# Descobre a pasta raiz do trabalho, um nível acima da pasta do projeto.
ROOT_DIR = PROJECT_DIR.parent
# Define a pasta onde estão os arquivos da base geográfica.
DATA_DIR = ROOT_DIR / "base_dados"
# Define o caminho do arquivo de saída final.
OUT_PATH = PROJECT_DIR / "out.txt"
# Define o caminho do executável do dbt dentro do ambiente virtual.
DBT_BIN = ROOT_DIR / ".venv" / "bin" / "dbt"
# Cria um transformador de coordenadas de SIRGAS 2000 geográfico para SIRGAS 2000 / UTM 25S.
TRANSFORMER = Transformer.from_crs("EPSG:4674", "EPSG:31985", always_xy=True)


# Executa um comando de terminal e devolve um bloco de texto formatado para o relatório.
def run_command(title: str, command: list[str], extra_env: dict[str, str] | None = None) -> str:
    # Começa sem ambiente customizado.
    env = None
    # Verifica se foram passadas variáveis de ambiente extras.
    if extra_env:
        # Copia o ambiente atual do sistema.
        env = dict(os.environ)
        # Acrescenta ou sobrescreve as variáveis extras.
        env.update(extra_env)
    # Executa o comando e captura stdout e stderr como texto.
    result = subprocess.run(command, cwd=str(PROJECT_DIR), capture_output=True, text=True, env=env)
    # Junta tudo em um único bloco de texto autoexplicativo.
    return "\n".join(
        [
            # Título da seção do comando.
            f"=== {title} ===",
            # Linha em branco para separar visualmente.
            "",
            # Mostra o comando exato executado.
            "$ " + " ".join(command),
            # Linha em branco antes do stdout.
            "",
            # Marca o início do stdout.
            "--- STDOUT ---",
            # Escreve o stdout do comando ou um texto padrão se estiver vazio.
            result.stdout.rstrip() or "(no stdout)",
            # Linha em branco antes do stderr.
            "",
            # Marca o início do stderr.
            "--- STDERR ---",
            # Escreve o stderr do comando ou um texto padrão se estiver vazio.
            result.stderr.rstrip() or "(no stderr)",
            # Linha em branco antes do código de saída.
            "",
            # Marca o início da seção do código de saída.
            "--- EXIT CODE ---",
            # Converte o código de saída para texto.
            str(result.returncode),
            # Linha final em branco.
            "",
        ]
    )


# Calcula um percentil simples a partir de uma lista já ordenada.
def percentile(values: list[float], percent: int) -> float:
    # Se a lista estiver vazia, devolve zero.
    if not values:
        return 0.0
    # Calcula o índice aproximado do percentil pedido.
    index = round((percent / 100) * (len(values) - 1))
    # Devolve o valor naquela posição com duas casas decimais.
    return round(float(values[index]), 2)


# Executa toda a rotina principal do script.
def main() -> None:
    # Abre o shapefile de ferrovias com codificação UTF-8.
    rail_reader = shapefile.Reader(str(DATA_DIR / "Ferrovias_IBGE 2022_AL.shp"), encoding="utf-8")
    # Abre o shapefile de estações com codificação UTF-8.
    station_reader = shapefile.Reader(str(DATA_DIR / "Estacoes ferroviarias.shp"), encoding="utf-8")

    # Lê todos os registros geométricos de ferrovias em memória.
    rail_shapes = list(rail_reader.iterShapeRecords())
    # Lê todos os registros geométricos de estações em memória.
    station_shapes = list(station_reader.iterShapeRecords())

    # Extrai os nomes dos campos da tabela de ferrovias, ignorando o campo técnico DeletionFlag.
    rail_fields = [field[0] for field in rail_reader.fields if field[0] != "DeletionFlag"]
    # Extrai os nomes dos campos da tabela de estações, ignorando o campo técnico DeletionFlag.
    station_fields = [field[0] for field in station_reader.fields if field[0] != "DeletionFlag"]

    # Converte cada registro de ferrovia em dicionário.
    rail_rows = [dict(zip(rail_fields, item.record)) for item in rail_shapes]
    # Converte cada registro de estação em dicionário.
    station_rows = [dict(zip(station_fields, item.record)) for item in station_shapes]

    # Converte cada geometria de ferrovia em objeto Shapely.
    rail_geometries = [shape(item.shape.__geo_interface__) for item in rail_shapes]
    # Converte cada geometria de estação em objeto Shapely.
    station_geometries = [shape(item.shape.__geo_interface__) for item in station_shapes]

    # Reprojeta as ferrovias para uma projeção métrica, adequada para cálculo de distâncias em metros.
    rail_projected = [transform(TRANSFORMER.transform, geometry) for geometry in rail_geometries]
    # Reprojeta as estações para a mesma projeção métrica.
    station_projected = [transform(TRANSFORMER.transform, geometry) for geometry in station_geometries]

    # Cria um índice espacial com as geometrias de ferrovias para acelerar a busca do trecho mais próximo.
    tree = STRtree(rail_projected)
    # Cria a lista que vai armazenar a distância de cada estação até a ferrovia mais próxima.
    distances = []
    # Inicia o contador de inconsistências temporais/operacionais.
    temporal_mismatches = 0

    # Percorre cada estação junto com sua geometria já reprojetada.
    for station_row, station_geometry in zip(station_rows, station_projected):
        # Busca no índice o índice da ferrovia mais próxima.
        nearest_index = tree.nearest(station_geometry)
        # Recupera a linha de atributos da ferrovia mais próxima.
        nearest_rail_row = rail_rows[nearest_index]
        # Calcula a distância entre a estação atual e a ferrovia mais próxima.
        distance = float(station_geometry.distance(rail_projected[nearest_index]))
        # Guarda essa distância na lista geral.
        distances.append(distance)

        # Verifica se a estação está marcada como operando, mas a ferrovia mais próxima não está.
        if station_row.get("operaciona") == "Sim" and nearest_rail_row.get("operaciona") != "Sim":
            # Soma uma inconsistência encontrada.
            temporal_mismatches += 1

    # Ordena a lista de distâncias para permitir cálculo de percentis.
    distances.sort()

    # Conta quantas ferrovias têm geometria inválida.
    invalid_rails = sum(not geometry.is_valid for geometry in rail_geometries)
    # Conta quantas estações têm geometria inválida.
    invalid_stations = sum(not geometry.is_valid for geometry in station_geometries)
    # Conta quantos pares de trechos ferroviários se tocam.
    touch_pairs = sum(1 for left, right in combinations(rail_projected, 2) if left.touches(right))
    # Conta os tipos de estação mais frequentes.
    station_types = Counter(str(row["tipoedifme"]) for row in station_rows if row.get("tipoedifme") not in (None, "")).most_common(3)
    # Conta os tipos de trecho ferroviário mais frequentes.
    rail_types = Counter(str(row["tipotrecho"]) for row in rail_rows if row.get("tipotrecho") not in (None, "")).most_common(3)
    # Procura nomes de campos que pareçam representar informação temporal.
    temporal_fields = sorted(
        # Cria a variável local com o nome do campo sendo analisado.
        field_name
        # Percorre a união entre os campos de ferrovias e estações.
        for field_name in set(rail_fields).union(station_fields)
        # Mantém apenas os campos cujo nome sugere data, tempo, validade ou atualização.
        if any(token in field_name.lower() for token in ("data", "date", "tempo", "time", "valid", "versao", "update"))
    )

    # Monta o conteúdo final do relatório em uma lista de linhas.
    parts = [
        # Título principal do arquivo de saída.
        "# Projeto DBT Core simplificado",
        # Linha em branco.
        "",
        # Bloco com a saída de `dbt --version`.
        run_command("DBT VERSION", [str(DBT_BIN), "--version"]),
        # Bloco com a saída de `dbt debug`.
        run_command(
            # Título da seção do comando.
            "DBT DEBUG",
            # Lista com o comando e seus argumentos.
            [
                # Caminho para o executável do dbt.
                str(DBT_BIN),
                # Subcomando do dbt.
                "debug",
                # Flag que aponta para a pasta do projeto.
                "--project-dir",
                # Caminho da pasta do projeto.
                str(PROJECT_DIR),
                # Flag que aponta para a pasta do profiles.
                "--profiles-dir",
                # Caminho da pasta do profiles.
                str(PROJECT_DIR),
                # Flag para silenciar o arquivo de log detalhado.
                "--log-level-file",
                # Valor da flag anterior.
                "none",
            ],
            # Variáveis de ambiente temporárias para desviar logs e artefatos para /tmp.
            {"DBT_LOG_PATH": "/tmp/dbt_core_flat_logs", "DBT_TARGET_PATH": "/tmp/dbt_core_flat_target"},
        ),
        # Título da seção com os resultados ISO.
        "=== ISO RESULTADO ===",
        # Linha em branco.
        "",
        # Texto fixo indicando qual biblioteca está sendo avaliada.
        "Biblioteca avaliada: dbt-core com dbt-duckdb.",
        # Texto fixo indicando quais bases estão sendo comparadas.
        "Bases comparadas: Ferrovias_IBGE 2022_AL.shp x Estacoes ferroviarias.shp.",
        # Linha em branco.
        "",
        # Resumo rápido com contagens e proximidade espacial entre as camadas.
        f"Resumo rapido: {len(rail_rows)} ferrovias, {len(station_rows)} estacoes, {sum(d <= 20 for d in distances)}/{len(distances)} estacoes ate 20 m da ferrovia mais proxima, {sum(d <= 100 for d in distances)}/{len(distances)} ate 100 m.",
        # Linha em branco.
        "",
        # Cabeçalho da ISO 1.
        "ISO 1 - Completude",
        # Conclusão conceitual sobre a ISO 1.
        "SIM para a definicao conceitual.",
        # Conclusão prática para dbt-core na ISO 1.
        "DESQUALIFICADA para dbt-core sob a regra sem SQL/Python custom.",
        # Motivo da desqualificação na ISO 1.
        "Motivo: sem imagem de referencia ou plugin pronto de deteccao de omissao.",
        # Linha em branco.
        "",
        # Cabeçalho da ISO 2.
        "ISO 2 - Consistencia logica",
        # Conclusão conceitual sobre a ISO 2.
        "SIM para a definicao conceitual.",
        # Conclusão prática para dbt-core na ISO 2.
        "DESQUALIFICADA para dbt-core sob a regra sem SQL/Python custom.",
        # Evidência encontrada na base para a ISO 2.
        f"Evidencia da base: {invalid_rails} ferrovias invalidas, {invalid_stations} estacoes invalidas, {touch_pairs} contatos entre trechos ferroviarios.",
        # Linha em branco.
        "",
        # Cabeçalho da ISO 3.
        "ISO 3 - Precisao posicional",
        # Conclusão conceitual sobre a ISO 3.
        "SIM para a definicao conceitual.",
        # Conclusão prática para dbt-core na ISO 3.
        "DESQUALIFICADA para dbt-core sob a regra sem SQL/Python custom.",
        # Evidência encontrada na base para a ISO 3.
        f"Evidencia da base: p50={percentile(distances, 50)} m, p90={percentile(distances, 90)} m, p95={percentile(distances, 95)} m, max={percentile(distances, 100)} m.",
        # Linha em branco.
        "",
        # Cabeçalho da ISO 4.
        "ISO 4 - Qualidade tematica",
        # Conclusão conceitual sobre a ISO 4.
        "SIM para a definicao conceitual.",
        # Conclusão prática para dbt-core na ISO 4.
        "DESQUALIFICADA para dbt-core sob a regra sem SQL/Python custom.",
        # Evidência encontrada na base para a ISO 4.
        f"Evidencia da base: tipos de estacao mais comuns {station_types}; tipos de ferrovia mais comuns {rail_types}.",
        # Linha em branco.
        "",
        # Cabeçalho da ISO 5.
        "ISO 5 - Qualidade temporal",
        # Conclusão conceitual sobre a ISO 5.
        "SIM para a definicao conceitual.",
        # Conclusão prática para dbt-core na ISO 5.
        "DESQUALIFICADA para dbt-core sob a regra sem SQL/Python custom.",
        # Evidência encontrada na base para a ISO 5.
        f"Evidencia da base: campos temporais explicitos {temporal_fields or 'nenhum'}; {temporal_mismatches} estacoes com operacao 'Sim' ligadas a ferrovia 'Nao' ou 'Desconhecido'.",
        # Linha em branco.
        "",
        # Cabeçalho da conclusão final.
        "Veredito final",
        # Frase final consolidando a decisão do script.
        "As 5 descricoes da ISO fazem sentido, mas o dbt-core nao entrega nenhuma delas pronto como biblioteca/plugin geoespacial sem codigo customizado.",
        # Linha em branco.
        "",
    ]

    # Junta todas as linhas do relatório em um único texto e grava no arquivo de saída.
    OUT_PATH.write_text("\n".join(parts), encoding="utf-8")
    # Lê o arquivo recém-gravado e imprime no terminal.
    print(OUT_PATH.read_text(encoding="utf-8"))


# Verifica se o arquivo está sendo executado diretamente.
if __name__ == "__main__":
    # Se estiver, chama a função principal.
    main()
