# upbit_websocket
# **Upbit WebSocket 데이터 파이프라인**

---

## **프로젝트 개요**
이 프로젝트는 **업비트(Upbit) 웹소켓 API**를 통해 실시간으로 암호화폐 거래 데이터를 수집하고, 이를 **Kafka(Docker)** 를 통해 처리한 후 **PostgreSQL(TimescaleDB)** 에 저장합니다. 이후 **Apache Airflow**를 이용하여 한 시간마다 데이터를 **Google BigQuery**로 전송하는 ETL 파이프라인을 구축합니다.

---

## **구성 요소**
1. **Upbit WebSocket API**  
   - 업비트의 실시간 거래 데이터를 스트리밍합니다.

2. **Kafka (Docker 환경에서 운영)**  
   - 대량의 실시간 데이터를 효율적으로 처리하기 위한 메시지 브로커 역할을 합니다.

3. **PostgreSQL (TimescaleDB 확장 적용)**  
   - 시계열 데이터 저장을 최적화하여 대용량 데이터를 효과적으로 관리합니다.

4. **Apache Airflow**  
   - 데이터 ETL(추출, 변환, 적재) 파이프라인을 자동화합니다.  
   - 주기적으로 PostgreSQL에서 데이터를 BigQuery로 전송합니다.

5. **Google BigQuery**  
   - 저장된 데이터를 분석 및 시각화할 수 있는 데이터 웨어하우스로 사용됩니다.

---

## **아키텍처 구조**
```bash
┌──────────────────┐       ┌────────────┐       ┌───────────────┐       ┌─────────────┐       ┌───────────┐
│ Upbit WebSocket  │  ---> │ Kafka      │  ---> │ PostgreSQL    │  ---> │ Airflow     │  ---> │ BigQuery  │
│ (실시간 데이터)  │       │ (메시지 브로커) │       │ (TimescaleDB) │       │ (ETL 자동화) │       │ (데이터 분석) │
└──────────────────┘       └────────────┘       └───────────────┘       └─────────────┘       └───────────┘
```

---

## **설치 및 실행 방법**

### **1. 환경 설정**
- **Docker 및 Docker Compose 설치**
```sh
# Add Docker's official GPG key:
sudo apt-get update
sudo apt-get install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update


sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

sudo docker --version
  ```
- **Python 환경 설정**
  ```sh
  pip install -r requirements.txt
  ```

---

### **2. Kafka 컨테이너 실행**
```sh
docker-compose -f kafka-docker-compose.yml up -d
```
- Kafka와 Zookeeper 컨테이너가 실행됩니다.

---

### **3. PostgreSQL, Grafana, TimescalDB 설치**
```sh
docs 를 참고하여 설치
```
- Grafana, TimescaleDB가 실행됩니다.

---

### **4. Airflow DAG 실행**
```sh
cd airflow
# airflow 환경 설정 추가 (권한) 
echo -e "AIRFLOW_UID=$(id -u)\nAIRFLOW_GID=0" >> .env

# airflow docker container 띄우기
sudo docker compose up -d

sudo chmod 666 /var/run/docker.sock

localhost:8081 을 통해 웹 접속
```
- 웹 UI에서 DAG를 실행할 수 있습니다.

---

### **5. 데이터 흐름 확인**
- **Kafka Producer 실행**
  ```sh
  cd upbit-kafka
  python upbit_kafka_producer.py
  ```
  - 업비트 웹소켓 데이터를 Kafka로 전송합니다.

- **Kafka Consumer 실행**
  ```sh
  cd upbit-kafka
  python kafka_to_postgres.py
  ```
  - Kafka에서 데이터를 가져와 PostgreSQL(TimescaleDB)에 저장합니다.

