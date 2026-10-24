"""Shared factory and virtualenv task for all per-indicator INE DAG files."""

import pendulum

from airflow.sdk import DAG
from airflow.providers.standard.operators.python import PythonVirtualenvOperator


YEARS_LOOKBACK = 2
PUBLISHED_YEAR_CAPS = {"0008350": 2022}


def execute_indicator(indicator, year, month=None):
    """Run in the virtual environment and return only a compact status."""
    import importlib
    import logging

    from pistadigital.utils.ine_output import validate_period

    validate_period(year, month)
    logger = logging.getLogger("airflow.task")
    module = importlib.import_module(
        f"pistadigital.utils.ine_{indicator}_flow"
    )
    if module.MONTHLY != (month is not None):
        raise ValueError(f"INE {indicator} received an incompatible month argument.")
    options = dict(varcd=indicator, ano=year, exportar_csv=False, gravar_bd=True)
    if month is not None:
        options["mes"] = month
    frame = module.processar_indicador_ine(**options)
    period = f"year {year}" if month is None else f"month {year}-{month:02d}"
    if frame is None:
        raise RuntimeError(f"INE {indicator} returned no result for {period}.")
    if frame.empty:
        result = f"WARNING: No records for INE {indicator}, {period}. Existing data kept."
        logger.warning(result)
    else:
        result = (
            f"SUCCESS: Loaded {len(frame)} records for INE {indicator}, "
            f"{period}. Processing {'year' if month is None else 'month'} "
            "replaced; no CSV exported."
        )
        logger.info(result)
    return result


def create_dag(indicator: str, year: int, month: int | None = None) -> DAG:
    period_id = str(year) if month is None else f"{year}_{month:02d}"
    with DAG(
        f"ine_{indicator}_{period_id}",
        start_date=pendulum.datetime(2025, 12, 1),
        schedule="0 6 1 * *",
        default_args={
            "owner": "PISTA Digital",
            "depends_on_past": False,
            "email_on_failure": True,
            "email_on_retry": False,
            "email": "meanify@gmail.com",
            "retries": 1,
            "retry_delay": pendulum.duration(minutes=5),
        },
        tags=["ine", f"ine_{indicator}"],
        catchup=False,
    ) as dag:
        PythonVirtualenvOperator(
            task_id=f"task_ine_{indicator}_{period_id}",
            python_callable=execute_indicator,
            op_args=[indicator, year] if month is None else [indicator, year, month],
            python_version="3.13.2",
            requirements=[
                "requests>=2.32.5", "pandas>=2.3.3",
                "psycopg2-binary>=2.9.11", "sqlalchemy>=2.0.45",
                "apache-airflow[otel]", "apache-airflow[cncf.kubernetes]",
            ],
            inherit_env=True,
            env_vars={
                "PISTA_DB_HOSTNAME": "{{ conn.pista_db.host }}",
                "PISTA_DB_PORTNUMBER": "{{ conn.pista_db.port }}",
                "PISTA_DB_NAME": "{{ conn.pista_db.schema }}",
                "PISTA_DB_USERNAME": "{{ conn.pista_db.login }}",
                "PISTA_DB_PASSWORD": "{{ conn.pista_db.password }}",
            },
            system_site_packages=True,
        )
    return dag


def build_indicator_dags(indicator: str, *, monthly: bool = False) -> dict[str, DAG]:
    """Return DAGs for registration by the indicator's own entry-point file."""
    current_year = pendulum.now().year
    end_year = min(current_year, PUBLISHED_YEAR_CAPS.get(indicator, current_year))
    dags = {}
    for year in range(end_year - YEARS_LOOKBACK, end_year + 1):
        for month in (range(1, 13) if monthly else (None,)):
            dag = create_dag(indicator, year, month)
            dags[dag.dag_id] = dag
    return dags
