from pykis import KisBalance
from datetime import datetime
import logging
from typing import Dict, List, Tuple, Optional
from module.analysts import TBM_Strategy

class Trader:
    ''' 주문자: 매수&매도주문의 적절성을 판단 후 주문하는 클래스.
    '''
    def __init__(self, kis, config):
        self.kis       = kis
        self.config    = config
        self.watchlist = []
        self.holdings  = {}  # 보유 중인 종목 관리
        
        # config에서 risk_level 가져오기
        risk_level = config.get("trading_settings", {}).get("risk_level", 2)
        self.tbm_strategy = TBM_Strategy(kis, config, risk_level=risk_level)  # 설정에서 가져온 리스크 레벨 사용
    
    def get_trading_hours(self):
        ''' 현재 미국 장이 열려있는지 확인하는 함수.

        returns:
            bool: 미국 장이 열려있는지.
        '''
        opening_time = self.kis.trading_hours("US").open_kst
        closing_time = self.kis.trading_hours("US").close_kst
        now          = datetime.now().time()

        is_open = True
        if closing_time < now < opening_time:
            is_open = False
        return is_open

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
                self.holdings[stock.symbol] = {
                    'quantity': stock.quantity,
                    'avg_price': stock.avg_price,
                    'current_price': stock.current_price,
                    'total_value': stock.total_value,
                    'profit_loss': stock.profit_loss,
                    'profit_loss_rate': stock.profit_loss_rate,
                    'buy_date': datetime.now().strftime("%Y-%m-%d")  # 매수일은 정확한 정보가 없어 현재 날짜로 대체
                }
            
            logging.info(f"보유 종목 정보 업데이트 완료: {len(self.holdings)}개 종목")
            return True
            
        except Exception as e:
            logging.error(f"보유 종목 정보 업데이트 실패: {str(e)}")
            return False
    
    def submit_order(self, ticker: str, price: float, quantity: int, order_type: str = "buy") -> bool:
        '''주문 실행
        
        Args:
            ticker (str): 종목 코드
            price (float): 주문 가격
            quantity (int): 주문 수량
            order_type (str): 주문 유형 ("buy" 또는 "sell")
            
        Returns:
            bool: 주문 성공 여부
        '''
        try:
            # 모의투자 여부 확인
            is_virtual = self.config.get("api_info", {}).get("is_virtual", False)
            
            if is_virtual:
                # 모의투자인 경우, 주문 성공으로 처리하고 로그만 남김
                logging.info(f"모의투자 주문: {ticker} {order_type} {quantity}주 @ {price:,.0f}원")
                
                # 매수 주문인 경우 보유 종목에 추가
                if order_type == "buy":
                    if ticker not in self.holdings:
                        self.holdings[ticker] = {
                            'quantity': quantity,
                            'avg_price': price,
                            'current_price': price,
                            'total_value': price * quantity,
                            'profit_loss': 0,
                            'profit_loss_rate': 0,
                            'buy_date': datetime.now().strftime("%Y-%m-%d")
                        }
                    else:
                        # 기존 보유 종목인 경우 수량 추가
                        old_quantity = self.holdings[ticker]['quantity']
                        old_avg_price = self.holdings[ticker]['avg_price']
                        new_quantity = old_quantity + quantity
                        
                        # 평균 단가 계산
                        new_avg_price = (old_quantity * old_avg_price + quantity * price) / new_quantity
                        
                        self.holdings[ticker]['quantity'] = new_quantity
                        self.holdings[ticker]['avg_price'] = new_avg_price
                        self.holdings[ticker]['current_price'] = price
                        self.holdings[ticker]['total_value'] = new_quantity * price
                
                # 매도 주문인 경우 보유 종목에서 제거
                if order_type == "sell" and ticker in self.holdings:
                    remaining = self.holdings[ticker]['quantity'] - quantity
                    if remaining <= 0:
                        del self.holdings[ticker]
                    else:
                        self.holdings[ticker]['quantity'] = remaining
                        self.holdings[ticker]['total_value'] = remaining * price
                
                return True
            else:
                # 실제 주문 실행
                stock = self.kis.stock(ticker)
                
                # 주문 실행 - PyKis 라이브러리의 실제 주문 메서드 사용
                try:
                    # 일반적인 접근법 시도
                    if order_type == "buy":
                        order = stock.buy(price=price, quantity=quantity)
                    else:
                        order = stock.sell(price=price, quantity=quantity)
                except AttributeError:
                    # 다른 주문 메서드 시도
                    try:
                        # 다른 메서드 이름 시도 (purchase/disposal)
                        if order_type == "buy":
                            order = stock.purchase(price=price, quantity=quantity)
                        else:
                            order = stock.disposal(price=price, quantity=quantity)
                    except AttributeError:
                        # 또 다른 메서드 시도 (order 메서드에 type 인자 사용)
                        order = stock.order(type=order_type, price=price, quantity=quantity)
                
                logging.info(f"주문 실행 완료: {ticker} {order_type} {quantity}주 @ {price:,.0f}원")
                
                # 매수 주문이 완료되면 보유 종목 정보 업데이트
                if order_type == "buy" and order:
                    self.update_holdings()
                    
                # 매도 주문이 완료되면 보유 종목에서 제거
                if order_type == "sell" and order and ticker in self.holdings:
                    remaining = self.holdings[ticker]['quantity'] - quantity
                    if remaining <= 0:
                        del self.holdings[ticker]
                    else:
                        self.holdings[ticker]['quantity'] = remaining
                    
                return True
            
        except Exception as e:
            logging.error(f"주문 실행 중 오류 발생: {str(e)}")
            # 스택 트레이스 로깅 추가
            import traceback
            logging.error(f"상세 오류: {traceback.format_exc()}")
            return False

    def get_daily_profit_loss(self):
        '''일별 손익 조회
        
        Returns:
            Dict: 일별 손익 정보
        '''
        try:
            # 일별 손익 조회
            profit_loss = self.kis.inquire_daily_profit_loss()
            
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
            return None
            
    def check_sell_conditions(self, ticker: str) -> Tuple[bool, Dict]:
        '''매도 결정을 위한 조건 확인
        
        Args:
            ticker (str): 종목 코드
            
        Returns:
            Tuple[bool, Dict]: (매도 여부, 매도 결정 관련 정보)
        '''
        # 보유 종목이 아니면 매도할 수 없음
        if ticker not in self.holdings:
            return False, {'reason': '보유하지 않은 종목'}
            
        holding_info = self.holdings[ticker]
        
        try:
            # 1. 현재 시장 가격 확인
            stock = self.kis.stock(ticker)
            quote = stock.quote()
            current_price = quote.price
            
            # 2. 손익률 계산
            avg_price = holding_info['avg_price']
            profit_rate = (current_price - avg_price) / avg_price * 100
            
            # 3. TBM 전략으로 종목 분석
            success, analysis = self.tbm_strategy.analyze(ticker)
            
            # 매도 신호 목록
            sell_signals = []
            
            # 4. 매도 조건 확인
            
            # 손절점 도달 (기본 -7%)
            stop_loss_threshold = self.config.get("trading_settings", {}).get("stop_loss_threshold", -7.0)
            if profit_rate <= stop_loss_threshold:
                sell_signals.append("손절점 도달")
            
            # 익절점 도달 (기본 +20%)
            take_profit_threshold = self.config.get("trading_settings", {}).get("take_profit_threshold", 20.0)
            if profit_rate >= take_profit_threshold:
                sell_signals.append("익절점 도달")
            
            # TBM 전략에서 SELL 신호
            if success and analysis['signal'] == "SELL":
                sell_signals.append("TBM 매도 신호")
            
            # 홀딩 기간 초과
            max_holding_days = self.config.get("trading_settings", {}).get("max_holding_days", 30)
            buy_date = datetime.strptime(holding_info['buy_date'], "%Y-%m-%d")
            days_held = (datetime.now() - buy_date).days
            if days_held > max_holding_days:
                sell_signals.append(f"홀딩 기간 초과 ({days_held}일)")
            
            # 매도 결정
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
    
    def auto_trading_cycle(self):
        '''자동 매매 사이클 실행
        
        Returns:
            Dict: 매매 사이클 실행 결과
        '''
        # 1. 매도 실행
        sell_candidates = self.check_all_sell_conditions()
        sell_results = self.execute_sell_orders(sell_candidates)
        
        # 2. 매수 추천 종목 확인
        buy_recommendations = self.tbm_strategy.generate_recommendations()
        
        # 모의투자 여부 확인 - config 설정 사용
        is_virtual = self.config.get("api_info", {}).get("is_virtual", False)
        
        if is_virtual:
            logging.info("모의투자 모드가 활성화되어 있습니다. 가상 잔고를 사용합니다.")
        
        # 3. 매수 가능 금액 확인
        available_cash_float = 0
        if is_virtual:
            # 모의투자인 경우, config에서 설정한 가상 잔고 사용
            virtual_balance = self.config.get("trading_settings", {}).get("virtual_balance", 100000000)
            available_cash_float = float(virtual_balance)
            logging.info(f"모의투자용 가상 잔고: {available_cash_float:,.0f}원")
        else:
            account = self.kis.account()
            balance = account.balance()
            
            # 현금 잔고 가져오기
            try:
                # 메서드 호출 시 통화 지정
                if hasattr(balance, "deposit") and callable(getattr(balance, "deposit")):
                    deposit_obj = balance.deposit(currency='KRW')
                    # deposit_obj에서 amount 속성 추출
                    if hasattr(deposit_obj, "amount"):
                        available_cash = deposit_obj.amount
                    else:
                        available_cash = 0
                # deposits 딕셔너리에서 KRW 항목 확인
                elif hasattr(balance, "deposits") and "KRW" in balance.deposits:
                    available_cash = balance.deposits["KRW"].amount
                # cash 속성 확인
                elif hasattr(balance, "cash"):
                    available_cash = balance.cash
                # available_cash 속성 확인
                elif hasattr(balance, "available_cash"):
                    available_cash = balance.available_cash
                else:
                    # 속성을 찾을 수 없는 경우 로깅 후 매수 스킵
                    logging.error("현금 잔고 정보를 찾을 수 없습니다.")
                    available_cash = 0
            except Exception as e:
                logging.error(f"현금 잔고 확인 중 오류 발생: {str(e)}")
                available_cash = 0
            
            # 안전한 포맷팅을 위해 숫자 타입인지 확인
            try:
                available_cash_float = float(available_cash)
                logging.info(f"사용 가능한 현금 잔고: {available_cash_float:,.0f}원")
            except (ValueError, TypeError):
                logging.info(f"사용 가능한 현금 잔고: {available_cash}원")
                available_cash_float = 0
        
        # 사용 가능한 잔고가 없으면 매수 스킵 (단, 모의투자는 제외)
        if available_cash_float <= 0 and not is_virtual:
            logging.warning("사용 가능한 현금 잔고가 없어 매수를 진행하지 않습니다.")
            # 안전한 합계 계산
            total_sell = sum(float(r['total_value']) for r in sell_results if r['success'] and isinstance(r['total_value'], (int, float)))
            
            result = {
                'sell_results': sell_results,
                'buy_results': [],
                'total_sell_value': total_sell,
                'total_buy_value': 0,
                'net_cash_flow': total_sell,
                'sell_count': len([r for r in sell_results if r['success']]),
                'buy_count': 0
            }
            return result
        
        # 모의투자에서 잔고가 0인 경우 최소 금액 설정 (1억원)
        if is_virtual and available_cash_float <= 0:
            available_cash_float = 100000000  # 1억원
            logging.warning("모의투자 모드에서 가상 잔고가 0원이므로 기본값 1억원으로 설정합니다.")
        
        # 4. 매수 종목 선정 (설정에 따라 상위 N개)
        max_buy_stocks = self.config.get("trading_settings", {}).get("max_buy_stocks", 3)
        buy_targets = buy_recommendations[:max_buy_stocks]
        
        # 5. 매수 금액 설정 (설정에 따라 사용 가능 금액의 일정 비율을 균등 분배)
        budget_percentage = self.config.get("trading_settings", {}).get("budget_percentage", 30)
        buy_budget_per_stock = (available_cash_float * budget_percentage / 100) / max(len(buy_targets), 1)
        
        # 6. 매수 실행
        buy_results = []
        for ticker in buy_targets:
            try:
                # 현재가 확인
                stock = self.kis.stock(ticker)
                quote = stock.quote()
                current_price = quote.price
                
                # decimal.Decimal 타입인 경우 float로 변환
                try:
                    current_price = float(current_price)
                except (TypeError, ValueError):
                    logging.error(f"{ticker} 현재가를 float로 변환할 수 없습니다: {current_price}")
                    continue
                
                # 매수 수량 계산 (정수로)
                quantity = int(buy_budget_per_stock / current_price)
                
                if quantity > 0:
                    # 주문 실행
                    success = self.submit_order(ticker, current_price, quantity, order_type="buy")
                    
                    result = {
                        'ticker': ticker,
                        'price': current_price,
                        'quantity': quantity,
                        'total_value': current_price * quantity,
                        'success': success
                    }
                    
                    buy_results.append(result)
                    
                    if success:
                        try:
                            logging.info(f"매수 주문 성공: {ticker}, {quantity}주 @ {float(current_price):,.0f}원, 총액: {float(current_price * quantity):,.0f}원")
                        except (ValueError, TypeError):
                            logging.info(f"매수 주문 성공: {ticker}, {quantity}주 @ {current_price}원, 총액: {current_price * quantity}원")
                    else:
                        logging.error(f"매수 주문 실패: {ticker}")
                else:
                    try:
                        logging.warning(f"매수 가능 수량이 0인 종목: {ticker}, 현재가: {float(current_price):,.0f}")
                    except (ValueError, TypeError):
                        logging.warning(f"매수 가능 수량이 0인 종목: {ticker}, 현재가: {current_price}")
                    
            except Exception as e:
                logging.error(f"{ticker} 매수 중 오류 발생: {str(e)}")
                buy_results.append({
                    'ticker': ticker,
                    'success': False,
                    'error': str(e)
                })
        
        # 7. 결과 종합 - 안전한 합계 계산
        try:
            total_sell_value = sum(float(r['total_value']) for r in sell_results if r['success'] and isinstance(r['total_value'], (int, float)))
            total_buy_value = sum(float(r['total_value']) for r in buy_results if r['success'] and isinstance(r['total_value'], (int, float)))
        except (ValueError, TypeError):
            total_sell_value = 0
            total_buy_value = 0
        
        result = {
            'sell_results': sell_results,
            'buy_results': buy_results,
            'total_sell_value': total_sell_value,
            'total_buy_value': total_buy_value,
            'net_cash_flow': total_sell_value - total_buy_value,
            'sell_count': len([r for r in sell_results if r['success']]),
            'buy_count': len([r for r in buy_results if r['success']])
        }
        
        try:
            logging.info(f"자동 매매 사이클 완료: 매도 {result['sell_count']}종목 {float(total_sell_value):,.0f}원, 매수 {result['buy_count']}종목 {float(total_buy_value):,.0f}원")
        except (ValueError, TypeError):
            logging.info(f"자동 매매 사이클 완료: 매도 {result['sell_count']}종목 {total_sell_value}원, 매수 {result['buy_count']}종목 {total_buy_value}원")
        
        return result
