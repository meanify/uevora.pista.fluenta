"""Monthly database refresh of annual INE territorial areas through 2022."""

from airflow.sdk import DAG

from dags_ine import build_indicator_dags


globals().update(build_indicator_dags("0008350"))
