from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    'owner': 'braulio',
    'depends_on_past': False,
    'retries': 0,
    'retry_delay': timedelta(minutes=5),
}

# Caminho dentro do container spark-master
DBT_PROJECT_PATH = '/opt/spark/scripts/dbt/bitcoin_analytics'

with DAG(
    dag_id='bitcoin_analytics_pipeline',
    default_args=default_args,
    description='Pipeline: Extrai Bitcoin -> Iceberg -> dbt',
    schedule_interval='@hourly',
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['bitcoin', 'iceberg', 'dbt'],
) as dag:

    # Task 1: Extrair dados das APIs
    extract = BashOperator(
        task_id='extract_bitcoin_prices',
        bash_command='docker exec spark-master spark-submit /opt/spark/scripts/extract_bitcoin_prices.py',
    )

    # Task 2: Rodar dbt via spark-master
    transform = BashOperator(
        task_id='dbt_run',
        bash_command=f'docker exec spark-master dbt run --project-dir {DBT_PROJECT_PATH} --profiles-dir {DBT_PROJECT_PATH}',
    )

    # Task 3: Rodar testes dbt
    test = BashOperator(
        task_id='dbt_test',
        bash_command=f'docker exec spark-master dbt test --project-dir {DBT_PROJECT_PATH} --profiles-dir {DBT_PROJECT_PATH}',
    )

    # Ordem de execução
    extract >> transform >> test
