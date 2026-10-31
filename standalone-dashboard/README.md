# Tourism dashboards (HTML)

Seven dashboards about tourism in the Alentejo, built from the v2 mockups in
[`powerbi/mockups`](../powerbi/mockups) and fed by live, read-only queries over
the INE tables (`ine_*_ds`) in the Pista Digital PostgreSQL database. Panels
that need data sources not yet loaded (occupancy, ADR, population, card
spending, ...) are shown dashed, as in the mockups.

| Page (in `frontend/`) | Audience | Shows |
|---|---|---|
| `index.html` | Everyone | Links to the dashboards and the years loaded |
| `01_pulso_alentejo.html` | Turismo do Alentejo, CCDR | Volume, seasonality, position among NUTS II regions |
| `02_raio_x_concelho.html` | Municipalities | Tourism pressure, monthly calendar, markets, compared with peer municipalities |
| `03_radar_mercados.html` | Tourism promotion | Market growth vs length of stay, concentration, where each market stays |
| `04_mapa_oportunidades.html` | Investors | Demand vs supply growth, RevPAR by category, size vs use |
| `05_alentejo_em_numeros.html` | Academia, media, public | Headline numbers, story in chapters and a sortable, exportable table |
| `06_barometro_empresario.html` | Hoteliers, accommodation managers | Monthly profile of a municipality and segment against the region and Portugal |
| `07_noites_e_quartos.html` | Technicians, ERT, investors | Demand, supply and the balance between them (nights per room), in three tabs |

## How it works

`standalone-dashboard` is self-contained: it does not import the flows
package (`pistadigital` in `flows-code`) and can be copied or deployed on its
own.

A browser cannot connect to PostgreSQL directly, so the pages are served by a
small Python server. The pages call `/api/<dashboard>`; the server reads the
tables, computes the indicators and returns JSON. The pages draw it with
Chart.js.

```
standalone-dashboard/
├── dashboards.py          entry point: starts the server
├── requirements.txt       Python packages
├── backend/
│   ├── server.py          HTTP server: serves frontend/ and the /api/ JSON
│   ├── queries.py         reads the INE tables (Alentejo and Portugal), shared helpers
│   ├── measures.py        pure measures (Gini, HHI, quadrants, weighted means)
│   ├── database.py        loads .env and connects to PostgreSQL
│   └── dashboards/        one module per dashboard: its /api/ route and data
├── frontend/
│   ├── index.html, 01_…07_*.html   the pages
│   └── assets/            common.css, common.js (header, footer, API calls,
│                          charts, heatmap, formatting)
└── tests/                 tests per dashboard and a shared fixture; no database needed
```

The server only serves `.html`, `.css` and `.js` files inside `frontend/`;
the Python code, this README and any `.env` are never sent to the browser.

Opening the `.html` files directly from disk (double-click) does **not** work:
they need the server for their data.

## Requirements

- Python 3.13 or newer with the packages in `requirements.txt`. The
  workspace's `.venv` already has them; for a separate environment:

  ```bash
  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
  ```

- Database access through these variables, which a read-only user is
  enough for: `PISTA_DB_HOSTNAME`, `PISTA_DB_PORTNUMBER`, `PISTA_DB_NAME`,
  `PISTA_DB_USERNAME`, `PISTA_DB_PASSWORD`. They are read from the
  environment, then from `standalone-dashboard/.env`, then from the
  workspace root `.env`. Values already set are never replaced.
- Internet access in the browser: the pages load Chart.js and the Public Sans
  font from public CDNs.

## Run

From `standalone-dashboard`, using the workspace's environment:

```bash
cd standalone-dashboard
../.venv/bin/python dashboards.py
```

Or with a separate environment created here: `.venv/bin/python dashboards.py`.

Then open <http://127.0.0.1:8050/>. Stop the server with `Ctrl+C`.

Options:

| Option | Default | Meaning |
|---|---|---|
| `--host` | `127.0.0.1` | Interface to listen on. Use `0.0.0.0` to allow other machines on the network. |
| `--port` | `8050` | Port. |
| `--ttl` | `1800` | Seconds the tables stay cached before they are read again. |

