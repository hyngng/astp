from pykis import KisQuote

class Analyst:
    ''' 분석가: 차트분석 통해 매도&매수주문을 의뢰하는 클래스
    '''
    def __init__(self, kis):
        self.kis = kis

    # 시세조회
    def get_stock_quote(self, ticker):
        ''' 엔비디아의 상품 객체를 가져옵니다.

        ticker -- 티커 심볼. "AAPL"처럼 입력바람.
        '''
        stock = self.kis.stock(ticker)

        quote: KisQuote = stock.quote()
        quote: KisQuote = stock.quote(extended=True) # 주간거래 시세

        print(quote)