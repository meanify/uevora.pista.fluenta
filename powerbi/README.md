# Pista Digital – Power BI template

Power BI Project (PBIP / PBIR) following
[design/pistadigital.uevora.pt-DESIGN.md](../design/pistadigital.uevora.pt-DESIGN.md).

## Open

1. Power BI Desktop → Options → Preview features → enable **Power BI Project (.pbip) save option**
   and **Store reports using enhanced metadata format (PBIR)**.
2. Open `PistaDigital.pbip`.
3. Install the Montserrat font (Google Fonts) on every machine that edits the report.

## Make a `.pbit` template

File → Export → Power BI template. Replace the `Exemplo` table in the semantic
model with the real data source first.

## Layout (1280 × 720)

- Content area: x 0–1040. Header band (navy, 96 px) with a 4 px gold rule.
- **Navigation bar on the right**: x 1040–1280 (240 px), navy, brand block on top and a
  vertical page navigator below. Selected page is gold, hover is `#154373`.
- Every page repeats the same header/brand/navigator. To add a page, duplicate an
  existing one so the navigation bar stays identical; the navigator lists new pages itself.

## Theme

`PistaDigital.Report/StaticResources/RegisteredResources/PistaDigitalTheme.json`:
navy `#001F44`, gold `#FFAD00`, link `#2066BC`, ink `#1D2127`, hairline `#4E4F50`,
Montserrat, 0 px corner radius, no shadows, navy table headers.
