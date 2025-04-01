from pykis import KisBalance
from datetime import datetime
import yfinance
import logging
import traceback
import time

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
        
        # 상위 매수 후보 선정 (상위 3개)
        top_buy_candidates = buy_candidates[:3] if len(buy_candidates) >= 3 else buy_candidates

        logging.info(f"매수 대상 종목: {len(top_buy_candidates)}개")
        
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

    def get_quote(self, ticker: str):
        '''종목 시세 정보를 가져오는 함수
        '''
        attempts = 0
        while attempts < 4:
            try:
                return self.kis.stock(ticker).quote()
            except Exception as e:
                logging.error(f"[{attempts+1}/4] 시세 정보 가져오기 실패 ({ticker}): {str(e)}")
                attempts += 1
                time.sleep(1)  # 1초 대기 후 재시도
        raise Exception(f"시세 정보 가져오기 실패 (최대 재시도 초과) - {ticker}")

    def get_recommendations_to_buy(self, tickers):
        '''TBM 전략을 기반으로 추천 종목을 생성하고 처리합니다.
        
        Args:
            tickers (List[str]): 분석할 종목 티커 리스트
            
        Returns:
            List[dict]: 처리된 매수 추천 종목 리스트 (티커, 가격, 종목명 포함)
        '''
        try:
            # 기본 종목 리스트 설정
            if not tickers:
                tickers = self.get_default_tickers()
            
            # 전략 실행
            result = self.run_strategy(tickers)
            recommendations = [item['ticker'] for item in result['buy']]
            
            # 매수 추천 종목이 없는 경우
            if not recommendations:
                logging.info("매수 추천 종목이 없습니다.")
                return []
            
            # 주문 가능한 형태로 가공
            processed_targets = []
            for target in recommendations:
                try:
                    # 시세 조회를 통한 가격 정보 가져오기
                    quote = self.get_quote(target)
                    if not quote or getattr(quote, 'price', 0) <= 0:
                        logging.warning(f"{target} 유효하지 않은 가격 정보")
                        continue
                        
                    target_data = {
                        'ticker':   target,
                        'price':    getattr(quote, 'price', 0),
                        'quantity': 1, # 임시
                        'name':     getattr(quote, 'name', target)
                    }

                    if quote.price < 100: # 100달러가 기준값
                        processed_targets.append(target_data)
                    
                except Exception as e:
                    logging.error(f"{target} 시세 조회 실패: {str(e)}")
                    continue
            
            # 처리된 종목이 없는 경우
            if not processed_targets:
                logging.info("처리 가능한 매수 대상 종목이 없습니다.")
                return []
                
            return processed_targets
            
        except Exception as e:
            logging.error(f"매수 종목 선정 중 오류 발생: {str(e)}")
            import traceback
            logging.error(f"매수 종목 선정 상세 오류: {traceback.format_exc()}")
            return []
    
    def update_holdings(self):
        '''보유 종목 정보 업데이트'''
        try:
            # 잔고 객체 가져오기
            balance = self.get_balance()
            
            # 보유종목 정보 저장
            self.holdings = {}
            
            # 튜토리얼에 따라 balance.stocks 활용
            for stock_info in balance.stocks:
                try:
                    # 종목 정보 형식화
                    stock_ticker = getattr(stock_info, 'symbol', getattr(stock_info, 'ticker', None))
                    self.holdings[stock_ticker] = stock_info
                except Exception as stock_err:
                    logging.error(f"종목 정보 처리 중 오류: {str(stock_err)}")
            
            logging.info(f"보유종목 업데이트 완료: {len(self.holdings)}개 종목")
            return True
        
        except Exception as e:
            logging.error(f"보유종목 업데이트 실패: {str(e)}")
            logging.error(traceback.format_exc())
            return False

    # analyst에 옮기기
    def get_balance(self):
        ''' 내 계좌 잔고 확인하는 함수

        returns:
            KisIntegrationBalance: 예수금, 보유종목 등 내 계좌에 대한 정보
        '''
        account = self.kis.account()
        balance: KisBalance = account.balance()
        return balance

    def get_sell_recommendations(self):
        """보유 종목 중 매도 조건을 충족하는 종목 선정
        
        Returns:
            List[Dict]: 매도 대상 종목 리스트
        """
        try:
            # 보유 종목 정보 업데이트
            self.update_holdings()
            
            recommendations = []
            total_holdings = len(self.holdings)
            
            for idx, (ticker, holding_info) in enumerate(self.holdings.items()):
                try:
                    logging.info(f"[{idx+1}/{total_holdings}] 종목 {ticker} 매도 추천 생성 중...")
                    
                    # 현재 시장 가격 확인
                    quote = self.get_quote(ticker)
                    
                    # 현재가 추출
                    current_price = quote.price

                    # balance에 ticker 받아서 매입금액이나, 아니면 수익률이라도 알 수 있지 않을까?
                    balance = self.get_balance()
                    print(quote)
                    print(balance)
                    
                    # 시세 정보가 없으면 건너뜀
                    if not current_price or current_price <= 0:
                        logging.warning(f"종목 {ticker} 현재가 정보 없음")
                        continue
                    
                    # 평균 매수가 확인
                    if not holding_info.price or holding_info.price <= 0:
                        logging.warning(f"종목 {ticker} 평균 매수가 정보 없음")
                        continue
                    
                    # 수익률 계산
                    profit_rate = ((current_price - avg_price) / avg_price) * 100 # (현재가/매수가)
                    
                    # 매도 조건 확인
                    sell_signals = []
                    
                    # 1. 손절점 도달
                    stop_loss = self.config.get("stop_loss_threshold", -7.0)
                    if profit_rate <= stop_loss:
                        sell_signals.append("손절점 도달")
                    
                    # 2. 익절점 도달
                    take_profit = self.config.get("take_profit_threshold", 20.0)
                    if profit_rate >= take_profit:
                        sell_signals.append("익절점 도달")
                    
                    # 매도 추천이 있는 경우만 추가
                    if sell_signals:
                        # 수량 정보 가져오기
                        quantity = holding_info.quantity
                        if not quantity:
                            quantity = getattr(holding_info, 'quantity', 0)
                        
                        recommendations.append({
                            'ticker': ticker,
                            'name': getattr(quote, 'name', ticker),
                            'current_price': current_price,
                            'avg_price': avg_price,
                            'profit_rate': profit_rate,
                            'quantity': quantity,
                            'sell_signals': sell_signals
                        })
                
                except Exception as e:
                    logging.error(f"[{idx+1}/{total_holdings}] 종목 {ticker} 매도 추천 생성 중 오류: {str(e)}")
                    continue
            
            return recommendations
            
        except Exception as e:
            logging.error(f"매도 추천 생성 중 오류: {str(e)}")
            logging.error(traceback.format_exc())
            return [] 