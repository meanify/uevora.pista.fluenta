""" Airflow DAGs for Perfil dos Visitantes Individual e Grupo """
import pendulum

from airflow.sdk import task
from airflow.sdk import DAG
from airflow.providers.standard.operators.bash import BashOperator


dag_id = "install_python_dependencies"
start_date = pendulum.datetime(2025, 12, 1)
schedule = "@once"
default_args = {
    'owner': 'PISTA Digital',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
}

with DAG(dag_id, start_date=start_date, schedule=schedule, default_args=default_args, tags=["install_python_dependencies"]) as dag:

    install = BashOperator(
        task_id="install_python_dependencies",
        bash_command="pip install -r /opt/airflow/dags/requirements.txt"
    )

