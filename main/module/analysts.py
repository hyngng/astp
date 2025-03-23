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
            # Wikipedia에서 나스닥 100 기업 목록 가져오기
            url = 'https://en.wikipedia.org/wiki/Nasdaq-100'
            
            # pandas를 사용하여 테이블 데이터 가져오기
            tables = pd.read_html(url)
            
            # 나스닥 100 구성종목 테이블은 일반적으로 4번째 테이블(인덱스 4)에 있음
            if len(tables) <= 4:
                logger.warning("Wikipedia에서 나스닥 100 테이블을 찾을 수 없습니다. 기본 종목 목록을 사용합니다.")
                return Analyst.get_default_tickers()
                
            nasdaq_df = tables[4]  
            
            # 'Ticker' 컬럼이 있는지 확인
            if 'Ticker' not in nasdaq_df.columns:
                # 컬럼명이 다를 수 있으므로 첫 번째 컬럼을 사용
                tickers = nasdaq_df.iloc[:, 1].tolist()
            else:
                tickers = nasdaq_df['Ticker'].tolist()
                
            # 티커 심볼 정리 (NaN 제거 및 문자열 변환)
            tickers = [str(ticker) for ticker in tickers if str(ticker) != 'nan']
            
            logger.info(f"나스닥 100 기업 목록 가져오기 성공")
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

