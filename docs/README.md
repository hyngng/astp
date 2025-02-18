## ASTP (2025)

- 로보어드바이저(RA) 프로그램

### 알고리즘

- MACD

## 기술사항

**사용 라이브러리**

| 라이브러리명 | 역할 |
| [python-kis](https://github.com/Soju06/python-kis) | 한국투자증권이 제공하는 매수&매도용 라이브러리 |
|  |  |

### 클래스 구조

**크게 두 가지 유형의 클래스로 작동함**

- Leader: 상위 라이브러리로서 매수&매도주문을 올림
    - 큐 자료형에 등록된 모든 주문을 일정시간마다 처리함
- Analyst: 하위 라이브러리로서 차트를 분석하고 매수&매도주문을 큐에 등록함

## 유의사항

- 모의투자 API를 직접 생성할 때 모의투자에 더불어 실전투자의 `app_key`와 `app_secret`가 함께 필요함
    - YAML을 이용하여 불러오려 했더니 이런 문제가 있었음
    - [이곳](https://github.com/Soju06/python-kis/issues/39) 참고바람

## 참고

- [한국투자 OpenAPI 문서(공식)](https://apiportal.koreainvestment.com/apiservice/oauth2#L_5c87ba63-740a-4166-93ac-803510bb9c02)