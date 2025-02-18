from pykis import PyKis, KisQuote

class Analyst:
    def __init__(self, kis):
        self.kis = kis

    # 시세조회
    def get_stock_quote(self, ticker):
        ''' 엔비디아의 상품 객체를 가져옵니다.

        ticker -- "AAPL"와 같은 기업 심볼
        '''
        stock = self.kis.stock(ticker)

        quote: KisQuote = stock.quote()
        quote: KisQuote = stock.quote(extended=True) # 주간거래 시세

        print(quote)