class TBM_Strategy(Analyst):
    '''트렌드-볼린저-MACD 결합 전략
    
    트렌드 확인, 볼린저 밴드, MACD를 결합한 균형 잡힌 주식 분석 전략을 제공합니다.
    '''
    def __init__(self, kis, config, risk_level=2):
        super().__init__(kis, config)
        # 리스크 레벨: 1(보수), 2(중간), 3(공격)
        self.risk_level = risk_level
        
    def analyze(self, ticker: str) -> Tuple[bool, Dict]:
        '''종목 분석을 수행하고 매매 신호를 반환합니다.
        
        Args:
            ticker (str): 주식 티커 심볼
            
        Returns:
            Tuple[bool, Dict]: 
                - bool: 성공 여부
                - Dict: 분석 결과 및 신호
        '''
        try:
            # 데이터 가져오기 (1년 데이터, 일봉 기준)
            data = yfinance.Ticker(ticker).history(period="1y")
            if len(data) < 50:
                return False, {"error": "충분한 데이터가 없습니다"}
                
            # 1. 트렌드 확인 (이동평균선)
            data['MA50'] = data['Close'].rolling(window=50).mean()
            data['MA200'] = data['Close'].rolling(window=200).mean()
            
            # 2. 볼린저 밴드 계산 (20일 기준)
            data['MA20'] = data['Close'].rolling(window=20).mean()
            data['STD20'] = data['Close'].rolling(window=20).std()
            data['BB_Upper'] = data['MA20'] + (data['STD20'] * 2)
            data['BB_Lower'] = data['MA20'] - (data['STD20'] * 2)
            data['BB_Width'] = (data['BB_Upper'] - data['BB_Lower']) / data['MA20']
            
            # 3. MACD 계산
            data['EMA12'] = data['Close'].ewm(span=12, adjust=False).mean()
            data['EMA26'] = data['Close'].ewm(span=26, adjust=False).mean()
            data['MACD'] = data['EMA12'] - data['EMA26']
            data['Signal_Line'] = data['MACD'].ewm(span=9, adjust=False).mean()
            data['Histogram'] = data['MACD'] - data['Signal_Line']
            
            # 최근 데이터 추출
            current = data.iloc[-1]
            previous = data.iloc[-2]
            
            # 4. 각 요소별 점수 계산 (0-1점 척도)
            scores = {}
            
            # 트렌드 점수 (0-1)
            trend_score = 0
            if current['Close'] > current['MA50']:
                trend_score += 0.5
            if current['MA50'] > current['MA200']:
                trend_score += 0.5
            scores['trend'] = trend_score
            
            # 볼린저 점수 (0-1)
            bb_score = 0
            # 강한 추세 확인 (밴드 확장)
            if current['BB_Width'] > data['BB_Width'].rolling(window=20).mean().iloc[-1]:
                bb_score += 0.3
            
            # 매수 시점 확인 (하단밴드에서 반등)
            bb_position = (current['Close'] - current['BB_Lower']) / (current['BB_Upper'] - current['BB_Lower'])
            if previous['Close'] <= previous['BB_Lower'] and current['Close'] > current['BB_Lower']:
                bb_score += 0.7
            # 중간 위치에서 상승 추세
            elif 0.3 <= bb_position <= 0.7 and current['Close'] > previous['Close']:
                bb_score += 0.5
            scores['bollinger'] = bb_score
            
            # MACD 점수 (0-1)
            macd_score = 0
            # 골든크로스
            if previous['MACD'] < previous['Signal_Line'] and current['MACD'] > current['Signal_Line']:
                macd_score += 0.7
            # 정배열 상태
            elif current['MACD'] > current['Signal_Line'] and current['Histogram'] > previous['Histogram']:
                macd_score += 0.5
            # 강한 상승 추세
            if current['MACD'] > 0 and current['MACD'] > previous['MACD']:
                macd_score += 0.3
                
            scores['macd'] = min(1.0, macd_score)  # 최대 1점
            
            # 5. 종합 점수 계산 (가중치 적용)
            if self.risk_level == 1:  # 보수적
                weights = {'trend': 0.5, 'bollinger': 0.3, 'macd': 0.2}
            elif self.risk_level == 2:  # 중간
                weights = {'trend': 0.4, 'bollinger': 0.3, 'macd': 0.3}
            else:  # 공격적
                weights = {'trend': 0.3, 'bollinger': 0.3, 'macd': 0.4}
                
            total_score = sum(scores[k] * weights[k] for k in scores)
            
            # 6. 매매 신호 결정
            signal = "NO_SIGNAL"
            if total_score >= 0.7:
                signal = "BUY"
            elif total_score <= 0.3:
                signal = "SELL"
            else:
                signal = "HOLD"
                
            # 추가 분석 정보
            details = {
                'price': current['Close'],
                'ma50': current['MA50'],
                'ma200': current['MA200'],
                'bollinger_width': current['BB_Width'],
                'bollinger_position': bb_position,
                'macd': current['MACD'],
                'signal_line': current['Signal_Line'],
                'histogram': current['Histogram'],
                'scores': scores,
                'total_score': total_score,
                'signal': signal
            }
            
            return True, details
            
        except Exception as e:
            error_msg = f'TBM 분석 중 오류 발생: {str(e)}'
            logger.error(error_msg)
            return False, {'error': error_msg}
        
    def get_stop_loss(self, entry_price, risk_percentage=None):
        '''매수 가격에 기반한 손절가를 계산합니다.
        
        Args:
            entry_price (float): 매수 가격
            risk_percentage (float, optional): 손절 비율. 기본값은 리스크 레벨에 따라 결정
            
        Returns:
            float: 손절가
        '''
        # 리스크 레벨에 따른 손절 비율 설정
        if risk_percentage is None:
            if self.risk_level == 1:
                risk_percentage = 0.05  # 보수적: 5%
            elif self.risk_level == 2:
                risk_percentage = 0.07  # 중간: 7% 
            else:
                risk_percentage = 0.10  # 공격적: 10%
                
        return entry_price * (1 - risk_percentage)
        
    def get_take_profit(self, entry_price, reward_percentage=None):
        '''매수 가격에 기반한 익절가를 계산합니다.
        
        Args:
            entry_price (float): 매수 가격
            reward_percentage (float, optional): 익절 비율. 기본값은 리스크 레벨에 따라 결정
            
        Returns:
            float: 익절가
        '''
        # 리스크 레벨에 따른 익절 비율 설정
        if reward_percentage is None:
            if self.risk_level == 1:
                reward_percentage = 0.15  # 보수적: 15%
            elif self.risk_level == 2:
                reward_percentage = 0.20  # 중간: 20%
            else:
                reward_percentage = 0.30  # 공격적: 30%
                
        return entry_price * (1 + reward_percentage)
    
    def run_strategy(self, tickers):
        '''전체 종목에 대해 TBM 전략을 실행하고 결과를 반환합니다.
        
        Args:
            tickers (List[str]): 분석할 종목 리스트
            
        Returns:
            Dict: 분석 결과 {
                'buy': [매수 후보 종목 정보],
                'sell': [매도 후보 종목 정보],
                'hold': 홀딩 종목 수,
                'error': 오류 발생 종목 수
            }
        '''
        # 종목 분석
        buy_candidates = []
        sell_candidates = []
        hold_positions = []
        error_tickers = []
        
        for ticker in tickers:
            success, result = self.analyze(ticker)
            
            if not success:
                error_tickers.append(ticker)
                continue
                
            if result['signal'] == "BUY":
                buy_candidates.append({
                    'ticker': ticker,
                    'score': result['total_score'],
                    'price': result['price'],
                    'stop_loss': self.get_stop_loss(result['price']),
                    'take_profit': self.get_take_profit(result['price'])
                })
            elif result['signal'] == "SELL":
                sell_candidates.append({
                    'ticker': ticker,
                    'score': result['total_score'],
                    'price': result['price']
                })
            else:
                hold_positions.append({
                    'ticker': ticker,
                    'score': result['total_score'],
                    'price': result['price']
                })
        
        # 결과 정렬 (점수 기준)
        buy_candidates.sort(key=lambda x: x['score'], reverse=True)
        
        # 상위 매수 후보 선정 (상위 5개)
        top_buy_candidates = buy_candidates[:5] if len(buy_candidates) >= 5 else buy_candidates
        
        return {
            'buy': top_buy_candidates,
            'sell': sell_candidates,
            'hold': len(hold_positions),
            'error': len(error_tickers)
        }
    
    def generate_recommendations(self):
        '''TBM 전략을 기반으로 추천 종목을 생성합니다.
        
        Returns:
            List[str]: 추천 종목 티커 리스트
        '''
        # 기본 종목 리스트 또는 나스닥 100 종목 가져오기
        tickers = self.get_nasdaq_top_100() if hasattr(self, 'config') and self.config.get('companies_settings', {}).get('auto_fetch', False) else self.get_default_tickers()
        
        # 전략 실행
        result = self.run_strategy(tickers)
        
        # 매수 추천 종목만 반환
        return [item['ticker'] for item in result['buy']]