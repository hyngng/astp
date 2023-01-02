<h1>ASTP : Auto Stock Trading Program</h1>

<h3>특징</h3>

- <i>Designed by <b>PAYANG</b></i>
- 목표 : "영략" 구현
    - 나스닥-100 지수와 나스닥 상장 1위 기업과 2위 기업의 비율만을 고려하여 주식 매수
    - 나스닥-100 지수 폭락 혹은 과도한 환율 상승 등의 이벤트가 발생했을 때, 보유주식 전량 매도 및 20영업일간 매매활동 중지
- 파이썬 이용
- 한국투자증권 Open API 이용
- 미국 주식거래 특화
- [Yahoo Finance](https://finance.yahoo.com/quote/NQ=F?p=NQ=F&.tsrc=fin-srch) 페이지 크롤링을 통한 NASDAQ-100 지수 활용
- NASDAQ 상장 상위 10개 기업 리스트 활용

---

<h3>사전작업</h3>

- 한국투자증권 계좌 개설
- [한국투자증권 API(eFriend Expert)](https://www.truefriend.com/main/customer/systemdown/OpenAPI.jsp?cmd=TF04ea01200) 다운 및 설치

<h3>주의사항</h3>

- 한국투자증권 계좌개설 및 해당 계좌로 API 신청 후 APP Key, APP Secret 발급 필수  
    - 모의계좌의 경우도 별도의 APP Key, APP Secet 발급 필수  
- 공동인증서 모듈의 64bit 미지원 이슈로 코드는 32bit 가상환경에서의 실행 필요
- 미국 장은 한국시간으로 밤 11:30부터 다음날 아침 6:30까지 진행됨
    - 그렇기 때문에, 코드가 실제로 의도대로 작동하는지 확인할 수 있는 시간에는 강력한 제약이 있음.

---

<h3>예정된 작업</h3>

- FinanceDataReader 라이브러리로부터 독립  
- 디스코드 알림 기능 추가  
- 국내주식 대응 함수 추가  
- 공황대응함수 작성
- 매수 한도 추가  
- 매도 조건 추가  
- +++ 기능이 많아질 시, 클래스 작성을 통한 함수 분류 및 유형화  
- +++ UI를 갖춘 독립 프로그램 생성
- +++ 가능하다면, Android 애플리케이션으로 이주

<br/><br/><br/><br/>

---
 
<h3>코드</h3>
 
```python
import mojito
import pprint
import datetime
from pytz import timezone

import requests
from bs4 import BeautifulSoup

import yfinance as yf
import FinanceDataReader as fdr
import pandas as pd





### 변수 선언란

# 크롤링
url = 'https://finance.yahoo.com/quote/%5ENDX/'
response = requests.get(url)

# 기초 계좌정보 연결
mock_acc = open("mock.key", 'r')   # real_acc = open("real.key", 'r')            # 실제 계좌
lines = mock_acc.readlines()
key    = lines[0].strip()
secret = lines[1].strip()
acc_no = lines[2].strip()                                                        # 모의 계좌

# 상위 10개 기업 리스트
top10_stock_list = []





### 함수 작성란

# NASDAQ-100 크롤링
def get_ndx():

    if response.status_code == 200:
    
        html = response.text
        soup = BeautifulSoup(html, 'html.parser')

        # HTML 태그 내 클래스명으로 검색, 텍스트 추출
        ndx_class = soup.find(class_ = 'Fw(b) Fz(36px) Mb(-4px) D(ib)')
        ndx = ndx_class.get_text()

    else :
        print(response.status_code)
    
    return ndx


# 기초정보고시
def my_acc():

    print("나스닥 100 지수는 " + get_ndx() + "이며, ")

    # 미국 현지 시간
    cur_time_US_raw = datetime.datetime.now(timezone('America/New_York'))
    cur_time_US = cur_time_US_raw.strftime("%Y년 %m월 %d일 %H시 %M분 %S초")
    print("미국 뉴욕 현지 시간은 " + str(cur_time_US) + " 입니다.")

    bullet = broker.fetch_present_balance()                                      # 잔고조회
    print("총자산평가 : " + bullet['output3']['tot_asst_amt'])


# 나스닥 상위 10개 기업 리스트 생성
def top10_stock_list_maker():

    # FinanceDataReader, 거래소 + 시총 상위 10위 기업
    df_nsq = fdr.StockListing('NASDAQ')

    for i in range(10):
        top10_stock_list.append(df_nsq.iloc[i, 0]) # 행, 열


# 매수종목선정함수
def stock_selector():

    fstock = yf.Ticker(top10_stock_list[0]).info["marketCap"]                   # 시가총액 1위
    sstock = yf.Ticker(top10_stock_list[1]).info["marketCap"]                   # 시가총액 2위

    print("나스닥 시가총액 1위 기업은 " + top10_stock_list[0] + ",\n"
        + "나스닥 시가총액 2위 기업은 " + top10_stock_list[1])

    if (sstock - fstock) * 100 / sstock > 10:                                   # 1,2위 기업간 시총이 10% 이상 차이날 때
        divider = False
    else:
        divider = True
    
    return divider


# 종목주문함수
def stock_buying(divider):

    info_fstock = broker.fetch_price(top10_stock_list[0])                       # 시총 1위 기업정보
    info_sstock = broker.fetch_price(top10_stock_list[1])                       # 시총 2위 기업정보

    if divider == True:                                                         # 두 기업의 시가총액이 10% 이상 차이난다면
        print("시총 1, 2위 기업 간 차이 심함")
        resp     = broker.create_limit_buy_order(                               # 1위 기업만 매수
            symbol   = top10_stock_list[0],
            price    = info_fstock['output']['last'],
            quantity = 1
        )
        print(resp)

    elif divider == False:                                                      # 그렇지 않은 경우
        print("시총 1, 2위 기업 간 차이 심하지 않음")
        resp     = broker.create_limit_buy_order(                               # 1위, 2위 기업 매수
            symbol   = top10_stock_list[0],
            price    = info_sstock['output']['last'],
            quantity = 1
        )
        pprint.pprint(resp)

        resp     = broker.create_limit_buy_order(
            symbol   = top10_stock_list[1],
            price    = info_sstock['output']['last'],
            quantity = 1
        )
        pprint.pprint(resp)


# 공황대응함수
def crisis_activated():
    print("임시 코드, 작성 예정")





### 실질 코드란

# 메인함수
if __name__=="__main__":

    while True:
        # 증권사 객체 생성
        broker = mojito.KoreaInvestment(
        api_key = key,
        api_secret = secret,
        acc_no = acc_no,
        exchange = '나스닥',
        mock = True                                                             # 모의투자 여부
        )
        
        # 자산고지
        my_acc()

        # 상위 10개 기업 산출
        top10_stock_list_maker()

        # 매수종목선정함수 실행 및 종목주문
        stock_buying(stock_selector())
```