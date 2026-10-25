""" Airflow DAGs for Perfil dos Visitantes Individual e Grupo """
import pendulum

from airflow.sdk import task
from airflow.sdk import DAG
from airflow.sdk import Connection, Variable
from airflow.providers.standard.operators.empty import EmptyOperator
from airflow.providers.standard.operators.python import PythonVirtualenvOperator
from airflow.providers.standard.operators.bash import BashOperator
import logging

import pistadigital.flows.limesurvey_flows as flows_utils
# from utils.mappings.mappings import survey_mappings as survey_mappings

# https://airflow.apache.org/docs/apache-airflow/stable/_api/airflow/example_dags/index.html

pistadb_conn = Connection.get("pista_db")
limesurvey_conn = Connection.get("limesurvey")

logger = logging.getLogger("airflow.task")

dags = [
    {'id_prefix': 'limesurvey_visitante', 'survey': '000000', 'start':'2025-01-01T00:05:00', 'schedule': '*/30 * * * *', 'display_name': 'Utilizado para Debugging'}, 
    {'id_prefix': 'limesurvey_visitante', 'survey': '762625', 'start':'2025-01-01T00:10:00', 'schedule': '*/30 * * * *', 'display_name': 'Perfil do Visitante Individual'},
    {'id_prefix': 'limesurvey_visitante', 'survey': '666914', 'start':'2025-01-01T00:15:00', 'schedule': '*/30 * * * *', 'display_name': 'Perfil do Visitante Grupo'},
    {'id_prefix': 'limesurvey_visitante', 'survey': '237583', 'start':'2025-01-01T00:20:00', 'schedule': '*/30 * * * *', 'display_name': 'Perceção de Turismo dos Residentes do Alentejo e Ribatejo'},
    {'id_prefix': 'limesurvey_visitante', 'survey': '416252', 'start':'2025-01-01T00:25:00', 'schedule': '*/30 * * * *', 'display_name': 'Gestão de Energia'},
    {'id_prefix': 'limesurvey_visitante', 'survey': '321593', 'start':'2025-01-01T00:30:00', 'schedule': '*/30 * * * *', 'display_name': 'Gestão de Água'},
    {'id_prefix': 'limesurvey_visitante', 'survey': '247644', 'start':'2025-01-01T00:35:00', 'schedule': '*/30 * * * *', 'display_name': 'Gestão de Resíduos'},
    {'id_prefix': 'limesurvey_visitante', 'survey': '368732', 'start':'2025-01-01T00:40:00', 'schedule': '*/30 * * * *', 'display_name': 'Barometro de Turismo'},
]

def execute_sync_pistadigital(survey, from_response_id, increment):
    """Example of a synchronous task."""
    import pistadigital.flows.limesurvey_flows as flows_utils
    import logging

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    logger = logging.getLogger("airflow.task")
    logger.error("ERROR")
    logger.warning("WARNING")
    logger.info("INFO")
    logger.debug("DEBUG")


    result = flows_utils.export_and_load(survey, from_response_id, increment)
    if result:
        logger.info(f"Executed export and load for survey {survey} with result: {result}")
    else:
        logger.info(f"Export and load for survey {survey} returned no result.")
    return result

def create_dag(id_prefix: str, survey: str, schedule: str) -> DAG:
    """Create a DAG for the given parameters."""
    dag_id = f"{id_prefix}_{survey}"
    start_date = pendulum.datetime(2025, 12, 1)
    default_args = {
        'owner': 'PISTA Digital',
        'depends_on_past': False,
        'email_on_failure': True,
        'email_on_retry': False,
        'email': 'meanify@gmail.com',
        'retries': 0,
    }

    with DAG(dag_id, start_date=start_date, schedule=schedule, default_args=default_args, tags=["perfil_visitante"]) as dag:

        pista_visitante = PythonVirtualenvOperator(
            task_id=f"task_{id_prefix}_{survey}",
            python_callable=execute_sync_pistadigital,
            op_args=[survey, None, 1000],
            python_version='3.13.2',
            requirements=["citric>=2.0.0",
                         "pandas>=2.3.3",
                         "psycopg2-binary>=2.9.11",
                         "sqlalchemy>=2.0.45",
                         "apache-airflow[otel]",
                         "apache-airflow[cncf.kubernetes]"],
            inherit_env=True,
            env_vars={
                'PISTA_DB_HOSTNAME': f"{pistadb_conn.host}",
                'PISTA_DB_PORTNUMBER': f"{pistadb_conn.port}",
                'PISTA_DB_NAME': f"{pistadb_conn.schema}",
                'PISTA_DB_USERNAME': f"{pistadb_conn.login}",
                'PISTA_DB_PASSWORD': f"{pistadb_conn.password}",
                'LIME_SURVEY_URL': f"{limesurvey_conn.host}",
                'LIME_SURVEY_USERNAME': f"{limesurvey_conn.login}",
                'LIME_SURVEY_PASSWORD': f"{limesurvey_conn.password}",
                'PISTAFLOWS_EXPORTS_PATH': '/opt/app/exports'
            },
            system_site_packages=True
        )
    
    return dag


for each_dag in dags:
    ID_PREFIX = each_dag["id_prefix"]
    SURVEY = each_dag["survey"]
    SCHEDULE = each_dag["schedule"]

    globals()[f"{ID_PREFIX}_{SURVEY}"] = create_dag(ID_PREFIX, SURVEY, SCHEDULE)
