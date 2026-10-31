# Dashboards de turismo no Alentejo: mockups

Mockups HTML de sete dashboards Power BI construídos sobre as tabelas INE da Pista Digital (`docs/ine_dicionario_dados.sql`). Servem de especificação visual e funcional. **Todos os valores são ilustrativos.**

## Conteúdo

| Ficheiro | Dashboard | Público |
|---|---|---|
| `index.html` | Página inicial com ligações | Todos |
| `01_pulso_alentejo.html` | Pulso do Alentejo | Turismo do Alentejo, CCDR |
| `02_raio_x_concelho.html` | Raio-X do concelho | Câmaras municipais |
| `03_radar_mercados.html` | Radar de mercados | Promoção turística |
| `04_mapa_oportunidades.html` | Mapa de oportunidades | Investidores e empresários |
| `05_alentejo_em_numeros.html` | Alentejo em números | Academia, media, público |
| `06_barometro_empresario.html` | Barómetro do empresário | Hoteleiros e gestores de alojamento |
| `07_noites_e_quartos.html` | Noites e Quartos (oferta e procura) | Técnicos, ERT, investidores |
| `powerbi_tema_alentejo.json` | Tema Power BI com a mesma paleta | — |
| `imagens/claro/`, `imagens/escuro/` | Capturas PNG de cada dashboard (2x), incluindo estados alternativos | — |

Cada HTML é autónomo (CSS e JS inline). Precisa de internet para carregar o Chart.js (cdnjs) e a fonte Public Sans (Google Fonts). Suporta modo claro e escuro.

## Identidade visual

Inspirada no casario alentejano: fundo de cal, a barra azul-anil que contorna as casas (cor principal e faixa sob o cabeçalho) e o amarelo-ocre das molduras (destaque e seleção).

| Token | Claro | Escuro | Uso |
|---|---|---|---|
| `--anil` | `#1F4FA3` | `#7FA6EC` | Série principal, seleção, cabeçalho |
| `--ocre` | `#C9960F` | `#E2B53D` | Destaque (Alentejo entre regiões, mercado selecionado, verão) |
| `--oliva` | `#5F6F2E` | `#A3B661` | Variação positiva |
| `--neg` | `#B3412E` | `#E5846F` | Variação negativa, oferta acima da procura |
| `--cal` | `#FAFAF7` | `#11151C` | Fundo da página |

## Especificação por dashboard

### 01 Pulso do Alentejo
| Visual | Tabelas | Medida |
|---|---|---|
| KPIs (dormidas, hóspedes, estada, RevPAR, quota internacional, índice 2019) | 0009877, 0009876, 0009929, 0009183 | `[Dormidas]`, `[Hóspedes]`, `[Estada média]`, `[Quota internacional]`, `[Índice 2019]` |
| Sazonalidade mensal, ano vs 2019 | 0009808 | `[Dormidas]` por `mes` |
| Variação por NUTS III | 0009877 | `[Var. homóloga %]` |
| Posicionamento NUTS II (dispersão) | 0009808, 0009812 | crescimento vs `[Estada média]` |
| Indicadores de sazonalidade | 0009808 | `[Rácio pico/vale]`, `[% jun-set]`, `[Gini mensal]` |

Filtros: ano; definição territorial NUTS 2024 / NUTS 2013 (a NUTS 2013 inclui a Lezíria do Tejo).

### 02 Raio-X do concelho
| Visual | Tabelas | Medida |
|---|---|---|
| KPIs (dormidas/km², quartos/km², peso AL, estada, mês de pico) | 0009877, 0009874, 0008350, 0010735 | `[Dormidas por km2]`, `[Quartos por km2]`, `[Peso AL]` |
| Pressão face aos pares | 0009877, 0008350 | `[Dormidas por km2]`, município selecionado destacado |
| Calendário de pressão (mapa de calor) | 0010735 | `[Índice mensal]` = dormidas do mês ÷ máx. do ano × 100 |
| Mercados sobre/sub-representados | 0009930 | `[Quota mercado município] - [Quota mercado Alentejo]` |
| Mapa | 0008350 + TopoJSON municipal | Shape Map / Azure Maps |

Filtro: município (slicer de seleção única). Pares = mesma NUTS III.

