## ASTP (2025)

- 로보어드바이저(RA) 프로그램

## 기술사항

**사용 라이브러리**

| 라이브러리명 | 역할 | 비고 |
| --- | --- | --- |
| [python-kis](https://github.com/Soju06/python-kis)[^1] | 매수&매도주문을 요청하기 위함. | 한국투자증권이 제공. |
| yfinance | MACD와 같은 주식 보조 지표를 얻기 위함. | pandas를 필수적으로 요구함. |

**알고리즘**

> 차후 memrmaid로 포팅할 계획

나스닥 상위 10개 기업에 대해 금일 MACD 구하기, 일정 기준 이상이면 매수하기.

`main.py` 또는 `traders.py`에서 관리하는 `watchlist: list`

**클래스 구조**

> 크게 두 가지 유형의 클래스로 작동함

- `Leader`: 상위 라이브러리로서 매수&매도주문을 올림
    - 큐 자료형에 등록된 모든 주문을 일정시간마다 처리함
- `Analyst`: 하위 라이브러리로서 차트를 분석하고 매수&매도주문을 큐에 등록함

## 유의사항

- 모의투자 API를 직접 생성할 때 모의투자에 더불어 실전투자의 `app_key`와 `app_secret`가 함께 필요함
    - YAML을 이용하여 불러오려 했더니 이런 문제가 있었음
    - 자세한 사항은 [이곳](https://github.com/Soju06/python-kis/issues/39) 참고바람

## 고민거리

잠자리가 불안해지지 않을까?

## 참고

- [한국투자 OpenAPI 문서(공식)](https://apiportal.koreainvestment.com/apiservice/oauth2#L_5c87ba63-740a-4166-93ac-803510bb9c02)
- [MACD 지표의 python 코드 작성 (Pandas library and Dictionary)](https://pioneergu.github.io/posts/macd-code/#%EC%8B%A4%EC%8B%9C%EA%B0%84-macd-%EC%A7%80%ED%91%9C-%EB%AA%A8%EC%9D%98-%EA%B3%84%EC%82%B0)
- [파이썬으로 MACD 지표 구축](https://medium.com/@financial_python/building-a-macd-indicator-in-python-190b2a4c1777)

[^1]: 티커 심볼을 입력받아 거래량, 거래대금, 시가총액, EPS, BPS, PER, PBR, 52주 최고가, 52주 최저가, 시가, 고가, 저가, 종가, 변동폭을 제공받을 수 있음.