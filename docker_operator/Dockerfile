FROM python:3.11.9  

# ETL 스크립트와 필요한 파일 복사
COPY script.py /app/script.py
COPY carbon-scene-443505-t5-ffd099044cea.json /app/carbon-scene-443505-t5-ffd099044cea.json
COPY requirements.txt /app/requirements.txt

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
 && rm -rf /var/lib/apt/lists/*


# # Python 라이브러리 설치
RUN pip install -r /app/requirements.txt




WORKDIR /app

# 기본 실행 명령
CMD ["python", "etl_script.py"]