# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a real-time cryptocurrency data pipeline that collects trading data from Upbit WebSocket API, processes it through Kafka, stores it in PostgreSQL with TimescaleDB extension, and transfers it to Google BigQuery via Apache Airflow for analysis.

## Architecture

The data flow follows this pattern:
```
Upbit WebSocket → Kafka → PostgreSQL (TimescaleDB) → Airflow → BigQuery
```

## Key Components

### 1. Data Collection (`upbit-kafka/`)
- **producer.py**: Connects to Upbit WebSocket API and sends ticker data to Kafka
- **consumer.py**: Consumes data from Kafka and stores it in PostgreSQL/TimescaleDB
- Uses confluent-kafka for message broker operations

### 2. Message Broker
- Kafka runs in Docker containers (kafka-compose.yml)
- Topic: `upbit_ticker` (configurable via .env)
- Zookeeper for cluster coordination

### 3. Data Storage
- PostgreSQL with TimescaleDB extension for time-series optimization
- Table: `trade_data` with columns: time, code, trade_price, trade_volume

### 4. ETL Pipeline (`airflow/`)
- **dags.py**: Hourly DAG that transfers data from PostgreSQL to BigQuery
- Uses DockerOperator to run ETL script in containerized environment
- **docker_operator/script.py**: Handles data extraction, transformation, and BigQuery upload

## Development Commands

### Environment Setup
```bash
# Install Python dependencies
pip install -r requirements.txt

# Set up Airflow environment
cd airflow
echo -e "AIRFLOW_UID=$(id -u)\nAIRFLOW_GID=0" >> .env
```

### Infrastructure
```bash
# Start Kafka cluster
docker-compose -f kafka-compose.yml up -d

# Start Airflow
cd airflow
sudo docker compose up -d
sudo chmod 666 /var/run/docker.sock
```

### Data Pipeline
```bash
# Start data producer (collects from Upbit WebSocket)
cd upbit-kafka
python producer.py

# Start data consumer (saves to PostgreSQL)
cd upbit-kafka
python consumer.py
```

### Services Access
- Airflow Web UI: http://localhost:8081 (admin/airflow)
- Kafka: localhost:9092
- PostgreSQL: localhost:5432

## Environment Variables

Configure via .env file:
- `KAFKA_SERVERS`: Kafka bootstrap servers (default: localhost:9092)
- `KAFKA_TOPIC`: Topic name (default: upbit_ticker)
- `KAFKA_GROUP_ID`: Consumer group (default: default_group)
- `TIMESCALEDB_*`: Database connection parameters

## Data Schema

PostgreSQL/TimescaleDB `trade_data` table:
- `time`: TIMESTAMP (trade occurrence time)
- `code`: STRING (crypto symbol, e.g., BTC, ETH)
- `trade_price`: FLOAT (trading price)
- `trade_volume`: FLOAT (trading volume)

BigQuery schema mirrors PostgreSQL with NUMERIC types for precise decimal handling.

## Docker Images

The project uses:
- `wurstmeister/kafka:latest` and `wurstmeister/zookeeper:latest` for message broker
- `apache/airflow:2.10.3` for workflow orchestration
- Custom `load_to_bigquery:1.0` image for ETL operations (built from docker_operator/)

## Important Notes

- The KafkaProducerClient class handles WebSocket reconnection automatically
- ETL script converts data types for BigQuery compatibility (Decimal for precise numeric handling)
- Airflow DAG runs hourly and processes the previous hour's data
- TimescaleDB provides optimized time-series data storage and querying