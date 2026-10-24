"""Monthly database refresh of annual INE room counts."""

from airflow.sdk import DAG

from dags_ine import build_indicator_dags


globals().update(build_indicator_dags("0009874"))
