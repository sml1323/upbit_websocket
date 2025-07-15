-- TimescaleDB 초기화 스크립트
-- 이 파일은 PostgreSQL 컨테이너 시작시 자동으로 실행됩니다

-- TimescaleDB extension 활성화
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- 로그 출력
\echo 'TimescaleDB extension has been enabled successfully'