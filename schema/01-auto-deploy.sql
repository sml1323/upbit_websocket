-- 자동 스키마 배포 스크립트
-- 이 파일은 데이터베이스 초기화 후 자동으로 실행됩니다

-- 스키마 배포 시작 로그
\echo 'Starting automatic schema deployment...'

-- 1. 기본 테이블 스키마 생성
\i /docker-entrypoint-initdb.d/ticker_data_schema.sql

-- 2. MCP 함수 생성
\i /docker-entrypoint-initdb.d/mcp_functions.sql

-- 3. 기술적 지표 함수 생성
\i /docker-entrypoint-initdb.d/technical_indicators.sql

-- 4. 예측 알고리즘 함수 생성
\i /docker-entrypoint-initdb.d/prediction_algorithms.sql

-- 5. 연속 집계 테이블 생성
\i /docker-entrypoint-initdb.d/03-continuous-aggregates.sql

-- 스키마 배포 완료 로그
\echo 'Schema deployment completed successfully!'

-- 함수 확인
\echo 'Checking created functions...'
SELECT proname, pronargs FROM pg_proc WHERE proname LIKE 'get_%' OR proname LIKE 'detect_%' OR proname LIKE 'calculate_%';

-- 테이블 확인
\echo 'Checking created tables...'
\dt

-- 연속 집계 테이블 확인
\echo 'Checking continuous aggregates...'
SELECT view_name, materialized_only FROM timescaledb_information.continuous_aggregates;