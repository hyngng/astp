from pykis import KisBalance
from datetime import datetime
import logging
from typing import Dict, List, Tuple, Optional
from module.analysts import TBM_Strategy
import time

class Trader:
    ''' 주문자: 매수&매도주문의 적절성을 판단 후 주문하는 클래스.
    '''
    def __init__(self, kis, config):
        '''주문자 초기화'''
        self.kis = kis
        self.config = config
        self.watchlist = []
        self.holdings = {}  # 보유 중인 종목 관리
        
        # 기본 설정값
        self.is_virtual = config.get("api_info", {}).get("is_virtual", False)
        
        # config에서 risk_level 가져오기
        risk_level = config.get("trading_settings", {}).get("risk_level", 2)
        self.tbm_strategy = TBM_Strategy(kis, config, risk_level=risk_level)
        
        # 초기 보유종목 로드
        self.update_holdings()
        
        # 초기화 완료 로그
        logging.info(f"트레이더 초기화 완료 (모드: {'모의투자' if self.is_virtual else '실제투자'})")

    def get_trading_hours(self):
        ''' 현재 미국 장이 열려있는지 확인하는 함수.

        returns:
            bool: 미국 장이 열려있는지.
        '''
        try:
            opening_time = self.kis.trading_hours("US").open_kst
            closing_time = self.kis.trading_hours("US").close_kst
            now          = datetime.now().time()

            is_open = True
            if closing_time < now < opening_time:
                is_open = False
            return is_open
        except Exception as e:
            logging.error(f"미국 장 개장 여부 확인 실패: {str(e)}")
            # 연결 오류 발생 시 기본값 반환 (장 시간으로 가정)
            return True

    def get_balance(self):
        ''' 내 계좌 잔고 확인하는 함수.

        returns:
            KisIntegrationBalance: 예수금, 보유종목 등 내 계좌에 대한 정보
        '''
        account = self.kis.account()
        balance: KisBalance = account.balance()
        return repr(balance)

    def update_holdings(self):
        '''보유 종목 정보를 업데이트하는 함수'''
        try:
            account = self.kis.account()
            balance = account.balance()

            # 보유 종목 정보 초기화
            self.holdings = {}

            # 보유 종목 정보 업데이트
            for stock in balance.stocks:
                # 주요 속성 안전하게 가져오기
                symbol = getattr(stock, 'symbol', '')
                quantity = getattr(stock, 'quantity', 0)
                avg_price = getattr(stock, 'avg_price', None)
                current_price = getattr(stock, 'current_price', None)
                total_value = getattr(stock, 'total_value', None)
                profit_loss = getattr(stock, 'profit_loss', None)
                profit_loss_rate = getattr(stock, 'profit_loss_rate', None)
                
                # 해외 주식과 국내 주식의 속성명 차이 처리
                if avg_price is None:
                    avg_price = getattr(stock, 'purchase_price', 0) or getattr(stock, 'pchs_avg_pric', 0)
                if current_price is None:
                    current_price = getattr(stock, 'price', 0) or getattr(stock, 'now_pric', 0)
                if total_value is None:
                    total_value = getattr(stock, 'eval_amt', 0) or quantity * current_price
                if profit_loss is None:
                    profit_loss = getattr(stock, 'eval_pfls_amt', 0)
                if profit_loss_rate is None:
                    profit_loss_rate = getattr(stock, 'eval_pfls_rt', 0)
                
                if symbol:  # 심볼이 있는 경우에만 추가
                    self.holdings[symbol] = {
                        'quantity': quantity,
                        'avg_price': avg_price,
                        'current_price': current_price,
                        'total_value': total_value,
                        'profit_loss': profit_loss,
                        'profit_loss_rate': profit_loss_rate,
                        'buy_date': datetime.now().strftime("%Y-%m-%d")  # 매수일은 정확한 정보가 없어 현재 날짜로 대체
                    }

            logging.info(f"보유 종목 정보 업데이트 완료: {len(self.holdings)}개 종목")
            return True

        except Exception as e:
            logging.error(f"보유 종목 정보 업데이트 실패: {str(e)}")
            import traceback
            logging.error(f"보유 종목 업데이트 상세 오류: {traceback.format_exc()}")
            return False

    def api_call_with_retry(self, func, *args, max_retries=3, initial_delay=2, **kwargs):
        '''API 호출을 지수 백오프 방식으로 재시도하는 함수'''
        delay = initial_delay
        last_error = None
        
        for retry in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                error_str = str(e)
                # API 호출 제한 또는 네트워크 오류 감지
                if "API 호출 횟수를 초과" in error_str or "Connection aborted" in error_str:
                    if retry < max_retries - 1:
                        logging.warning(f"API 호출 또는 네트워크 오류. {delay}초 후 재시도 ({retry+1}/{max_retries})...")
                        time.sleep(delay)
                        delay *= 2  # 지수 백오프
                    else:
                        logging.error(f"최대 재시도 횟수 초과: {error_str}")
                else:
                    # 다른 종류의 오류는 즉시 발생
                    break
        
        # 모든 재시도 실패
        raise last_error if last_error else Exception("API 호출 실패")

    def get_quote(self, ticker: str) -> Dict:
        '''종목 시세 정보를 가져오는 함수'''
        try:
            stock = self.kis.stock(ticker)
            # 네트워크 오류 자동 재시도 추가
            return self.api_call_with_retry(stock.quote)
        except Exception as e:
            logging.error(f"시세 정보 가져오기 실패 ({ticker}): {str(e)}")
            raise

    def check_sell_conditions(self, ticker: str) -> Tuple[bool, Dict]:
        '''매도 결정을 위한 조건 확인'''
        # 보유 종목이 아니면 매도할 수 없음
        if ticker not in self.holdings:
            return False, {'reason': '보유하지 않은 종목'}
            
        holding_info = self.holdings[ticker]
        
        try:
            # 1. 현재 시장 가격 확인 - 네트워크 오류에 대한 재시도 로직 포함
            try:
                quote = self.get_quote(ticker)
                current_price = quote.price
            except Exception as e:
                logging.error(f"{ticker} 시세 조회 중 오류, 보유 정보의 현재가 사용: {str(e)}")
                # 오류 발생 시 보유 정보의 현재가 사용
                current_price = holding_info.get('current_price', 0)
                if not current_price:
                    return False, {'reason': f'시세 조회 실패: {str(e)}'}
            
            # 2. 손익률 계산
            avg_price = holding_info['avg_price']
            profit_rate = (current_price - avg_price) / avg_price * 100
            
            # 3. TBM 전략으로 종목 분석
            try:
                success, analysis = self.tbm_strategy.analyze(ticker)
            except Exception as e:
                logging.error(f"{ticker} TBM 분석 중 오류: {str(e)}")
                success, analysis = False, {'signal': 'ERROR'}
            
            # 매도 신호 목록
            sell_signals = []
            
            # 4. 매도 조건 확인
            settings = self.config.get("trading_settings", {})
            
            # 손절점 도달
            stop_loss = settings.get("stop_loss_threshold", -7.0)
            if profit_rate <= stop_loss:
                sell_signals.append("손절점 도달")
                
            # 익절점 도달
            take_profit = settings.get("take_profit_threshold", 20.0)
            if profit_rate >= take_profit:
                sell_signals.append("익절점 도달")
                
            # TBM 전략에서 SELL 신호
            if success and analysis['signal'] == "SELL":
                sell_signals.append("TBM 매도 신호")
                
            # 홀딩 기간 초과
            max_holding_days = settings.get("max_holding_days", 30)
            buy_date = datetime.strptime(holding_info['buy_date'], "%Y-%m-%d")
            days_held = (datetime.now() - buy_date).days
            if days_held > max_holding_days:
                sell_signals.append(f"홀딩 기간 초과 ({days_held}일)")
                
            # 매도 결정 (신호가 하나라도 있으면 매도)
            should_sell = len(sell_signals) > 0
            
            # 매도 정보
            result = {
                'ticker': ticker,
                'current_price': current_price,
                'avg_price': avg_price,
                'profit_rate': profit_rate,
                'quantity': holding_info['quantity'],
                'sell_signals': sell_signals,
                'total_value': holding_info['quantity'] * current_price
            }
            
            return should_sell, result
            
        except Exception as e:
            logging.error(f"{ticker} 매도 조건 확인 중 오류 발생: {str(e)}")
            return False, {'reason': f'오류: {str(e)}'}

    def submit_order(self, ticker: str, price: float, quantity: int, order_type: str = "buy") -> bool:
        '''주문 실행'''
        if quantity <= 0:
            logging.warning(f"주문 수량이 0 이하입니다: {ticker}, {quantity}주")
            return False
            
        try:
            stock = self.kis.stock(ticker)
            
            # 주문 로그
            log_prefix = "모의투자" if self.config.get("api_info", {}).get("is_virtual", False) else "실제"
            logging.info(f"{log_prefix} 주문 실행: {ticker} {order_type} {quantity}주 @ {price:,.0f}원")
            
            # 주문 실행
            try:
                # PyKis 최신 문서에 따른 매개변수 사용
                if order_type == "buy":
                    order = stock.buy(price=price, qty=quantity)
                else:
                    order = stock.sell(price=price, qty=quantity)
                    
                if not order:
                    logging.error(f"{log_prefix} 주문 실패: {ticker}")
                    return False
                    
                logging.info(f"{log_prefix} 주문 성공: {ticker} {order_type} {quantity}주 @ {price:,.0f}원")
                
                # 보유 종목 정보 업데이트
                self.update_holdings()
                
                return True
                
            except Exception as e:
                logging.error(f"주문 메서드 호출 실패 ({ticker}): {str(e)}")
                
                # 다른 매개변수 시도
                try:
                    logging.info(f"대체 매개변수로 재시도: {ticker}")
                    if order_type == "buy":
                        order = stock.buy(price=price, volume=quantity)
                    else:
                        order = stock.sell(price=price, volume=quantity)
                        
                    if order:
                        logging.info(f"대체 매개변수로 주문 성공: {ticker}")
                        self.update_holdings()
                        return True
                except Exception as e2:
                    logging.error(f"대체 매개변수 시도 중 오류: {str(e2)}")
                    
                return False
                
        except Exception as e:
            logging.error(f"주문 실행 중 오류 발생 ({ticker}): {str(e)}")
            logging.error(f"상세 오류: {traceback.format_exc()}")
            return False

    def get_daily_profit_loss(self):
        '''일별 손익 조회

        Returns:
            Dict: 일별 손익 정보
        '''
        try:
            # API 호출 속도 제한 문제를 방지하기 위한 재시도 로직
            max_retries = 3
            retry_delay = 2  # 초
            
            for retry in range(max_retries):
                try:
                    # 일별 손익 조회
                    profit_loss = self.kis.inquire_daily_profit_loss()
                    break  # 성공 시 루프 종료
                except Exception as e:
                    if "API 호출 횟수를 초과" in str(e) and retry < max_retries - 1:
                        logging.warning(f"API 호출 제한 감지. {retry_delay}초 후 재시도 ({retry+1}/{max_retries})...")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # 백오프 지연 시간 증가
                    else:
                        raise  # 다른 오류이거나 최대 재시도 횟수 초과 시 예외 발생
            
            # 종목별 손익 상세
            details = []
            for stock in profit_loss.stocks:
                details.append({
                    'symbol': stock.symbol,
                    'name': stock.name,
                    'quantity': stock.quantity,
                    'profit_loss': stock.profit_loss,
                    'profit_loss_rate': stock.profit_loss_rate
                })

            return {
                'date': profit_loss.date,
                'total_profit_loss': profit_loss.total_profit_loss,
                'total_profit_loss_rate': profit_loss.total_profit_loss_rate,
                'details': details
            }

        except Exception as e:
            logging.error(f"일별 손익 조회 중 오류 발생: {str(e)}")
            import traceback
            logging.error(f"일별 손익 조회 상세 오류: {traceback.format_exc()}")
            return None

    def check_all_sell_conditions(self) -> List[Dict]:
        '''모든 보유 종목에 대해 매도 조건 확인

        Returns:
            List[Dict]: 매도 대상 종목 정보 리스트
        '''
        sell_candidates = []

        # 보유 종목 정보 최신화
        self.update_holdings()

        # 각 보유 종목에 대해 매도 조건 확인
        for ticker in self.holdings:
            should_sell, result = self.check_sell_conditions(ticker)

            if should_sell:
                sell_candidates.append(result)
                logging.info(f"매도 대상: {ticker}, 현재가: {result['current_price']:,.0f}, 평균단가: {result['avg_price']:,.0f}, 손익률: {result['profit_rate']:.2f}%, 사유: {', '.join(result['sell_signals'])}")

        return sell_candidates

    def execute_sell_orders(self, sell_candidates: Optional[List[Dict]] = None) -> List[Dict]:
        '''매도 조건에 맞는 종목들에 대해 매도 주문 실행

        Args:
            sell_candidates (List[Dict], optional): 매도 대상 종목 리스트. 기본값은 None으로, 이 경우 자동으로 check_all_sell_conditions()를 호출

        Returns:
            List[Dict]: 매도 주문 실행 결과 리스트
        '''
        if sell_candidates is None:
            sell_candidates = self.check_all_sell_conditions()

        if not sell_candidates:
            logging.info("매도 대상 종목이 없습니다.")
            return []

        sell_results = []

        for candidate in sell_candidates:
            ticker = candidate['ticker']
            price = candidate['current_price']
            quantity = candidate['quantity']

            # 주문 실행
            success = self.submit_order(ticker, price, quantity, order_type="sell")

            result = {
                'ticker': ticker,
                'price': price,
                'quantity': quantity,
                'total_value': price * quantity,
                'success': success,
                'profit_rate': candidate['profit_rate'],
                'sell_signals': candidate['sell_signals']
            }

            sell_results.append(result)

            if success:
                logging.info(f"매도 주문 성공: {ticker}, {quantity}주 @ {price:,.0f}원, 총액: {price * quantity:,.0f}원, 손익률: {candidate['profit_rate']:.2f}%")
            else:
                logging.error(f"매도 주문 실패: {ticker}")

        return sell_results

    def auto_trading_cycle(self) -> Dict:
        '''자동 매매 사이클 실행'''
        try:
            # API 호출 간격 조절을 위한 지연 시간
            api_call_delay = 1  # 초
            
            # 1. 매도 실행
            try:
                sell_candidates = self.check_all_sell_conditions()
                time.sleep(api_call_delay)  # API 호출 속도 제한 방지
                sell_results = self.execute_sell_orders(sell_candidates)
            except Exception as e:
                logging.error(f"매도 실행 중 오류 발생: {str(e)}")
                logging.error(f"상세 오류: {traceback.format_exc()}")
                sell_results = []
                
            # 2. 매수 추천 종목 확인
            try:
                time.sleep(api_call_delay)  # API 호출 속도 제한 방지
                buy_recommendations = self.tbm_strategy.generate_recommendations()
            except Exception as e:
                logging.error(f"매수 추천 종목 확인 중 오류 발생: {str(e)}")
                buy_recommendations = []
                
            # 3. 현금 잔고 확인
            available_cash_float = 0
            
            if self.config.get("api_info", {}).get("is_virtual", False):
                logging.info("모의투자 모드가 활성화되어 있습니다. 현금 잔고 확인을 생략하고 바로 매수 주문을 진행합니다.")
                available_cash_float = 10000000  # 모의투자의 경우 충분한 자금 가정
            else:
                # 실계좌 잔고 확인
                try:
                    available_cash_float = self._get_available_cash()
                    
                    # 실계좌의 경우 사용 가능한 잔고가 없으면 매수 스킵
                    if available_cash_float <= 0:
                        logging.warning("사용 가능한 현금 잔고가 없어 매수를 진행하지 않습니다.")
                        total_sell = sum(float(r['total_value']) for r in sell_results if r['success'] and isinstance(r['total_value'], (int, float)))
                        
                        return {
                            'sell_results': sell_results,
                            'buy_results': [],
                            'total_sell_value': total_sell,
                            'total_buy_value': 0,
                            'net_cash_flow': total_sell,
                            'sell_count': len([r for r in sell_results if r['success']]),
                            'buy_count': 0
                        }
                except Exception as e:
                    logging.error(f"계좌 잔고 확인 중 오류 발생: {str(e)}")
                    logging.info("잔고 확인 실패로 모의투자 모드처럼 진행합니다.")
                    available_cash_float = 10000000
            
            # 4. 매수 종목 선정
            max_buy_stocks = self._get_max_buy_stocks()
            
            # 추천 종목이 리스트가 아니면 빈 리스트로 변환
            if not isinstance(buy_recommendations, list):
                logging.warning("매수 추천 종목이 리스트가 아닙니다. 빈 리스트로 처리합니다.")
                buy_recommendations = []
                
            # 상위 N개 종목 선택
            buy_targets = buy_recommendations[:max_buy_stocks]
            
            # 5. 매수 금액 설정
            budget_percentage = self.config.get("trading_settings", {}).get("budget_percentage", 30)
            
            # 보유주식 총액 계산
            total_holdings_value = sum(
                holding.get('total_value', 0) 
                for holding in self.holdings.values() 
                if isinstance(holding.get('total_value'), (int, float))
            )
            
            # 보유주식 금액이 10만원 이하면 매수 금액을 1만원으로 제한
            if total_holdings_value <= 100000:
                logging.info(f"보유주식 총액이 10만원 이하({total_holdings_value:,.0f}원)이므로 매수 금액을 1만원으로 제한합니다.")
                buy_budget_per_stock = 10000  # 1만원
                if not self.config.get("api_info", {}).get("is_virtual", False):
                    # 실계좌는 예산과 1만원 중 작은 값
                    buy_budget_per_stock = min(10000, (available_cash_float * budget_percentage / 100) / max(len(buy_targets), 1))
            else:
                if self.config.get("api_info", {}).get("is_virtual", False):
                    # 모의투자의 경우 고정된 매수 금액 사용
                    buy_budget_per_stock = 1000000  # 100만원
                else:
                    # 실계좌는 예산 기반 계산
                    buy_budget_per_stock = (available_cash_float * budget_percentage / 100) / max(len(buy_targets), 1)
            
            # 6. 매수 실행
            buy_results = []
            for ticker in buy_targets:
                try:
                    time.sleep(api_call_delay)  # API 호출 속도 제한 방지
                    
                    # 시세 조회
                    try:
                        quote = self.get_quote(ticker)
                        current_price = float(quote.price)
                    except Exception as e:
                        logging.error(f"{ticker} 시세 조회 실패: {str(e)}")
                        continue
                    
                    # 수량 계산
                    quantity = int(buy_budget_per_stock / current_price)
                    
                    if quantity <= 0:
                        logging.warning(f"매수 가능 수량이 0인 종목: {ticker}, 현재가: {current_price:,.0f}원")
                        continue
                    
                    # 주문 실행
                    success = self.submit_order(ticker, current_price, quantity, order_type="buy")
                    
                    buy_results.append({
                        'ticker': ticker,
                        'price': current_price,
                        'quantity': quantity,
                        'total_value': current_price * quantity,
                        'success': success
                    })
                    
                except Exception as e:
                    logging.error(f"{ticker} 매수 중 오류 발생: {str(e)}")
                    buy_results.append({'ticker': ticker, 'success': False, 'error': str(e)})
            
            # 7. 결과 종합
            total_sell_value = sum(float(r['total_value']) for r in sell_results if r['success'] and isinstance(r['total_value'], (int, float)))
            total_buy_value = sum(float(r['total_value']) for r in buy_results if r['success'] and isinstance(r['total_value'], (int, float)))
            
            result = {
                'sell_results': sell_results,
                'buy_results': buy_results,
                'total_sell_value': total_sell_value,
                'total_buy_value': total_buy_value,
                'net_cash_flow': total_sell_value - total_buy_value,
                'sell_count': len([r for r in sell_results if r['success']]),
                'buy_count': len([r for r in buy_results if r['success']])
            }
            
            logging.info(f"자동 매매 사이클 완료: 매도 {result['sell_count']}종목 {total_sell_value:,.0f}원, 매수 {result['buy_count']}종목 {total_buy_value:,.0f}원")
            
            return result
            
        except Exception as e:
            logging.error(f"자동 매매 사이클 실행 중 예상치 못한 오류 발생: {str(e)}")
            logging.error(f"상세 오류: {traceback.format_exc()}")
            
            # 최소한의 결과 반환
            return {
                'sell_results': [],
                'buy_results': [],
                'total_sell_value': 0,
                'total_buy_value': 0,
                'net_cash_flow': 0,
                'sell_count': 0,
                'buy_count': 0,
                'error': str(e)
            }

    def _get_max_buy_stocks(self) -> int:
        '''최대 매수 종목 수 설정값 가져오기'''
        try:
            setting = self.config.get("trading_settings", {}).get("max_buy_stocks", "3")
            
            # GitHub Actions 변수 패턴 확인
            if isinstance(setting, str) and "${{" in setting:
                logging.warning(f"GitHub Actions 변수 패턴 감지: {setting}. 기본값 3 사용.")
                return 3
                
            return int(setting)
        except (TypeError, ValueError) as e:
            logging.error(f"max_buy_stocks 설정값을 정수로 변환 실패. 기본값 3 사용: {str(e)}")
            return 3