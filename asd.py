import asyncio
import websockets
import json
import logging
import requests
import os # 파일 경로 및 존재 여부 확인용

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Upbit Data Fetching Functions ---
def get_coin_symbols() -> list:
    """
    업비트 REST API를 통해 'KRW-'로 시작하는 코인 심볼 목록을 가져옵니다.

    - return: 코인 심볼 리스트
    """
    url = "https://api.upbit.com/v1/market/all"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for HTTP errors
        markets = response.json()
        symbols = [market['market'] for market in markets if market['market'].startswith("KRW-")]
        logging.info(f"Fetched {len(symbols)} coin symbols from Upbit.")
        return symbols
    except Exception as e:
        logging.exception("Failed to fetch coin symbols.")
        raise e

async def subscribe_upbit(file_path: str = "upbit_ticker_data.json"):
    """
    업비트 웹소켓에 구독 요청을 보내고,
    수신한 ticker 메시지를 지정된 JSON 파일에 저장합니다.

    - file_path: 데이터를 저장할 JSON 파일 경로
    """
    coin_symbols = get_coin_symbols()
    ws_uri = "wss://api.upbit.com/websocket/v1"

    # 파일이 이미 존재하면 경고 메시지를 출력합니다.
    if os.path.exists(file_path):
        logging.warning(f"Warning: File '{file_path}' already exists. New data will be appended.")
    else:
        logging.info(f"Creating new file: '{file_path}'")

    while True:
        try:
            async with websockets.connect(ws_uri) as websocket:
                subscribe_data = [
                    {"ticket": "test"},
                    {"type": "ticker", "codes": coin_symbols, "isOnlySnapshot": False, "isOnlyRealtime": True}
                ]
                await websocket.send(json.dumps(subscribe_data))
                logging.info("웹소켓 구독 시작! (Upbit WebSocket subscription started!)")
                while True:
                    data = await websocket.recv()
                    message = json.loads(data)

                    # JSON 데이터를 파일에 한 줄씩 추가
                    with open(file_path, 'a', encoding='utf-8') as f:
                        json.dump(message, f, ensure_ascii=False)
                        f.write('\n') # 각 JSON 객체 뒤에 줄바꿈 추가
                    
                    # 콘솔에도 출력 (선택 사항)
                    if "trade_price" in message and "code" in message:
                        logging.info(f"Saved and Received: {message['code']} - Current Price: {message['trade_price']:,} KRW")
                    else:
                        logging.info(f"Saved and Received: {message}")

        except websockets.exceptions.ConnectionClosedOK:
            logging.warning("웹소켓 연결이 정상적으로 종료되었습니다. 재연결 시도 중... (WebSocket connection closed gracefully. Attempting to reconnect...)")
        except websockets.exceptions.WebSocketException as e:
            logging.error(f"웹소켓 오류 발생: {e}. 재연결 시도 중... (WebSocket error: {e}. Attempting to reconnect...)")
        except Exception as e:
            logging.exception(f"예상치 못한 오류 발생: {e}. 재연결 시도 중... (Unexpected error: {e}. Attempting to reconnect...)")
        await asyncio.sleep(5)  # Wait before attempting to reconnect

# --- Main execution block ---
async def main():
    # 데이터를 저장할 파일 경로를 지정합니다.
    # 기본값은 "upbit_ticker_data.json" 입니다.
    await subscribe_upbit(file_path="upbit_ticker_data.json") 

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("프로그램 종료. (Program terminated by user.)")