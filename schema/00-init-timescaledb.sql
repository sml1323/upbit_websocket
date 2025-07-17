-- TimescaleDB 초기화 스크립트
-- 이 파일은 PostgreSQL 컨테이너 시작시 자동으로 실행됩니다

-- TimescaleDB extension 활성화
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- 사용자 생성 (이미 존재하면 무시)
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_user WHERE usename = 'upbit_user') THEN
        CREATE USER upbit_user WITH ENCRYPTED PASSWORD 'upbit_password';
    END IF;
END $$;

-- 데이터베이스 생성 (이미 존재하면 무시)
SELECT 'CREATE DATABASE upbit_analytics OWNER upbit_user'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'upbit_analytics')\gexec

-- 권한 부여
GRANT ALL PRIVILEGES ON DATABASE upbit_analytics TO upbit_user;

-- upbit_analytics 데이터베이스에 연결하여 초기 설정
\c upbit_analytics;

-- TimescaleDB extension 활성화 (데이터베이스별로 필요)
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- 권한 부여
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO upbit_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO upbit_user;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO upbit_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO upbit_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO upbit_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO upbit_user;

-- 로그 출력
\echo 'TimescaleDB extension has been enabled successfully'
\echo 'Database upbit_analytics and user upbit_user created successfully'