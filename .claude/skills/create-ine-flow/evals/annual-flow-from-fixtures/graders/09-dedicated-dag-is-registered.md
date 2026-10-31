---
type: llm
focus: trace
weight: 1
---

A dedicated flows-code/dags/dags_ine_0009875.py was added without needing a
separate user request. It exposes annual DAGs using the shared factory, is
discoverable by Airflow's default safe-mode scan, and does not duplicate DAG IDs.
Tests cover registration, the scheduled year window, task arguments, database-only
output, credential templates, and propagated failures. README deployment guidance
includes both the entry point and shared factory. No deployment or production
database writes were performed.
