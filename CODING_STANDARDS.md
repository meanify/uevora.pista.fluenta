# Review criteria

These are judgement calls for code review, not mandatory abstraction rules.

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

Use the focused tests documented in [the README](flows-code/README.md#ine-tests)
to verify behavior; successful tests do not replace cross-caller review.
