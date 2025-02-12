# PostgreSQL 설치 및 설정

## 설치

```bash
sudo apt install curl ca-certificates
sudo install -d /usr/share/postgresql-common/pgdg
sudo curl -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc --fail https://www.postgresql.org/media/keys/ACCC4CF8.asc
sudo sh -c 'echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
sudo apt update
sudo apt -y install postgresql
```

## 상태 확인

```bash
sudo systemctl status postgres.service
```

## Role 생성 및 비밀번호 변경

```bash
sudo -i -u postgres
psql
CREATE ROLE project WITH LOGIN PASSWORD 'postgres';
ALTER USER postgres WITH PASSWORD 'postgres';
```

## 데이터베이스 생성 및 접속

```bash
create database upbit;
\list
\c upbit
```

## 테이블 목록 조회

```bash
\dt
```

## 외부 접속 허용 설정

### `postgresql.conf` 수정

```bash
cd /etc/postgresql/17/main
sudo vim postgresql.conf
```

60번째 줄 수정:

```
listen_addresses = '0.0.0.0'
```

### `pg_hba.conf` 수정

```bash
sudo vim pg_hba.conf
```

다음 줄 추가:

```
host    all             all             0.0.0.0/0            scram-sha-256
```

## PostgreSQL 재시작

```bash
sudo systemctl restart postgresql
```