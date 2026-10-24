"""Monthly database refresh of INE overnight stays, one DAG per year/month."""

from airflow.sdk import DAG

from dags_ine import build_indicator_dags


globals().update(build_indicator_dags("0009808", monthly=True))
