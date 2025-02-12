from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.utils.dates import days_ago

default_args = {
    'owner': 'airflow',
    'start_date': days_ago(1),
}

with DAG(
    dag_id='postgres_to_bigquery_docker_operator',
    default_args=default_args,
    schedule_interval='@hourly',
    catchup=False,
    description='ETL 작업을 DockerOperator로 실행하여 PostgreSQL 데이터를 BigQuery로 업로드'
) as dag:
    
    etl_task = DockerOperator(
        task_id='run_etl',
        image='load_to_bigquery:1.0',
        api_version='auto',
        auto_remove=True,
        command='python /app/script.py',
        docker_url='unix://var/run/docker.sock',
        network_mode='host',    # host 네트워크 사용 (호스트의 localhost 접근)
        mount_tmp_dir=False     # 임시 볼륨 마운트 비활성화
    )

    etl_task
