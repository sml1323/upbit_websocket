# grafana docker 설치

```bash
docker run -d -p 3000:3000 --name grafana grafana/grafana
```

## grafana 외부 접속 허용

### 기존 컨테이너 삭제
```bash
docker stop grafana
docker rm grafana
```
### 루트 사용자로 컨테이너 실행

```bash
docker run -d --name=grafana -p 3000:3000 --user root grafana/grafana
```
```bash
docker exec -it grafana /bin/sh
vi /etc/grafana/grafana.ini

http_addr = 0.0.0.0
```

## grafana에서 postgres 에 접근하기 위한 설정
```bash
ip a | grep docker0
3: docker0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default 
    inet 172.17.0.1/16 brd 172.17.255.255 scope global docker0
18: veth9bd6aad@if17: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue master docker0 state UP group default 
```

```bash
sudo vim /etc/postgresql/17/main/pg_hba.conf 

# 설정 추가
host    all             all             172.17.0.1/16          md5
```


## grafana 접속 - localhost:3000
- ad, pw : admin, admin
- Data sources
    - postgres 
        - 172.17.0.1
        - db
        - id
        - pw




