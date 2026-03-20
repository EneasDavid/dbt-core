# DBT Core x ISO 19157:2023

## Escopo

- Biblioteca avaliada: dbt-core 1.10.20 com adapter dbt-duckdb 1.10.0.
- Criterio de aceitacao: a funcao precisa existir na biblioteca ou em extensao/plugin, sem SQL customizado e sem Python customizado dentro do dbt.
- Bases comparadas: `Ferrovias_IBGE 2022_AL.shp` e `Estacoes ferroviarias.shp`.

## Resumo da base

- Ferrovias: 18 geometrias Counter({'LineString': 18}).
- Estacoes: 69 geometrias Counter({'Point': 69}).
- Estacoes ate 20 m da ferrovia mais proxima: 65/69.
- Estacoes ate 100 m da ferrovia mais proxima: 69/69.

## Veredito global

As cinco descricoes pedidas estao corretas como leitura operacional das dimensoes da ISO 19157,
mas o dbt-core deve ser desqualificado para as cinco sob o criterio imposto, porque suas validacoes
nativas sao testes de dados em SQL e nao funcoes geoespaciais ISO prontas por biblioteca/plugin.

## ISO 1 - Completude

- Interpretacao solicitada: SIM, como interpretacao operacional da dimensao de presenca/ausencia de feicoes.
- Biblioteca/plugin sem SQL/Python custom: NAO
- Veredito: DESQUALIFICADA
- Motivo: dbt-core nao oferece funcao nativa ou plugin geoespacial pronto para comparar vetores com ortofoto/satelite, detectar omissao de feicoes ou medir cobertura de coleta sem SQL/Python customizado.
- Evidencias:
  - Camadas comparadas: 18 ferrovias e 69 estacoes.
  - A base local permite apenas um proxy interno estacao-ferrovia; ela nao inclui imagem de referencia nem verdade terrestre.
  - Sem uma fonte externa, nao e possivel provar completude ISO no sentido estrito.

## ISO 2 - Consistencia logica

- Interpretacao solicitada: SIM, a descricao de gaps, overlaps e conectividade esta alinhada com a avaliacao topologica esperada.
- Biblioteca/plugin sem SQL/Python custom: NAO
- Veredito: DESQUALIFICADA
- Motivo: dbt-core possui testes de dados genericos em SQL, mas nao um validador topologico geoespacial nativo ou plugin pronto para slivers, gaps, overlaps e conectividade sem escrever SQL espacial.
- Evidencias:
  - Geometrias invalidas: 0 ferrovias e 0 estacoes.
  - Na inspecao por bibliotecas geoespaciais externas, nao apareceram overlaps nem crossings entre os 18 trechos ferroviarios; houve 21 touches entre segmentos.
  - O resultado indica boa coerencia interna da camada, mas a capacidade nao vem do dbt-core.

## ISO 3 - Precisao posicional

- Interpretacao solicitada: SIM, a descricao de deslocamento frente a uma referencia e coerente com a dimensao de precisao posicional.
- Biblioteca/plugin sem SQL/Python custom: NAO
- Veredito: DESQUALIFICADA
- Motivo: dbt-core nao entrega funcao nativa ou plugin pronto para RMSE, erro absoluto ou alinhamento com ground truth sem SQL espacial ou Python customizado.
- Evidencias:
  - Proxy interno: 65/69 estacoes ficam a ate 20 m da ferrovia mais proxima.
  - Proxy interno: 69/69 estacoes ficam a ate 100 m da ferrovia mais proxima.
  - Percentis de distancia estacao-ferrovia (m): p50=0.0, p90=9.63, p95=21.54, max=55.98.
  - Isso sugere bom encaixe entre as duas camadas, mas nao prova precisao posicional ISO porque falta referencia externa.

## ISO 4 - Qualidade tematica

- Interpretacao solicitada: SIM, a descricao de classificacao incorreta ou atributo semantico incoerente esta correta.
- Biblioteca/plugin sem SQL/Python custom: NAO
- Veredito: DESQUALIFICADA
- Motivo: dbt-core so oferece verificacoes genericas de dados; ele nao traz ontologia geoespacial, classificador tematico ou plugin pronto para validar semantica espacial sem codigo customizado.
- Evidencias:
  - Valores mais comuns em estacoes.tipoedifme: [('(1:Estação ferroviária de passageiros)', 56), ('(1:Desconhecido)', 12), ('(1:Outros)', 1)].
  - Valores mais comuns em ferrovias.tipotrecho: [('Trecho para trem', 18)].
  - A base nao inclui uma classe de referencia externa que permita provar erro tematico do tipo 'piscina != area umida'.

## ISO 5 - Qualidade temporal

- Interpretacao solicitada: SIM, a descricao de atualidade e validade temporal esta correta.
- Biblioteca/plugin sem SQL/Python custom: NAO
- Veredito: DESQUALIFICADA
- Motivo: dbt-core nao possui funcao temporal geoespacial pronta para validade de rede, vigencia de evento ou comparacao temporal com fonte externa sem customizacao.
- Evidencias:
  - Campos temporais detectados nas duas bases: nenhum.
  - Ha 19 estacoes com operacao 'Sim' cuja ferrovia mais proxima esta como 'Nao' ou 'Desconhecido'.
  - Esse achado indica metadado operacional inconsistente ou incompleto, mas nao substitui um teste ISO de atualidade com timestamp e fonte temporal de referencia.

## Observacao final sobre a comparacao das bases

A comparacao por bibliotecas geoespaciais mostra boa coerencia espacial interna entre estacoes e ferrovias,
porque praticamente todas as estacoes caem sobre a ferrovia mais proxima ou ficam muito perto dela.
Mesmo assim, isso nao converte o dbt-core em uma biblioteca ISO 19157 pronta, e por isso o veredito permanece de desqualificacao.