### 03 Radar de mercados
| Visual | Tabelas | Medida |
|---|---|---|
| Matriz de bolhas | 0009930, 0009183 | X `[Cresc. hóspedes %]`, Y `[Estada média mercado]`, tamanho `[Dormidas]` |
| Principais mercados | 0009183 | quota das dormidas de estrangeiros |
| Onde dorme este mercado | 0009183 | top 5 municípios; cross-filter a partir da bolha |
| Leitura dos quadrantes | derivado | classifica cada mercado face às médias |
| KPIs | 0009930, 0009183 | `[Quota internacional]`, `[HHI]`, `[Top 3 %]` |

### 04 Mapa de oportunidades
| Visual | Tabelas | Medida |
|---|---|---|
| Gap oferta-procura | 0009877, 0009874 | `[Cresc. dormidas %] - [Cresc. quartos %]` no período |
| Quota oferta vs procura por segmento | 0009874, 0009877 | quotas por `tipo_alojamento` |
| RevPAR por classificação | 0009929 | valor publicado (não agregar) |
| Dimensão vs utilização | 0009873, 0009874, 0009877 | `[Quartos por estab.]` vs `[Dormidas por quarto]` |
| KPI receita estimada | 0009929, 0009874 | RevPAR × quartos × dias (confirmar unidade temporal do RevPAR no metadado INE) |

### 05 Alentejo em números
Capítulos (bookmarks no Power BI): evolução 2015–2025 em índice; sazonalidade; litoral vs interior; mercados estrangeiros. Tabela de exploração livre com exportação e drill-through para o Raio-X. Valores NULL mostram-se como "conf.".

### 06 Barómetro do empresário
| Visual | Tabelas | Medida |
|---|---|---|
| KPIs do mês (dormidas, estada, peso no Alentejo, mês mais fraco) | 0010735, 0010736 | `[Dormidas mês]`, `[Var. homóloga mês %]` |
| Perfil mensal concelho vs Alentejo vs Portugal | 0010735, 0009808 | quota de cada mês no ano |
| Variação homóloga por mês | 0010735 | por `segmento_alojamento` |
| Calendário mês × ano | 0010735 | mapa de calor (matriz com formatação condicional) |
| Onde há margem para crescer | derivado | meses com quota abaixo do perfil regional |

Filtros: município, segmento, mês.

### 07 Noites e Quartos
Três páginas Power BI, alternadas por botões (bookmarks):

| Página | Visuais | Tabelas |
|---|---|---|
| Procura | KPIs (dormidas, hóspedes, estada, quota internacional, mês de pico); hóspedes e dormidas por mês; dormidas por NUTS III, por tipo (2024 vs 2025) e top concelhos; estada média por tipo | 0009808, 0009812, 0009876, 0009877, 0009183 |
| Oferta | KPIs (estabelecimentos, quartos, quartos/estab., quartos/km², peso TER); quartos por tipo 2015–2025; quartos por NUTS III; estabelecimentos por tipo; hotelaria por classificação; dimensão média | 0009873, 0009874, 0008350 |
| Equilíbrio | Indicador de referência `[Noites por quarto]`; índice 2015 = 100 dormidas vs quartos; noites por quarto por tipo; dispersão crescimento quartos vs dormidas por concelho (diagonal = crescimento igual); tabela de desequilíbrios | 0009874, 0009877 |

```dax
Noites por quarto = DIVIDE ( [Dormidas], [Quartos] )
Quartos = CALCULATE ( SUM ( f_oferta[quartos] ), d_alojamento[tipo_alojamento] = "Total" )
Gap oferta-procura p.p. = ( [Cresc. dormidas %] - [Cresc. quartos %] ) * 100
```
Nota: noites por quarto não é a taxa de ocupação oficial (que exige quartos disponíveis por dia); é um indicador de intensidade de uso da capacidade.

## Revisão v2 (alinhamento com o documento de métricas e públicos)

