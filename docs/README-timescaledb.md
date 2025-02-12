# TimescaleDB 설치 및 설정 가이드

PostgreSQL에 TimescaleDB를 설치하고 설정하는 방법입니다.

## 1. TimescaleDB 패키지 추가

```bash
echo "deb https://packagecloud.io/timescale/timescaledb/ubuntu/ $(lsb_release -c -s) main" | sudo tee /etc/apt/sources.list.d/timescaledb.list
```

## 2. TimescaleDB GPG 키 설치

```bash
wget --quiet -O - https://packagecloud.io/timescale/timescaledb/gpgkey | sudo apt-key add -
```

## 3. 패키지 업데이트

```bash
sudo apt update
```

## 4. TimescaleDB 설치

PostgreSQL 버전에 맞춰 설치합니다.

### PostgreSQL 16

```bash
sudo apt install timescaledb-2-postgresql-16 postgresql-client-16
```

### PostgreSQL 17

```bash
sudo apt install timescaledb-2-postgresql-17 postgresql-client-17
```

## 5. TimescaleDB 구성

```bash
sudo timescaledb-tune
```

## 6. PostgreSQL 재시작

```bash
sudo systemctl restart postgresql
```

## 7. PostgreSQL 상태 확인

```bash
sudo systemctl status postgresql.service
```

## 8. PostgreSQL 접속 및 설정

```bash
sudo -i -u postgres psql \list
\du
ALTER USER postgres WITH PASSWORD 'postgres';
```

## 9. 데이터베이스 생성

```sql
CREATE DATABASE coin;
\list
```

## 10. TimescaleDB 확장 추가

```sql
CREATE EXTENSION IF NOT EXISTS timescaledb;
\dx
```

## 11. 테이블 생성

```sql
CREATE TABLE trade_data (
    time TIMESTAMPTZ NOT NULL,
    code TEXT NOT NULL,
    trade_price NUMERIC,
    trade_volume NUMERIC
);
\dt
```

## 12. 하이퍼테이블 생성

```sql
SELECT create_hypertable('trade_data', 'time');
```

## 13. 데이터 삽입 (예시)

```sql
INSERT INTO trade_data (time, code, trade_price, trade_volume) VALUES ('2024-10-27 10:00:00+00', 'BTC', 100.0, 1.0);
\q
exit
```