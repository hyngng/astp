from pykis import KisQuote
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Analyst:
    ''' 분석가: 차트분석 통해 매도&매수주문을 의뢰하는 클래스

    부모클래스임에 주의
    '''
    def __init__(self, kis):
        self.kis = kis

    def get_stock_quote(self, ticker):
        ''' 주식의 시세 정보를 조회하는 함수

        Args:
            ticker (str): 티커 심볼 (예: "AAPL")

        Returns:
            KisQuote: 주식 시세 정보 객체
        '''
        stock = self.kis.stock(ticker).quote
        quote: KisQuote = stock.quote()
        return quote

    def get_nasdaq_top_100(self):
        '''나스닥 상위 100개 기업의 티커를 가져오는 함수

        Returns:
            List[str]: 티커 심볼 리스트
        '''
        try:
            url = 'https://en.wikipedia.org/wiki/Nasdaq-100'

            tables = pd.read_html(url)

            if len(tables) <= 4:
                logger.warning("Wikipedia에서 나스닥 100 테이블을 찾을 수 없습니다. 기본 종목 목록을 사용합니다.")
                return self.get_default_tickers()

            nasdaq_df = tables[4]  

            if 'Ticker' not in nasdaq_df.columns:
                tickers = nasdaq_df.iloc[:, 1].tolist()
            else:
                tickers = nasdaq_df['Ticker'].tolist()

            tickers = [str(ticker) for ticker in tickers if str(ticker) != 'nan']
            
            logger.info(f"위키피디아로부터 나스닥 100 기업 목록 가져오기 성공")
            return tickers

        except Exception as e:
            logger.error(f"위키피디아로부터 나스닥 100 기업 정보 조회 실패: {str(e)}")
            return self.get_default_tickers()

    def get_default_tickers(self):
        '''기본 종목 목록을 반환하는 함수

        Returns:
            List[str]: 기본 티커 심볼 리스트
        '''
        
        # config.yaml에서 가져오도록 수정
        return [
            "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "GOOG", "TSLA", "AVGO", "PEP",
            "COST", "CSCO", "TMUS", "ADBE", "NFLX", "CMCSA", "AMD", "TXN", "HON", "QCOM",
            "AMGN", "INTU", "AMAT", "ISRG", "ADP", "BKNG", "SBUX", "MDLZ", "ADI", "REGN"
        ]
    
