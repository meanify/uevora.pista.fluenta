# Workspace navigation

- Application code and usage: [flows-code/README.md](flows-code/README.md).
- CLI dispatch: [flows-code/pistadigital/cli/](flows-code/pistadigital/cli/).
- INE API helpers: [ine_api.py](flows-code/pistadigital/utils/ine_api.py).
- INE CSV/database output: [ine_output.py](flows-code/pistadigital/utils/ine_output.py).
- Database environment variables: [database.py](flows-code/pistadigital/utils/database.py)
  and the README's Configuration section. Do not hardcode credentials.
- Tests: [flows-code/tests/](flows-code/tests/). From the workspace root:
  `cd flows-code && ../.venv/bin/python -m unittest discover -s tests`.
- Scheduled flows: [flows-code/dags/](flows-code/dags/);
  deployment configuration: [k8s/](k8s/).
- Review criteria: [CODING_STANDARDS.md](CODING_STANDARDS.md).

Scope code searches to `flows-code/pistadigital`, `flows-code/dags`, and
`flows-code/tests` first. `.venv` contains dependencies, not project source.

For usage questions, explain existing behavior before proposing changes.
For explicitly requested, behavior-preserving refactors, implement the agreed
scope without repeating design approval. Use brainstorming for unresolved
feature or behavior choices, not routine explanations or mechanical extractions.