- **Airflow DAG을 실행하여 BigQuery로 데이터 이동**
  - `http://localhost:8081` 에 접속하여 `postgres_to_bigquery_docker_operator` DAG을 실행합니다.



    ### 1. 업비트 실시간 거래 데이터 대시보드
    ![업비트 대시보드](https://private-user-images.githubusercontent.com/124768198/412345623-844ce044-b402-4832-b2a8-149dc4f0b25f.png?jwt=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJnaXRodWIuY29tIiwiYXVkIjoicmF3LmdpdGh1YnVzZXJjb250ZW50LmNvbSIsImtleSI6ImtleTUiLCJleHAiOjE3Mzk3Njk2ODgsIm5iZiI6MTczOTc2OTM4OCwicGF0aCI6Ii8xMjQ3NjgxOTgvNDEyMzQ1NjIzLTg0NGNlMDQ0LWI0MDItNDgzMi1iMmE4LTE0OWRjNGYwYjI1Zi5wbmc_WC1BbXotQWxnb3JpdGhtPUFXUzQtSE1BQy1TSEEyNTYmWC1BbXotQ3JlZGVudGlhbD1BS0lBVkNPRFlMU0E1M1BRSzRaQSUyRjIwMjUwMjE3JTJGdXMtZWFzdC0xJTJGczMlMkZhd3M0X3JlcXVlc3QmWC1BbXotRGF0ZT0yMDI1MDIxN1QwNTE2MjhaJlgtQW16LUV4cGlyZXM9MzAwJlgtQW16LVNpZ25hdHVyZT00MjJkYTRjNmU4NmM1MTYzODgxZmNhNTkzYTE1OGFjYWY0NDYwN2NlMTNiMWI5YjhmNzViYjMxYWE3Y2E0OTMyJlgtQW16LVNpZ25lZEhlYWRlcnM9aG9zdCJ9._-SWUlv_Xp9xnVAN5uXOwHvnx8pOoyJn9ZaAPrEbuIw)

    ### 2. Airflow 로그 (ETL 프로세스)
    ![Airflow 로그](https://private-user-images.githubusercontent.com/124768198/412345624-6c0d4e78-e22f-4b6e-b74c-a1661aa36570.png?jwt=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJnaXRodWIuY29tIiwiYXVkIjoicmF3LmdpdGh1YnVzZXJjb250ZW50LmNvbSIsImtleSI6ImtleTUiLCJleHAiOjE3Mzk3Njk2ODgsIm5iZiI6MTczOTc2OTM4OCwicGF0aCI6Ii8xMjQ3NjgxOTgvNDEyMzQ1NjI0LTZjMGQ0ZTc4LWUyMmYtNGI2ZS1iNzRjLWExNjYxYWEzNjU3MC5wbmc_WC1BbXotQWxnb3JpdGhtPUFXUzQtSE1BQy1TSEEyNTYmWC1BbXotQ3JlZGVudGlhbD1BS0lBVkNPRFlMU0E1M1BRSzRaQSUyRjIwMjUwMjE3JTJGdXMtZWFzdC0xJTJGczMlMkZhd3M0X3JlcXVlc3QmWC1BbXotRGF0ZT0yMDI1MDIxN1QwNTE2MjhaJlgtQW16LUV4cGlyZXM9MzAwJlgtQW16LVNpZ25hdHVyZT03ODRhOWYwZjE2ODVmNmViNTdiZjljNTJjMTg1Y2ZhMDQ1YmQxNWNmNGYxZTBhYzhkY2NhNzQ3ZDUyZjUzZGUzJlgtQW16LVNpZ25lZEhlYWRlcnM9aG9zdCJ9.RyiyBKBUM2qQfDPNCH1a8HYYNI_ju-2yJQlxjVcAcbY)

    ### 3. Bigquery
    ![Bigquery](https://private-user-images.githubusercontent.com/124768198/412345622-58490b74-7f95-4c44-9cec-0c031b4b817a.png?jwt=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJnaXRodWIuY29tIiwiYXVkIjoicmF3LmdpdGh1YnVzZXJjb250ZW50LmNvbSIsImtleSI6ImtleTUiLCJleHAiOjE3Mzk3Njk2ODgsIm5iZiI6MTczOTc2OTM4OCwicGF0aCI6Ii8xMjQ3NjgxOTgvNDEyMzQ1NjIyLTU4NDkwYjc0LTdmOTUtNGM0NC05Y2VjLTBjMDMxYjRiODE3YS5wbmc_WC1BbXotQWxnb3JpdGhtPUFXUzQtSE1BQy1TSEEyNTYmWC1BbXotQ3JlZGVudGlhbD1BS0lBVkNPRFlMU0E1M1BRSzRaQSUyRjIwMjUwMjE3JTJGdXMtZWFzdC0xJTJGczMlMkZhd3M0X3JlcXVlc3QmWC1BbXotRGF0ZT0yMDI1MDIxN1QwNTE2MjhaJlgtQW16LUV4cGlyZXM9MzAwJlgtQW16LVNpZ25hdHVyZT01MjlkZmQ5OTIyNDAzOGE1OTNhY2M5NzAxYjM4ODIyYmJmNzA4NzFjNjVhZjUyZWQ1MGVmZGM2MGY1OTM0NzlmJlgtQW16LVNpZ25lZEhlYWRlcnM9aG9zdCJ9.y4cIiLKl4sdQbElzIItOiE6-_siJ4toqCX74rosByHQ)
---

## **데이터 스키마**
| 컬럼명 | 데이터 타입 | 설명 |
|--------|------------|----------------|
| `time` | `TIMESTAMP` | 거래 발생 시각 |
| `code` | `STRING` | 암호화폐 심볼 (BTC, ETH 등) |
| `trade_price` | `FLOAT` | 거래 가격 |
| `trade_volume` | `FLOAT` | 거래량 |

---


## **결과**
- 업비트 거래 데이터가 **Kafka → PostgreSQL(TimescaleDB) → BigQuery**로 원활하게 전송됨
- Apache Airflow를 활용하여 **자동화된 ETL 프로세스**가 구현됨
- BigQuery에서 **데이터 분석 및 시각화** 가능

---

## **추가 개선 사항**
- **Kafka Streams 적용**하여 데이터 변환 성능 개선
- **Google Cloud Functions**를 활용한 이벤트 기반 데이터 처리

---
