"""Monthly guest counts by segment, one INE DAG per year/month."""

from airflow.sdk import DAG

from dags_ine import build_indicator_dags


globals().update(build_indicator_dags("0010736", monthly=True))