- Comparação sistemática com Portugal: KPIs com valor nacional, quota nacional, índice 2019 = 100, perfil mensal e mix de tipologias.
- Índice de especialização de mercados = quota no Alentejo ÷ quota em Portugal (quociente de localização).
- Heatmap mês × ano no Pulso e no Barómetro.
- Dimensão `territorio_turistico` (agrupamento próprio de concelhos): Alqueva, Costa Vicentina, Comporta, Património UNESCO, Serra de São Mamede.
- Rodapé de metadados em todas as páginas: fonte, data de atualização, provisório vs definitivo, delimitação territorial.
- Pulso dividido em duas páginas Power BI (visão geral; Alentejo e Portugal).
- Novo dashboard 06 para hoteleiros (operacional, mensal).
- Painéis e KPIs a tracejado = indicadores que exigem fontes novas.

### Fontes a integrar
| Indicador | Fonte | Dashboards |
|---|---|---|
| Intensidade turística (dormidas por 100 hab.) | INE, população residente | 02 |
| Taxa de ocupação-cama e quarto | INE | 04, 06 |
| Proveitos totais e de aposento, ADR | INE | 01, 04, 06 |
| Pipeline de oferta, AL vs habitação | RNT / RNAL, Censos | 02, 04 |
| Gasto com cartões | SIBS | 02, 03 |
| Reputação online, eventos | Booking/Google, ERT | 02, 03 |

Notas: Portugal nas tabelas mensais regionais = soma das NUTS II; nas tabelas municipais a soma nacional é aproximada (segredo estatístico). Excursionistas não têm fonte oficial. A região turística ERT não coincide com a NUTS II.

## Medidas DAX de referência

```dax
Dormidas = CALCULATE ( SUM ( f_procura[dormidas] ), d_alojamento[tipo_alojamento] = "Total" )
Hóspedes = CALCULATE ( SUM ( f_procura[hospedes] ), d_alojamento[tipo_alojamento] = "Total" )
Estada média = DIVIDE ( [Dormidas], [Hóspedes] )
Dormidas por km2 = DIVIDE ( [Dormidas], SUM ( d_municipio[area_km2] ) )
Var. homóloga % =
VAR a = MAX ( d_tempo[ano] )
RETURN DIVIDE ( [Dormidas] - CALCULATE ( [Dormidas], d_tempo[ano] = a - 1 ), CALCULATE ( [Dormidas], d_tempo[ano] = a - 1 ) )
HHI =
VAR tot = CALCULATE ( [Hóspedes mercado], d_mercado[grupo] <> "Portugal" )
RETURN SUMX ( FILTER ( VALUES ( d_mercado[pais] ), d_mercado[grupo] <> "Portugal" ),
              POWER ( DIVIDE ( [Hóspedes mercado], tot ) * 100, 2 ) )
Especialização mercado =
VAR qa = DIVIDE ( [Hóspedes mercado], CALCULATE ( [Hóspedes mercado], ALL ( d_mercado ) ) )
VAR qp = CALCULATE ( qa, REMOVEFILTERS ( d_municipio ) )
RETURN DIVIDE ( qa, qp ) - 1
```

## Regras dos dados (não esquecer)

1. Totais: filtrar sempre `tipo_alojamento = 'Total'` e o total de `local_residencia`. As linhas de detalhe não somam o total (segredo estatístico).
2. Rácios (`estada_media`, `rendimento_medio_por_quarto`) não se somam nem se fazem médias; recalcular a partir de dormidas e hóspedes.
3. `mes` é texto `'01'..'12'`; filtrar sempre com `ano`.
4. NUTS 2013 vs 2024: a tabela 0012093 usa NUTS 2024; criar na dimensão município a coluna `alentejo_nuts2024` (exclui Lezíria do Tejo).
5. `segmento_alojamento` (tabelas mensais municipais) não está normalizado: criar tabela de mapeamento para os tipos das tabelas anuais.

## Próximos passos sugeridos para o Claude Code

- Criar vistas PostgreSQL: `f_procura` (junção de 0009873/74/76/77 pela mesma chave), `d_municipio`, `d_tempo`, `d_alojamento`, `d_mercado`.
- Substituir os dados ilustrativos dos HTML por consultas reais (ou exportar JSON) para validar os números antes do Power BI.
- Gerar o projeto Power BI em formato PBIP/TMDL com as medidas acima e aplicar `powerbi_tema_alentejo.json`.
