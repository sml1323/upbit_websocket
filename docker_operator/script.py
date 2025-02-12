import os
import datetime
import pandas as pd
import psycopg2
from decimal import Decimal
from google.oauth2 import service_account
from google.cloud import bigquery

# -------------------------------------------------------------------
# 1. PostgreSQL(TimescaleDB)에서 데이터 추출
# -------------------------------------------------------------------

# PostgreSQL 연결 정보 (환경에 맞게 수정)
pg_conn_info = {
    "dbname": "coin",       # 예: timescaledb
    "user": "postgres",     # 예: postgres
    "password": "postgres", # 예: 비밀번호
    "host": "172.17.0.1",    # 예: localhost 또는 DB 서버 IP
    "port": 5432            # 기본 PostgreSQL 포트
}

# 시간 조건을 위한 변수 (UTC 기준)
now = datetime.datetime.utcnow()
one_hour_ago = now - datetime.timedelta(hours=1)

# 추출할 데이터에 대한 SQL 쿼리 (지난 1시간 분량)
pg_query = f"""
    SELECT time, code, trade_price, trade_volume
    FROM trade_data
    WHERE time >= '{one_hour_ago.isoformat()}'
      AND time < '{now.isoformat()}';
"""

print("PostgreSQL 데이터 추출 시작...")
with psycopg2.connect(**pg_conn_info) as conn:
    df = pd.read_sql_query(pg_query, conn)
print(f"PostgreSQL에서 {len(df)} 행 추출 완료.")

# -------------------------------------------------------------------
# 2. 데이터 타입 변환 (pyarrow 변환 오류 방지를 위함)
# -------------------------------------------------------------------

# 2-1. time 컬럼: datetime으로 변환 후, 타임존 정보를 제거 (BigQuery TIMESTAMP와 호환)
df['time'] = pd.to_datetime(df['time'], utc=True)
df['time'] = df['time'].dt.tz_convert(None)

# 2-2. trade_price, trade_volume: float 대신 Python의 Decimal 타입으로 변환  
#     (BigQuery NUMERIC은 Arrow의 Decimal128 형식을 기대)
df['trade_price'] = df['trade_price'].apply(lambda x: Decimal(str(x)) if x is not None else None)
df['trade_volume'] = df['trade_volume'].apply(lambda x: Decimal(str(x)) if x is not None else None)

# 2-3. code 컬럼: 혹시 bytes 타입이면 문자열로 변환
df['code'] = df['code'].apply(lambda x: x.decode('utf-8') if isinstance(x, bytes) else str(x))

# (변환 후 데이터 타입 확인)
print("DataFrame dtypes:")
print(df.dtypes)

# -------------------------------------------------------------------
# 3. BigQuery에 데이터 업로드
# -------------------------------------------------------------------

# BigQuery 서비스 계정 키 파일 및 프로젝트 정보
SERVICE_ACCOUNT_FILE = "./carbon-scene-443505-t5-ffd099044cea.json" # 서비스 계정 JSON 파일 경로 (예: /path/to/api_key.json)
project_id = "carbon-scene-443505-t5"          # 본인의 프로젝트 ID로 수정

# 서비스 계정 인증 후 BigQuery 클라이언트 생성
credentials = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE)
bq_client = bigquery.Client(credentials=credentials, project=project_id)

# BigQuery 대상 테이블 정보  
# (미리 생성되어 있어야 하며, 테이블 스키마는 다음과 같이 되어 있다고 가정합니다.)
#  - time: TIMESTAMP
#  - code: STRING
#  - trade_price: NUMERIC
#  - trade_volume: NUMERIC
dataset_id = "project"  # 예: my_dataset
table_id = "trade_data" # 예: trade_data

table_ref = bq_client.dataset(dataset_id).table(table_id)

# 로드 작업 구성 (데이터를 기존 테이블에 추가)
job_config = bigquery.LoadJobConfig(
    write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
)

print("BigQuery 로드 작업 시작...")
load_job = bq_client.load_table_from_dataframe(df, table_ref, job_config=job_config)
load_job.result()  # 로드 작업 완료까지 대기

print(f"BigQuery에 {load_job.output_rows} 행 업로드 완료.")
