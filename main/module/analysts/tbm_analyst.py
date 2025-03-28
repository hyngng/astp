import yfinance
import logging

from ..analyst import Analyst

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TBM_Analyst(Analyst):
    '''트렌드-볼린저-MACD 결합 전략
    
    트렌드 확인, 볼린저 밴드, MACD를 결합한 균형 잡힌 주식 분석 전략을 제공합니다.
    '''
    def __init__(self, kis, config, risk_level=2):
        super().__init__(config)
        self.kis        = kis
        self.config     = config
        self.risk_level = risk_level

    def analyze(self, ticker):
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
            data = yfinance.Ticker(ticker).history(period="1y") # possibly delisted; no price data found  (period=1y)
            if len(data) < 50:
                return False, {"error": "충분한 데이터가 없습니다"}
                
            # 1. 트렌드 확인 (이동평균선)
            data['MA50']        = data['Close'].rolling(window=50).mean()
            data['MA200']       = data['Close'].rolling(window=200).mean()
            
            # 2. 볼린저 밴드 계산 (20일 기준)
            data['MA20']        = data['Close'].rolling(window=20).mean()
            data['STD20']       = data['Close'].rolling(window=20).std()
            data['BB_Upper']    = data['MA20'] + (data['STD20'] * 2)
            data['BB_Lower']    = data['MA20'] - (data['STD20'] * 2)
            data['BB_Width']    = (data['BB_Upper'] - data['BB_Lower']) / data['MA20']
            
            # 3. MACD 계산
            data['EMA12']       = data['Close'].ewm(span=12, adjust=False).mean()
            data['EMA26']       = data['Close'].ewm(span=26, adjust=False).mean()
            data['MACD']        = data['EMA12'] - data['EMA26']
            data['Signal_Line'] = data['MACD'].ewm(span=9, adjust=False).mean()
            data['Histogram']   = data['MACD'] - data['Signal_Line']
            
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
            # 데드크로스
            elif previous['MACD'] > previous['Signal_Line'] and current['MACD'] < current['Signal_Line']:
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
            logging.error(error_msg)
            return False, {'error': error_msg}
    
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

    def generate_recommendations(self, tickers):
        '''TBM 전략을 기반으로 추천 종목을 생성합니다.
        
        Returns:
            List[str]: 추천 종목 티커 리스트
        '''
        if not tickers:
            tickers = self.get_default_tickers()

        result = self.run_strategy(tickers)

        return [item['ticker'] for item in result['buy']]