# ASTP : Auto Stock Trading Program

### 특징

- 특정한 매매전략을 구현하는 것이 목표로, 전략은 다음과 같습니다.
    - NDX 지수와 NASDAQ 상장 1, 2위 기업의 비율을 고려하여 주식을 매수합니다.
    - NDX 지수가 폭락하거나, 환율이 과도하게 상승하는 등의 상황에서 보유주식을 전량 매도하고 20영업일간 매매활동을 중지합니다.  
- 파이썬과 한국투자증권이 배포하는 Open API를 사용합니다.
- [Yahoo Finance](https://finance.yahoo.com/quote/NQ=F?p=NQ=F&.tsrc=fin-srch) 크롤링을 통해 NDX 지수를 활용합니다.
- <i>Designed by <b>파양(PAYANG)</b></i>

<br>

### 사전작업

- 한국투자증권에서 계좌를 개설합니다.
- [한국투자증권 API(eFriend Expert)](https://www.truefriend.com/main/customer/systemdown/OpenAPI.jsp?cmd=TF04ea01200) 페이지에서 API 이용을 신청한 후, eFriend Expert 프로그램을 설치합니다.

<br>

### 주의사항

- 한국투자증권 계좌로 API를 신청한 후 APP Key, APP Secret를 발급받아 사용하며, 본 코드의 경우 별도의 mock.key 파일에서 정보를 읽어오도록 구성했습니다.
- 공동인증서 모듈이 64bit를 미지원하는 이슈가 있기 때문에, 코드를 정상적으로 실행하기 위해서는 32bit 가상환경을 구축할 필요가 있습니다. 자세한 것은 [이곳]()을 참조할 수 있습니다.
- 미국 장은 한국시간으로 밤 11:30부터 다음날 아침 6:30까지 열리기 때문에, 일반적인 경우와 달리 ASTP는 코드 동작을 확인할 수 있는 시간에 강한 제약이 있습니다.

<br>

### 예정된 작업

- FinanceDataReader 라이브러리 없이 코드가 동작 가능하도록 변경.
- 출력물 앞에 [2022-02-22-22:22:22]와 안내문 출력 시간대 표시
- 안내문 출력 기록 .txt 등 확장자의 파일로 빌드하는 기능 (Y/N)
- 공황 상황에 대응할 수 있는 함수 추가.
- 매수 한도와 매도 조건 추가
- 클래스 작성 및 함수 유형화
- Android Studio를 통한 안드로이드 어플리케이션 빌드

<br>
<br>
<br>
<br>
<br>

### 예시 동작

![ASTP_example](https://user-images.githubusercontent.com/96360829/210502904-533a39e2-56d7-4b06-9005-06be482e351b.png)

### 코드
 
```python
import mojito

import datetime
from pytz import timezone

import requests
from bs4 import BeautifulSoup

import yfinance as yf

import FinanceDataReader as fdr
import pandas as pd
import re




### 변수 선언란

# 크롤링
response = requests.get('https://finance.yahoo.com/quote/%5ENDX/')

# 기초 계좌정보 연결
mock_acc = open("C:\ASTP\python\mock.key")   # real_acc = open("real.key", 'r')  # 실제 계좌
lines = mock_acc.readlines()
key    = lines[0].strip()
secret = lines[1].strip()
acc_no = lines[2].strip()                                                        # 모의 계좌

# 상위 10개 기업 리스트
top10_stock_list = []

# 액셀 읽기
df_ndf_data = pd.read_excel('C:\\ASTP\\python\\ndq_data.xlsx')
buis_day = 20                                                                    # 20 영업일





### 함수 작성란

# 미국 시간
class time_US:

    # 기초정보고시용
    def guide_form():

        cur_time_US_raw = datetime.datetime.now(timezone('America/New_York'))
        cur_time_US_formed = cur_time_US_raw.strftime("%Y년 %m월 %d일 %H시 %M분 %S초")
        return cur_time_US_formed

    # 엑셀 입력용
    def cell_form():

        cur_time_US_raw = datetime.datetime.now(timezone('America/New_York'))
        cur_time_US_formed = cur_time_US_raw.strftime("%Y.%m.%d %H:%M:%S")
        return cur_time_US_formed


# NDX 크롤링
def get_ndx():

    if response.status_code == 200:
    
        html = response.text
        soup = BeautifulSoup(html, 'html.parser')

        ndx_class = soup.find(class_ = 'Fw(b) Fz(36px) Mb(-4px) D(ib)')
        ndx = re.sub(r'[^0-9]', '', ndx_class.get_text())                        # 문자열에서 특수문자 제거

    else :
        print(response.status_code)
    
    return ndx                                                                   # 리턴값 형식은 str


# 기초정보고시
def get_info():

    bullet = broker.fetch_present_balance()       

    print("\n\n\n"
        + "######################################################################\n"
        + "########################## -프로그램 시작- ###########################\n"
        + "######################################################################\n"
        + "\n"
        + "현재 나스닥-100 지수는 " + get_ndx() + "이며, \n"
        + "미국 뉴욕 현지 시간은 " + time_US.guide_form() + " 입니다. \n"
        + "총자산평가 수치는 다음과 같습니다 : " + bullet['output3']['tot_asst_amt'] + "."
    )


# 나스닥 엑셀 40칸 공백 확인
def if_all_filled():

    all_filled = True

    if len(df_ndf_data) < buis_day * 2:                                          # 하루 장 시작, 종료 시점에 "두 번씩" NDX지수를 입력받는다.
        all_filled = False

    return all_filled


# NDX 엑셀 입력
def write_ndq_data():

    if if_all_filled() == False:                                                 # 40칸이 다 채워지지 않았을 시
        df_ndf_data.loc[len(df_ndf_data)] = {'date'      : time_US.cell_form(),  # 데이터 입력
                                             'ndx_index' : get_ndx()}

        df_ndf_data.to_excel('C:\\ASTP\\python\\ndq_data.xlsx',                  # 엑셀 입력
                          sheet_name = 'ndx_data_20bis_day',
                          index      = False)

    else:                                                                        # 40칸이 다 채워져있을 시
        for row in range(buis_day * 2 - 1):
            df_ndf_data.loc[row] = df_ndf_data.loc[row + 1]                      # 40번째 이전 행 앞으로 이동

        df_ndf_data.loc[buis_day * 2 - 1] = {'date'      : time_US.cell_form(),  # 40번째 행 입력
                                             'ndx_index' : get_ndx()}
        
        df_ndf_data.to_excel('C:\\ASTP\\python\\ndq_data.xlsx',                  # 엑셀 입력
                          sheet_name = 'ndx_data_20bis_day',
                          index      = False)


# NDX -3% 여부 확인
def ndx_collapsed():

    df_ndf_data['ndx_index'] = df_ndf_data['ndx_index'].astype(float)            # 엑셀값 문자열에서 실수로 변경
    ndx_decrse_3per = False

    ndx_max = df_ndf_data['ndx_index'].max()
    ndx_min = df_ndf_data['ndx_index'].min()

    if 100 * (ndx_max - ndx_min) / ndx_max > 3:
        ndx_decrse_3per = True
        print("\nNDX 수치의 변동이 심합니다.\n")
    else:
        print("\nNDX 수치는 안정적입니다.\n")

    return ndx_decrse_3per


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

    if (sstock - fstock) * 100 / sstock > 10:                                   # 1,2위 기업간 시총이 10% 이상 차이날 때
        divrs_invst = False                                                     # diversified investment, 분산 투자
    else:
        divrs_invst = True

    print("\n"
    + "나스닥 시가총액 1위 기업코드는 " + top10_stock_list[0] + ",\n"
    + "나스닥 시가총액 2위 기업코드는 " + top10_stock_list[1] + "입니다.\n"
    )
    
    return divrs_invst


# 주문함수
def stock_buying(symbol_input, price_input):

    resp = broker.create_limit_buy_order(
        symbol   = symbol_input,
        price    = price_input,
        quantity = 1
    )
    print(resp['msg1'])


# 조건부종목주문함수
def if_buy_divrs(divrs_invst):

    info_fstock = broker.fetch_price(top10_stock_list[0])                       # 시총 1위 기업정보
    info_sstock = broker.fetch_price(top10_stock_list[1])                       # 시총 2위 기업정보

    if divrs_invst == True:                                                     # 두 기업의 시가총액이 10% 이상 차이난다면
        print(top10_stock_list[0] + "와 "
            + top10_stock_list[1] + "에는 시가총액상의 큰 차이가 없습니다.\n"
            + top10_stock_list[0] + "의 2주치 매수주문을 올립니다.\n")
        stock_buying(top10_stock_list[0], info_fstock['output']['last'])        # 1위 기업만 매수
        stock_buying(top10_stock_list[0], info_fstock['output']['last'])

    elif divrs_invst == False:                                                  # 그렇지 않은 경우
        print(top10_stock_list[0] + "와"
            + top10_stock_list[1] + "는 시가총액상 큰 차이를 보이고 있습니다.\n"
            + "각각 1주치의 매수주문을 분산하여 올립니다.\n")
        stock_buying(top10_stock_list[0], info_fstock['output']['last'])        # 1, 2위 기업을 분산 매수
        stock_buying(top10_stock_list[1], info_sstock['output']['last'])





### 실질 코드란

if __name__=="__main__":

    # 증권사 객체 생성
    broker = mojito.KoreaInvestment(
    api_key = key,
    api_secret = secret,
    acc_no = acc_no,
    exchange = '나스닥',
    mock = True                                                             # 모의투자 여부
    )

    # 자산고지
    get_info()

    while ndx_collapsed() == False:

        # NDX지수 입력
        write_ndq_data()

        # 상위 10개 기업 산출
        top10_stock_list_maker()

        # 매수종목선정함수 및 매수
        if_buy_divrs(stock_selector())
    
    print("코드를 종료합니다.")
```
