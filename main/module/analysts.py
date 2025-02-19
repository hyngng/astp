from pykis import KisQuote, KisStock
import yfinance
import pandas



class Analyst:
    ''' 분석가: 차트분석 통해 매도&매수주문을 의뢰하는 클래스

    부모클래스임에 주의
    '''
    def __init__(self, kis):
        self.kis = kis

    # 시세조회
    def get_stock_quote(self, ticker):
        ''' 엔비디아의 상품 객체를 가져오는 함수.

        args:
            ticker -- 티커 심볼. "AAPL"처럼 입력바람.
        '''
        stock = self.kis.stock(ticker)
        quote: KisQuote = stock.quote()

        return quote

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
            
        '''
        # start_date는 3달 전으로 하면 될듯. "YYYY-MM-DD" 형식임.
        data = yfinance.download(ticker, start=start_date, end=end_date)

        # 12일과 26일 EMA 계산
        data['EMA12'] = data['Close'].ewm(span=12, adjust=False).mean()
        data['EMA26'] = data['Close'].ewm(span=26, adjust=False).mean()

        # MACD Line 계산
        data['MACD'] = data['EMA12'] - data['EMA26']

        # Signal Line 계산 (MACD의 9일 EMA)
        data['Signal_Line'] = data['MACD'].ewm(span=9, adjust=False).mean()

        # MACD Histogram 계산
        data['MACD_Histogram'] = data['MACD'] - data['Signal_Line']

        # 결과 출력
        return data[['Close', 'MACD', 'Signal_Line', 'MACD_Histogram']].tail()

    def generate_recommendations(self):
        super().generate_recommendations()

        # MACD