Example, shared on the local network on port 9000:

```bash
../.venv/bin/python dashboards.py --host 0.0.0.0 --port 9000
```

To read the database again immediately (for example after an INE flow ran),
open any API address with `refresh=1`, e.g.
<http://127.0.0.1:8050/api/meta?refresh=1>, then reload the page.

## Filters and links

Filters are kept in the address, so a view can be bookmarked or shared:

```
02_raio_x_concelho.html?municipio=Odemira&ano=2025
01_pulso_alentejo.html?ano=2024&terr=2013
04_mapa_oportunidades.html?inicio=2019&fim=2024&seg=Alojamento%20local
```

`terr=2024` (default) is the Alentejo NUTS 2024, without Lezíria do Tejo;
`terr=2013` includes it.

## API

| Address | Parameters |
|---|---|
| `/api/meta` | none: years available, municipalities, segments |
| `/api/pulso` | `ano`, `terr` |
| `/api/raio-x` | `municipio`, `ano` |
| `/api/radar` | `ano`, `base` (`anterior` or `2019`), `terr` |
| `/api/oportunidades` | `inicio`, `fim`, `seg` (`Total`, `Hotelaria`, `Alojamento local`, `TER e habitação`), `terr` |
| `/api/numeros` | `ano`, `terr` |
| `/api/barometro` | `municipio`, `seg`, `mes` (`AAAA-MM`; default: latest month published) |
| `/api/noites-quartos` | `ano`, `seg`, `terr` (one call for the three tabs; the page keeps `tab` in its address) |

Invalid values return HTTP 400 with `{"erro": "..."}`; database failures
return 502.

## Reading the numbers

- Totals come from the INE total rows, never from adding detail rows.
- Values the INE keeps confidential appear as "conf.", never as zero.
- When an indicator has no data for the selected year, the latest earlier year
  is used and the page says which year (rooms, establishments and RevPAR have
  missing years in the database).
- The INE publishes RevPAR only per municipality; regional and national RevPAR
  are estimates weighted by rooms.
- Portugal is the sum of all municipalities (annual tables) or the INE
  Portugal row (monthly regional tables); municipal sums are close lower
  bounds because of confidential values.
- Annual accommodation data starts in 2017, so long-run indices use
  2017 = 100 where the mockups say 2015.
- Tourism territories (Alqueva, Costa Vicentina, Comporta, Património UNESCO,
  Serra de São Mamede) are own groupings of municipalities, set in
  `TOURISM_TERRITORIES` in `backend/queries.py`. The members of Serra de São
  Mamede (Marvão, Castelo de Vide, Portalegre) are an assumption: the mockup
  does not list them.
- "Noites por quarto" (nights ÷ rooms) measures how intensively the capacity is
  used; it is not the official occupancy rate.

## Tests

From `standalone-dashboard`:

```bash
../.venv/bin/python -m unittest discover -v -s tests
```

These tests are not part of the flows suite in `flows-code/tests`.

## Troubleshooting

| Symptom | Cause |
|---|---|
| "Não foi possível contactar o servidor dos dashboards" | The server is not running, or the page was opened from disk instead of through `http://127.0.0.1:8050/`. |
| "Missing database settings: ..." in the terminal | A `PISTA_DB_*` variable is not set. |
| `ModuleNotFoundError: No module named 'pandas'` (or `sqlalchemy`, `dotenv`) | The Python used has not got `requirements.txt` installed; use the workspace `.venv` or install them. |
| "Falha ao consultar a base de dados" on the page | The database is unreachable or the credentials are wrong; the terminal shows the details. |
| `Address already in use` | Port 8050 is taken; use `--port`. |
| Charts missing, numbers shown, red message about Chart.js | No internet access to the Chart.js CDN (`cdnjs.cloudflare.com`), or a firewall blocks it. |
| Blank charts or `... is not defined` in the browser console after an update | The browser kept old files from before the server sent `Cache-Control: no-cache`. Reload once with `Cmd+Shift+R` (macOS) or `Ctrl+F5`. |
| A chart shows "Sem dados ..." | No published data for that year or territory (monthly municipal data starts in 2020, markets in 2018). |
