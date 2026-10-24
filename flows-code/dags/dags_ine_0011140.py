"""Monthly database refresh of annual INE average stays by residence."""

from airflow.sdk import DAG

from dags_ine import build_indicator_dags


globals().update(build_indicator_dags("0011140"))
