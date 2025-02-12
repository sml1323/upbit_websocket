# postgres 설치
```
sudo apt install curl ca-certificates
sudo install -d /usr/share/postgresql-common/pgdg
sudo curl -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc --fail https://www.postgresql.org/media/keys/ACCC4CF8.asc
sudo sh -c 'echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
sudo apt update
sudo apt -y install postgresql
```
### 상태 확인
```
sudo systemctl status postgres.service
```
### role 생성

```
sudo -i -u postgres
psql
CREATE ROLE project WITH LOGIN PASSWORD 'postgres';
```
### pwd 변경
```
ALTER USER postgres WITH PASSWORD 'postgres';
```
### database 생성
```
create database upbit;
\list
```
### database 접속
```
\c upbit
```
### table 목록 조회
```
\dt 
```
## 외부접속 허용 설정
```
cd /etc/postgresql/17/main
sudo vim postgresql.conf 
```
### 60번째 줄 수정 - 외부접속 허용
```
listen_addresses = '0.0.0.0'            # what IP address(es) to listen on;
```

```
sudo vim pg_hba.conf 
```
### host 추가 - 외부 접속 허용  
```
# IPv4 local connections:
host    all             all             127.0.0.1/32            scram-sha-256
host    all             all             0.0.0.0/0            scram-sha-256
```
### postgres 재시작
```
sudo systemctl restart postgresql
```