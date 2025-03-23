from pykis import KisQuote, KisStock
import yfinance
import pandas as pd
from typing import Optional, Tuple, Dict, List
import logging
import requests
from bs4 import BeautifulSoup

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Analyst:
    ''' 분석가: 차트분석 통해 매도&매수주문을 의뢰하는 클래스

    부모클래스임에 주의
    '''
    def __init__(self, kis, config):
        self.kis = kis
        self.config = config

    def get_stock_quote(self, ticker):
        ''' 주식의 시세 정보를 조회하는 함수

        Args:
            ticker (str): 티커 심볼 (예: "AAPL")

        Returns:
            KisQuote: 주식 시세 정보 객체
        '''
        stock = self.kis.stock(ticker)
        quote: KisQuote = stock.quote()
        return quote

    @staticmethod
    def get_nasdaq_top_100() -> List[str]:
        '''나스닥 상위 100개 기업의 티커를 가져오는 함수

        Returns:
            List[str]: 티커 심볼 리스트
        '''
        try:
            # QQQ ETF 정보 가져오기
            qqq = yfinance.Ticker("QQQ")
            
            # QQQ ETF의 실시간 정보 가져오기
            info = qqq.info
            
            if 'holdings' not in info:
                logger.warning("QQQ ETF 구성 종목 정보를 가져올 수 없습니다. 기본 종목 목록을 사용합니다.")
                return Analyst.get_default_tickers()
            
            # 구성 종목 정보에서 티커 추출
            holdings = info['holdings']
            tickers = []
            
            # holdings는 딕셔너리 형태로, 각 종목의 비중 정보를 포함
            for holding in holdings:
                if 'symbol' in holding:
                    tickers.append(holding['symbol'])
            
            # 상위 100개만 선택
            tickers = tickers[:100]
            
            logger.info(f"나스닥 100 기업 목록 가져오기 성공: {len(tickers)}개 기업")
            return tickers
            
        except Exception as e:
            logger.error(f"나스닥 100 기업 정보 조회 실패: {str(e)}")
            return Analyst.get_default_tickers()

    @staticmethod
    def get_default_tickers() -> List[str]:
        '''기본 종목 목록을 반환하는 함수

        Returns:
            List[str]: 기본 티커 심볼 리스트
        '''
        return [
            "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "GOOG", "TSLA", "AVGO", "PEP",
            "COST", "CSCO", "TMUS", "ADBE", "NFLX", "CMCSA", "AMD", "TXN", "HON", "QCOM",
            "AMGN", "INTU", "AMAT", "ISRG", "ADP", "BKNG", "SBUX", "MDLZ", "ADI", "REGN"
        ]

    def generate_recommendations(self):
        ''' 추천 종목을 발생시키는 함수.

        Returns:
            list: 티커 형식의 추천 종목들
        '''
        recommendations = []
        return recommendations

class MACD_Analyst(Analyst):
    '''MACD(Moving Average Convergence Divergence) 기반 분석가 클래스
    
    MACD는 단기 이동평균과 장기 이동평균의 차이를 이용하여 추세를 분석하는 지표입니다.
    
    Attributes:
        default_period (str): 기본 데이터 조회 기간 (예: "60d")
        default_interval (str): 기본 데이터 조회 간격 (예: "1h")
        ema_short (int): 단기 지수이동평균 기간 (기본값: 12)
        ema_long (int): 장기 지수이동평균 기간 (기본값: 26)
        signal_period (int): 시그널 라인 계산 기간 (기본값: 9)
    '''
    
    def __init__(self, kis, config):
        super().__init__(kis, config)
        # MACD 기본 설정값
        self.default_period = config.get('macd_settings', {}).get('period', '60d')
        self.default_interval = config.get('macd_settings', {}).get('interval', '1h')
        self.ema_short = config.get('macd_settings', {}).get('ema_short', 12)
        self.ema_long = config.get('macd_settings', {}).get('ema_long', 26)
        self.signal_period = config.get('macd_settings', {}).get('signal_period', 9)

    def get_macd(self, ticker: str, period: Optional[str] = None, interval: Optional[str] = None) -> Tuple[bool, Dict]:
        '''MACD 지표를 계산하고 매매 신호를 분석하는 함수

        Args:
            ticker (str): 주식 티커 심볼
            period (str, optional): 데이터 조회 기간. 기본값은 설정파일에서 지정
            interval (str, optional): 데이터 조회 간격. 기본값은 설정파일에서 지정

        Returns:
            Tuple[bool, Dict]: 
                - bool: 성공 여부
                - Dict: {
                    'signal': str,  # 'GOLDEN_CROSS', 'DEAD_CROSS', 또는 'NO_SIGNAL'
                    'macd_value': float,  # 현재 MACD 값
                    'signal_value': float,  # 현재 시그널 라인 값
                    'histogram': float,  # MACD 히스토그램 값
                    'error': str  # 오류 발생 시 오류 메시지
                }

        Raises:
            Exception: 데이터 조회 또는 계산 중 오류 발생 시
        '''
        try:
            # 기간 설정
            period = period or self.default_period
            interval = interval or self.default_interval
            
            # 데이터 조회
            data = yfinance.Ticker(ticker).history(period=period, interval=interval)
            
            # 충분한 데이터가 있는지 확인
            min_periods = max(self.ema_long, self.ema_short)
            if len(data) < min_periods:
                return False, {
                    'error': f'충분한 데이터가 없습니다. 필요: {min_periods}개, 현재: {len(data)}개'
                }

            # MACD 계산
            data['EMA12'] = data['Close'].ewm(span=self.ema_short, adjust=False).mean()
            data['EMA26'] = data['Close'].ewm(span=self.ema_long, adjust=False).mean()
            data['MACD'] = data['EMA12'] - data['EMA26']
            data['Signal_Line'] = data['MACD'].ewm(span=self.signal_period, adjust=False).mean()
            data['Histogram'] = data['MACD'] - data['Signal_Line']

            # 최근 데이터 분석
            last_row = data.iloc[-1]
            second_last_row = data.iloc[-2]

            # 신호 분석
            signal = 'NO_SIGNAL'
            if second_last_row['MACD'] > second_last_row['Signal_Line'] and last_row['MACD'] < last_row['Signal_Line']:
                signal = 'DEAD_CROSS'
            elif second_last_row['MACD'] < second_last_row['Signal_Line'] and last_row['MACD'] > last_row['Signal_Line']:
                signal = 'GOLDEN_CROSS'

            return True, {
                'signal': signal,
                'macd_value': last_row['MACD'],
                'signal_value': last_row['Signal_Line'],
                'histogram': last_row['Histogram']
            }

        except Exception as e:
            error_msg = f'MACD 계산 중 오류 발생: {str(e)}'
            logger.error(error_msg)
            return False, {'error': error_msg}

    def generate_recommendations(self):
        '''MACD 신호를 기반으로 매매 추천 목록을 생성

        Returns:
            list: 추천 종목 리스트
        '''
        recommendations = super().generate_recommendations()
        # TODO: MACD 신호를 기반으로 한 추천 로직 구현
        return recommendations