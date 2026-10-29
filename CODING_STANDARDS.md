# Review criteria

The shared-responsibility criteria are judgement calls, not mandatory
abstraction rules. The INE column rules below define output behavior.

## Shared responsibilities

When adding an indicator or processing mode, compare the changed code with
existing callers and helpers, including callers outside the diff.

- Reuse established metadata access and CSV/database output helpers when their
  contracts fit. INE API access belongs in
  [ine_api.py](flows-code/pistadigital/utils/ine_api.py); shared output belongs
  in [ine_output.py](flows-code/pistadigital/utils/ine_output.py).
- Keep indicator-specific schema and transformation in its indicator module.
  Do not generalize transformations merely because they have similar structure.
- If a new block duplicates an existing responsibility, consider a small shared
  function and update both callers. Prefer this over copying the block or
  introducing a framework for hypothetical future indicators.
- Check all affected entry points for preserved filenames, delimiters, empty
  results, database transaction boundaries, and error reporting.

Use the focused tests documented in [the README](README.md#ine-tests)
to verify behavior; successful tests do not replace cross-caller review.

## INE column rules

When creating or updating an INE flow with the following columns, apply these
rules to the transformed rows before CSV/database output. Both outputs and the
returned frame must contain the same filtered, normalized data. Do not change
unrelated existing flows merely to introduce these rules.

### Accommodation labels

When `tipo_alojamento` is present, use its lowercase value for matching without
changing the original `tipo_alojamento`. Apply each replacement only when its
target column exists:

| Match on lowercase `tipo_alojamento` | `classificacao` | `subtipo_alojamento` |
|---|---|---|
| Exactly `alojamento local` | `Alojamento Local` | `Alojamento Local` |
| Contains `rural` | `Turismo no Espaço Rural e de Habitação` | `Turismo no Espaço Rural e de Habitação` |
| Contains `habitação` but not `rural` | `Turismo no Espaço Rural e de Habitação` | Keep original value |
| Otherwise | Keep original value | Keep original value |

Preserve these spellings and accents. Do not broaden exact matching to
substring matching for `alojamento local`.

### Accommodation total and leaf codes

When `tipo_alojamento` is present, retain the API total `T` plus rows whose
`dim_3` code has no subcategory in the period metadata (for example
`010115`, `0103`, `02`, `03`). Drop intermediate codes such as `01` or
`0101`. Keep `T` because INE suppresses many detailed municipal values, so
detail rows do not add up to the total. Levels below a code repeat that
code's own API label (`T` gives `Total`; `0103` sets `classificacao` to
`Pousadas/Quintas da Madeira`).

### Municipality-level geography

When `municipio` is present, retain only rows whose API `geocod` is a
seven-character municipality code. Decide on the API code, not on the
`Total` labels written for aggregate geography levels. Flows with
`nuts_ii` but no `municipio` (9808, 9812, 12093) retain only two-character
NUTS II codes, dropping `PT` and NUTS I rows.

### Implementation and verification

- Keep indicator-specific mappings in the flow module. Reuse
  `accommodation_fields` and `filter_detail_rows` in
  [ine_transform.py](flows-code/pistadigital/utils/ine_transform.py) for the
  common column rules. The
  [annual](flows-code/pistadigital/utils/ine_annual.py) and
  [monthly](flows-code/pistadigital/utils/ine_monthly.py) runners already
  filter after validation and before output; do not duplicate orchestration.
- Preserve source validation, schema/column order, metrics, and period
  replacement safeguards. A filtered-empty result must retain its CSV header
  and must not delete existing database data.
- Test mixed-case accommodation labels, the `habitação`-only distinction,
  unchanged labels, each aggregate geocode level, retained `T`, dropped
  intermediate accommodation codes, filtered-empty output, and identical
  filtering for CSV and database output. Check that unrelated flows retain
  their existing behavior.
