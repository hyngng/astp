from typing import Optional, Tuple, Dict
import yfinance
import logging

from ..analyst import Analyst

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MACD_Analyst(Analyst):
    '''MACD 분석가
    
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