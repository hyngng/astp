from pykis import KisQuote, KisStock
import yfinance
import pandas



class Analyst:
    ''' 분석가: 차트분석 통해 매도&매수주문을 의뢰하는 클래스

    부모클래스임에 주의
    '''
    def __init__(self, kis):
        self.kis = kis

    def get_stock_quote(self, ticker):
        ''' 엔비디아의 상품 객체를 가져오는 함수. 시세조회를 위해 쓰일 수 있음.

        args:
            ticker -- 티커 심볼. "AAPL"처럼 입력바람.
        '''
        stock = self.kis.stock(ticker)
        quote: KisQuote = stock.quote()

        return quote

    def get_nasdaq_100(self):
        # 나스닥 100 지수 티커: ^NDX

        qqq = yfinance.Ticker('QQQ')
    
        # QQQ의 holdings 정보를 가져옵니다 (상장된 종목 목록)
        holdings = qqq.get_holdings()

        # holdings에서 tickers만 추출
        tickers = [holding['symbol'] for holding in holdings['components']]
        print(tickers)

    def generate_recommendations(self):
        ''' 추천 종목을 발생시키는 함수.

        returns:
            list: 티커 형식의 추천 종목들
        '''
        recommendations = []
        # recommendations.append()

        return recommendations



class MACD_Analyst(Analyst):
    def get_macd(self, ticker):
        ''' MACD를 구하는 함수. 하루에 한 번, 장 종료 시점에 구함.

        returns:
            pandas.core.frame.DataFrame: 
        '''
        data = yfinance.Ticker(ticker).history(period= "60d" , interval= "1h" )

        data['EMA12'] = data[ 'Close' ].ewm(span= 12 , adjust= False ).mean() # 26주기 EMA 계산
        data['EMA26'] = data[ 'Close' ].ewm(span= 26 , adjust= False ).mean() # MACD(12주기 EMA와 26주기 EMA의 차이) 계산
        data ['MACD'] = data['EMA12'] - data['EMA26'] 
        data[ 'Signal_Line' ] = data[ 'MACD' ].ewm(span= 9 , adjust= False ).mean()

        last_row = data.iloc[-1]
        second_last_row = data.iloc[-2]

        if second_last_row['MACD'] > second_last_row['Signal_Line'] and last_row['MACD'] < last_row['Signal_Line']:
            print('급락이 (신호선 아래로 교차)')
        elif second_last_row['MACD'] < second_last_row['Signal_Line'] and last_row['MACD'] > last_row['Signal_Line']:
            print('급등이 (신호선 위로 교차)')
        else:
            print('크로스오버 없음')

    def generate_recommendations(self):
        super().generate_recommendations()

        # MACD