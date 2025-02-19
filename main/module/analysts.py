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

        ticker -- 티커 심볼. "AAPL"처럼 입력바람.
        '''
        stock = self.kis.stock(ticker)
        quote: KisQuote = stock.quote()

        return quote

    def generate_recommendations(self):
        ''' 추천 종목을 발생시키는 함수.
        '''
        recommendations = []
        # recommendations.append()

        return recommendations

class MACD_Analyst(Analyst):
    def get_macd():
        ''' MACD를 구하는 함수. 하루에 한 번, 장 종료 시점에 구함.
        '''
        pass

    def generate_recommendations():
        super().generate_recommendations()

        # MACD