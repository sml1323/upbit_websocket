# KakaoTalk 알림 설정

카카오톡 "나에게 보내기"로 이상 감지 알림을 받을 수 있습니다 (severity medium 이상).

### 1. Kakao Developers 앱 등록

[Kakao Developers](https://developers.kakao.com/) 접속 -> 앱 생성 -> REST API 키 복사

### 2. 카카오 로그인 설정

- **카카오 로그인** 활성화 ON
- **동의항목** -> `talk_message` 선택 동의
- **Redirect URI**: `https://localhost:3000/callback`

### 3. 토큰 발급

**Step 1)** 브라우저에서 아래 URL을 열고 카카오 로그인 + 동의:

```
https://kauth.kakao.com/oauth/authorize?client_id={REST_API_KEY}&redirect_uri=https://localhost:3000/callback&response_type=code&scope=talk_message
```

**Step 2)** "사이트에 연결할 수 없음" 페이지가 뜨면 정상. **URL 바**에서 `code=` 뒤의 값을 복사:

```
https://localhost:3000/callback?code=여기가_인가코드
```

**Step 3)** 터미널에서 토큰 발급:

```bash
curl -X POST https://kauth.kakao.com/oauth/token \
  -d "grant_type=authorization_code" \
  -d "client_id={REST_API_KEY}" \
  -d "redirect_uri=https://localhost:3000/callback" \
  -d "code={위에서_복사한_인가코드}"
```

**Step 4)** 응답 JSON에서 `access_token`과 `refresh_token`을 복사하여 `.env`에 입력:

```env
KAKAO_REST_API_KEY=your_key
KAKAO_ACCESS_TOKEN=응답의_access_token_값
KAKAO_REFRESH_TOKEN=응답의_refresh_token_값
```

> [!TIP]
> `access_token`은 6시간마다 만료되지만, 시스템이 `refresh_token`으로 자동 갱신합니다.
> `refresh_token`은 2개월 유효. 만료 시 Step 1부터 다시 수행합니다.

> [!WARNING]
> 토큰은 반드시 `.env` 파일에만 보관하세요. 코드, 커밋 메시지, PR, 이슈에 토큰을 노출하지 마세요.
> 토큰이 유출된 경우 [Kakao Developers](https://developers.kakao.com/) > 내 애플리케이션 > 앱 키에서 즉시 재발급하세요.

---

[← README 로 돌아가기](../README.md)
