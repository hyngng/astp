import logging
import traceback
import time
import os
import sys
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any, Union
from module.analysts import TBM_Strategy

# 상대 경로 문제 해결
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

class Trader:
    """주식 거래를 담당하는 클래스
    
    이 클래스는 매수/매도 결정 및 주문 실행을 담당합니다.
    """
    
    def __init__(self, kis, config):
        """Trader 클래스 초기화
        
        Args:
            kis: PyKis 라이브러리 인스턴스
            config: 설정 정보 딕셔너리
        """
        self.kis = kis
        self.config = config
        self.holdings = {}  # 보유 종목 정보
        
        # 설정 값 로드
        trading_settings = config.get("trading_settings", {})
        self.max_buy_stocks = self._get_max_buy_stocks()
        self.stop_loss_pct = trading_settings.get("stop_loss_pct", 5.0)
        self.take_profit_pct = trading_settings.get("take_profit_pct", 15.0)
        self.is_virtual = config.get("api_info", {}).get("is_virtual", True)
        
        # 분석 전략 초기화
        risk_level = trading_settings.get("risk_level", 2)
        self.tbm_strategy = TBM_Strategy(kis, config, risk_level=risk_level)
        
        # 세션 최적화 및 보유 종목 초기화
        self._optimize_kis_session()
        self.update_holdings()
        
        logging.info(f"트레이더 초기화 완료 (모드: {'모의투자' if self.is_virtual else '실제투자'})")
    
    def _get_max_buy_stocks(self) -> int:
        """최대 매수 종목 수 설정 가져오기"""
        try:
            max_stocks_setting = self.config.get("trading_settings", {}).get("max_buy_stocks", 3)
            
            # GitHub Actions 환경변수 패턴 확인 (${ENV_VAR})
            if isinstance(max_stocks_setting, str) and "${" in max_stocks_setting:
                logging.info(f"GitHub Actions 환경 변수 패턴 감지: {max_stocks_setting}, 기본값 3 사용")
                return 3
            
            # 정수로 변환 시도
            return int(max_stocks_setting)
        except (ValueError, TypeError):
            logging.warning(f"max_buy_stocks 설정 변환 실패, 기본값 3 사용")
            return 3
    
    def _optimize_kis_session(self):
        """PyKis 세션 최적화"""
        try:
            if hasattr(self.kis, 'session') and self.kis.session:
                # 연결 유지 활성화
                self.kis.session.keep_alive = True
                
                # 타임아웃 설정
                if hasattr(self.kis.session, 'timeout'):
                    self.kis.session.timeout = 60
                
                # requests 세션인 경우 어댑터 설정
                if hasattr(self.kis.session, 'adapters'):
                    from requests.adapters import HTTPAdapter
                    from urllib3.util.retry import Retry
                    
                    retry_strategy = Retry(
                        total=3,
                        backoff_factor=1,
                        status_forcelist=[429, 500, 502, 503, 504],
                        allowed_methods=["HEAD", "GET", "POST"],
                    )
                    
                    adapter = HTTPAdapter(max_retries=retry_strategy)
                    self.kis.session.mount("https://", adapter)
                    self.kis.session.mount("http://", adapter)
                
                logging.info("PyKis 세션 최적화 완료")
        except Exception as e:
            logging.warning(f"PyKis 세션 최적화 실패: {str(e)}")

    def api_call_with_retry(self, func, *args, max_retries=3, initial_delay=2, **kwargs):
        """API 호출 재시도 로직

        Args:
            func: 호출할 함수
            *args: 함수에 전달할 위치 인자
            max_retries: 최대 재시도 횟수
            initial_delay: 초기 대기 시간(초)
            **kwargs: 함수에 전달할 키워드 인자

        Returns:
            함수 호출 결과
        """
        retry_count = 0
        last_exception = None
        
        while retry_count < max_retries:
            try:
                # API 호출 실행
                return func(*args, **kwargs)
            
            except Exception as e:
                retry_count += 1
                last_exception = e
                
                # 네트워크 오류 또는 API 제한 관련 오류 확인
                error_str = str(e).lower()
                is_network_error = any(err in error_str for err in 
                                     ['connection', 'timeout', 'reset', 'refused', 'eof'])
                is_rate_limit = 'rate limit' in error_str or '429' in error_str
                
                # 로그 메시지 생성
                if retry_count < max_retries:
                    delay = initial_delay * (2 ** (retry_count - 1))  # 지수 백오프
                    error_type = "네트워크 오류" if is_network_error else "API 제한" if is_rate_limit else "API 오류"
                    logging.warning(f"{error_type} 발생, {delay}초 후 재시도 ({retry_count}/{max_retries}): {str(e)}")
                    time.sleep(delay)
                else:
                    logging.error(f"최대 재시도 횟수 초과, 실패: {str(e)}")
        
        # 모든 재시도 실패 시
        if last_exception:
            raise last_exception
        return None
    
    def get_trading_hours(self):
        """미국 시장 개장 여부 확인"""
        try:
            return self.api_call_with_retry(
                lambda: self.kis.trading_hours("US").is_open
            )
        except Exception as e:
            logging.error(f"미국 시장 개장 여부 확인 실패: {str(e)}")
            # 연결 오류 발생 시 기본값 반환 (장 시간으로 가정)
            return True
    
    def update_holdings(self):
        """보유 종목 정보 업데이트"""
        try:
            # 계좌 객체 가져오기
            account = self.kis.account()
            
            # 잔고 정보 요청
            balance = self.api_call_with_retry(lambda: account.balance())
            
            # 보유종목 정보 저장
            self.holdings = {}
            
            # 튜토리얼에 따라 balance.stocks 활용
            if hasattr(balance, 'stocks') and balance.stocks:
                for stock in balance.stocks:
                    try:
                        # 종목 정보 형식화
                        stock_ticker = getattr(stock, 'symbol', 
                                             getattr(stock, 'ticker', None))
                        
                        if not stock_ticker:
                            continue
                        
                        # 종목 정보 저장
                        stock_info = {
                            'ticker': stock_ticker,
                            'quantity': getattr(stock, 'qty', 0),
                            'price': getattr(stock, 'price', 0),
                            'purchase_price': getattr(stock, 'avg_price', 
                                                    getattr(stock, 'purchase_price', 0)),
                            'current_value': getattr(stock, 'amount', 0),
                            'profit': getattr(stock, 'profit', 0),
                            'profit_rate': getattr(stock, 'profit_rate', 0)
                        }
                        
                        self.holdings[stock_ticker] = stock_info
                    except Exception as stock_err:
                        logging.error(f"종목 정보 처리 중 오류: {str(stock_err)}")
            
            logging.info(f"보유종목 업데이트 완료: {len(self.holdings)}개 종목")
            return True
        
        except Exception as e:
            logging.error(f"보유종목 업데이트 실패: {str(e)}")
            logging.error(traceback.format_exc())
            return False

    def get_quote(self, ticker):
        """종목 시세 정보 조회"""
        try:
            stock = self.kis.stock(ticker)
            return self.api_call_with_retry(lambda: stock.quote())
        except Exception as e:
            logging.error(f"{ticker} 시세 조회 실패: {str(e)}")
            return None

    def check_sell_conditions(self, ticker):
        """매도 조건 확인
        
        Args:
            ticker: 종목 코드
            
        Returns:
            (bool, dict): 매도 여부 및 매도 이유
        """
        if ticker not in self.holdings:
            return False, {"reason": "보유종목 아님"}
        
        try:
            # 보유종목 정보 가져오기
            holding = self.holdings[ticker]
            
            # 현재 시세 조회
            quote = self.get_quote(ticker)
            if not quote:
                return False, {"reason": "시세 조회 실패"}
            
            # 튜토리얼에 따라 price 속성 사용
            current_price = quote.price
            purchase_price = holding['purchase_price']
            
            # 손절가, 목표가 계산
            stop_loss = purchase_price * (1 - self.stop_loss_pct / 100)
            take_profit = purchase_price * (1 + self.take_profit_pct / 100)
            
            # 손익률 계산
            profit_pct = ((current_price / purchase_price) - 1) * 100
            
            # 손절 조건 확인
            if current_price <= stop_loss:
                return True, {
                    "reason": "손절",
                    "purchase_price": purchase_price,
                    "current_price": current_price,
                    "profit_pct": profit_pct
                }
            
            # 목표가 도달 확인
            if current_price >= take_profit:
                return True, {
                    "reason": "목표가 도달",
                    "purchase_price": purchase_price,
                    "current_price": current_price,
                    "profit_pct": profit_pct
                }
            
            # TBM 전략 분석
            success, result = self.tbm_strategy.analyze(ticker)
            if success and result.get('signal') == 'DEAD_CROSS':
                return True, {
                    "reason": "매도 신호(DEAD_CROSS)",
                    "purchase_price": purchase_price,
                    "current_price": current_price,
                    "profit_pct": profit_pct
                }
            
            return False, {
                "reason": "매도 조건 미충족",
                "purchase_price": purchase_price,
                "current_price": current_price,
                "profit_pct": profit_pct
            }
            
        except Exception as e:
            logging.error(f"{ticker} 매도 조건 확인 중 오류: {str(e)}")
            return False, {"reason": f"오류: {str(e)}"}
    
    def check_all_sell_conditions(self):
        """모든 보유종목 매도 조건 확인"""
        sell_candidates = []

        for ticker in self.holdings:
            # API 호출 제한 방지를 위한 약간의 지연
            time.sleep(0.5)
            
            should_sell, result = self.check_sell_conditions(ticker)
            if should_sell:
                sell_candidates.append({
                    "ticker": ticker,
                    "reason": result["reason"],
                    "purchase_price": result.get("purchase_price", 0),
                    "current_price": result.get("current_price", 0),
                    "profit_pct": result.get("profit_pct", 0),
                    "quantity": self.holdings[ticker]["quantity"]
                })

        return sell_candidates

    def submit_order(self, ticker, price, quantity, order_type="BUY"):
        """주문 제출
        
        Args:
            ticker: 종목 코드
            price: 주문 가격
            quantity: 주문 수량
            order_type: 주문 유형 ("BUY" 또는 "SELL")
            
        Returns:
            bool: 주문 성공 여부
        """
        if not ticker or price is None or quantity is None:
            logging.error(f"주문 정보 부족: ticker={ticker}, price={price}, quantity={quantity}")
            return False
        
        if quantity <= 0:
            logging.warning(f"주문 수량이 0 이하입니다: {quantity}. 주문을 취소합니다.")
            return False
        
        order_type = order_type.upper()
        
        try:
            logging.info(f"{'모의' if self.is_virtual else '실제'} 주문 시도: {ticker} {order_type} {quantity}주 @ {price:,.2f}")
            
            # stock 객체를 통한 주문 (PyKis 튜토리얼 방식)
            stock = self.kis.stock(ticker)
            
            try:
                if order_type == "BUY":
                    # 매수 주문 (qty 파라미터 사용)
                    self.api_call_with_retry(
                        lambda: stock.buy(price=price, qty=quantity)
                    )
                else:
                    # 매도 주문 (qty 파라미터 사용)
                    self.api_call_with_retry(
                        lambda: stock.sell(price=price, qty=quantity)
                    )
                
                logging.info(f"주문 성공: {ticker} {order_type} {quantity}주 @ {price:,.2f}")
                return True
                
            except Exception as e:
                logging.warning(f"stock.buy/sell(qty) 호출 실패: {str(e)}")
                
                # qty 대신 volume 시도
                if "argument" in str(e).lower() and "qty" in str(e).lower():
                    try:
                        if order_type == "BUY":
                            self.api_call_with_retry(
                                lambda: stock.buy(price=price, volume=quantity)
                            )
                        else:
                            self.api_call_with_retry(
                                lambda: stock.sell(price=price, volume=quantity)
                            )
                        
                        logging.info(f"주문 성공(volume 파라미터): {ticker} {order_type} {quantity}주 @ {price:,.2f}")
                        return True
                    except Exception as vol_err:
                        logging.warning(f"volume 파라미터 시도 실패: {str(vol_err)}")
                
                # 계좌 객체를 통한 주문 (fallback)
                try:
                    account = self.kis.account()
                    method_name = None
                    
                    # 시장에 따라 적절한 메서드 선택
                    is_us_stock = any(c.isalpha() for c in ticker)
                    
                    if order_type == "BUY":
                        if is_us_stock and hasattr(account, 'overseas_buy'):
                            method_name = 'overseas_buy'
                        elif hasattr(account, 'domestic_buy'):
                            method_name = 'domestic_buy'
                    else:
                        if is_us_stock and hasattr(account, 'overseas_sell'):
                            method_name = 'overseas_sell'
                        elif hasattr(account, 'domestic_sell'):
                            method_name = 'domestic_sell'
                    
                    if method_name:
                        method = getattr(account, method_name)
                        self.api_call_with_retry(
                            lambda: method(ticker, price, volume=quantity)
                        )
                        logging.info(f"주문 성공({method_name}): {ticker} {order_type} {quantity}주 @ {price:,.2f}")
                        return True
                
                except Exception as acc_err:
                    logging.error(f"계좌 객체 주문 실패: {str(acc_err)}")
            
            logging.error(f"{ticker} {order_type} 주문 실패: 모든 방법 시도 실패")
            return False
            
        except Exception as outer_e:
            logging.error(f"{ticker} {order_type} 주문 중 오류: {str(outer_e)}")
            logging.error(f"주문 오류 상세: {traceback.format_exc()}")
            return False
    
    def execute_sell_orders(self, sell_candidates=None):
        """매도 주문 실행
        
        Args:
            sell_candidates: 매도 대상 종목 리스트 (없으면 자동 확인)
            
        Returns:
            list: 매도 결과 리스트
        """
        if sell_candidates is None:
            sell_candidates = self.check_all_sell_conditions()
        
        sell_results = []
        
        for candidate in sell_candidates:
            ticker = candidate["ticker"]
            quantity = candidate["quantity"]
            current_price = candidate.get("current_price", 0)
            
            # 현재가가 없으면 조회
            if current_price <= 0:
                quote = self.get_quote(ticker)
                if quote:
                    # 튜토리얼에 따라 price 속성 사용
                    current_price = quote.price
            
            # 매도 주문 실행
            success = self.submit_order(
                ticker=ticker,
                price=current_price,
                quantity=quantity,
                order_type="SELL"
            )
            
            result = {
                "ticker": ticker,
                "success": success,
                "quantity": quantity,
                "price": current_price,
                "reason": candidate["reason"],
                "profit_pct": candidate.get("profit_pct", 0)
            }
            
            sell_results.append(result)
            
            # API 호출 제한 방지 지연
            time.sleep(1)
        
        return sell_results

    def select_stocks_to_buy(self, max_count=None):
        """매수할 종목 선택
        
        Args:
            max_count: 최대 선택 종목 수
            
        Returns:
            list: 매수 대상 종목 리스트
        """
        if max_count is None:
            max_count = self.max_buy_stocks
        
        try:
            # 매수 후보 종목 초기화
            buy_candidates = []
            
            # 1. main.py에서 전달받은 골든크로스 종목 사용 (최우선)
            golden_cross_tickers = getattr(self, 'golden_cross_tickers', [])
            if golden_cross_tickers:
                logging.info(f"main.py에서 전달받은 골든크로스 종목 처리: {len(golden_cross_tickers)}개")
                
                for ticker in golden_cross_tickers:
                    # 이미 보유 중인 종목 스킵
                    if ticker in self.holdings:
                        continue
                        
                    # 현재 시세 조회
                    quote = self.get_quote(ticker)
                    if not quote:
                        continue
                    
                    # 매수 후보 추가
                    buy_candidates.append({
                        "ticker": ticker,
                        "price": quote.price,  # 튜토리얼에 따라 price 속성 사용
                        "signal": "GOLDEN_CROSS",
                        "confidence": 0.9  # 높은 신뢰도 부여
                    })
                    
                    # API 호출 제한 방지 지연
                    time.sleep(0.5)
            
            # 2. 아직 필요한 종목 수에 도달하지 않았으면 TBM 전략 사용
            if len(buy_candidates) < max_count:
                additional_needed = max_count - len(buy_candidates)
                
                # TBM 전략 추천 종목 가져오기
                recommendations = self.tbm_strategy.generate_recommendations()
                
                # 중복 확인을 위한 기존 후보 티커 목록
                existing_tickers = [c["ticker"] for c in buy_candidates]
                
                for ticker in recommendations:
                    # 최대 종목 수 도달하면 중단
                    if len(buy_candidates) >= max_count:
                        break
                        
                    # 이미 후보에 있거나 보유 중인 종목 스킵
                    if ticker in existing_tickers or ticker in self.holdings:
                        continue
                    
                    try:
                        # 상세 분석
                        success, result = self.tbm_strategy.analyze(ticker)
                        if success and result.get('signal') in ['GOLDEN_CROSS', 'BUY', 'STRONG_BUY']:
                            # 현재 시세 조회
                            quote = self.get_quote(ticker)
                            if not quote:
                                continue
                            
                            # 매수 후보 추가
                            buy_candidates.append({
                                "ticker": ticker,
                                "price": quote.price,  # 튜토리얼에 따라 price 속성 사용
                                "signal": result.get('signal'),
                                "confidence": result.get('confidence', 0.7)
                            })
                            
                            # 기존 후보 티커 목록 업데이트
                            existing_tickers.append(ticker)
                        
                        # API 호출 제한 방지 지연
                        time.sleep(0.5)
                        
                    except Exception as e:
                        logging.error(f"{ticker} TBM 분석 중 오류: {str(e)}")
            
            # 신뢰도순 정렬 후 최대 종목수 제한
            buy_candidates.sort(key=lambda x: x.get('confidence', 0), reverse=True)
            final_candidates = buy_candidates[:max_count]
            
            if final_candidates:
                logging.info(f"최종 매수 대상: {len(final_candidates)}개 종목 {[c['ticker'] for c in final_candidates]}")
            else:
                logging.info("매수 신호가 있는 종목이 없습니다.")
                
            return final_candidates
            
        except Exception as e:
            logging.error(f"매수 종목 선택 중 오류: {str(e)}")
            return []
    
    def calculate_order_quantity(self, price, available_funds=None, risk_pct=10):
        """주문 수량 계산
        
        Args:
            price: 종목 가격
            available_funds: 주문 가능 금액 (None이면 자동 계산)
            risk_pct: 한 종목당 투자 비율 (%)
            
        Returns:
            int: 주문 수량
        """
        try:
            if not available_funds:
                # 계좌 객체로 주문 가능 금액 조회
                account = self.kis.account()
                balance = self.api_call_with_retry(lambda: account.balance())
                
                # 튜토리얼에 따라 deposits['KRW']에서 금액 가져오기
                if hasattr(balance, 'deposits') and 'KRW' in balance.deposits:
                    available_funds = balance.deposits['KRW'].amount
                elif hasattr(balance, 'deposits') and 'USD' in balance.deposits:
                    # 해외주식용 USD 예수금
                    available_funds = balance.deposits['USD'].amount
                else:
                    # 예전 방식 호환성 유지
                    available_funds = getattr(balance, 'available_funds', 
                                           getattr(balance, 'cash', 0))
                
                # 로그 추가
                logging.info(f"주문 가능 금액: {available_funds:,}")
            
            if available_funds <= 0:
                logging.warning("주문 가능 금액이 0 이하입니다.")
                return 0
            
            # decimal.Decimal 타입 처리
            import decimal
            if isinstance(available_funds, decimal.Decimal):
                # Decimal로 계산
                risk_decimal = decimal.Decimal(str(risk_pct)) / decimal.Decimal('100')
                invest_amount = available_funds * risk_decimal
            else:
                # 일반 float 계산
                invest_amount = float(available_funds) * (risk_pct / 100)
            
            # 가격도 Decimal일 수 있으므로 float로 변환
            price_float = float(price)
            
            # 주문 수량 계산 (정수로 내림)
            quantity = int(float(invest_amount) / price_float)
            
            return max(0, quantity)
            
        except Exception as e:
            logging.error(f"주문 수량 계산 중 오류: {str(e)}")
            logging.error(traceback.format_exc())
            return 0
    
    def auto_trading_cycle(self, is_pre_market=False):
        """자동 거래 사이클 실행
        
        Args:
            is_pre_market: 장 전 거래 사이클 여부
            
        Returns:
            dict: 거래 결과 요약
        """
        cycle_start_time = datetime.now()
        logging.info(f"자동 거래 사이클 시작 (장 {'전' if is_pre_market else '중'})")
        
        results = {
            "cycle_time": cycle_start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "is_pre_market": is_pre_market,
            "update_holdings": False,
            "sell_orders": [],
            "buy_orders": []
        }
        
        try:
            # 1. 보유종목 정보 업데이트
            logging.info("1. 보유종목 정보 업데이트 중...")
            holdings_updated = self.update_holdings()
            results["update_holdings"] = holdings_updated
            
            if not holdings_updated:
                logging.warning("보유종목 업데이트 실패, 안전을 위해 매수/매도 중단")
                return results
            
            # API 호출 간 지연
            time.sleep(1)
            
            # 2. 매도 조건 확인 및 매도 주문 실행
            logging.info("2. 매도 조건 확인 및 주문 실행 중...")
            sell_candidates = self.check_all_sell_conditions()
            
            if sell_candidates:
                logging.info(f"{len(sell_candidates)}개 종목 매도 조건 충족")
                sell_results = self.execute_sell_orders(sell_candidates)
                results["sell_orders"] = sell_results
            else:
                logging.info("매도 조건을 충족하는 종목이 없습니다.")
            
            # API 호출 간 지연
            time.sleep(1)
            
            # 3. 매수 종목 선택 및 주문 실행
            logging.info("3. 매수 종목 선택 및 주문 실행 중...")
            
            # 보유 종목 수 확인
            current_holdings = len(self.holdings)
            max_buy_stocks = self.max_buy_stocks
            
            if current_holdings >= max_buy_stocks:
                logging.info(f"이미 최대 보유 종목 수({current_holdings}/{max_buy_stocks})에 도달했습니다.")
            else:
                # 추가 매수 가능 종목 수
                available_slots = max_buy_stocks - current_holdings
                
                # 골든크로스 종목 정보 확인 (main.py에서 설정)
                golden_cross_tickers = getattr(self, 'golden_cross_tickers', [])
                buy_candidates = []
                
                if golden_cross_tickers:
                    logging.info(f"main.py에서 전달받은 골든크로스 종목: {len(golden_cross_tickers)}개")
                    
                    # 이미 보유 중인 종목 필터링
                    filtered_tickers = [t for t in golden_cross_tickers if t not in self.holdings]
                    logging.info(f"매수 고려할 골든크로스 종목: {len(filtered_tickers)}개")
                    
                    # 최대 가능 종목 수만큼만 처리
                    for ticker in filtered_tickers[:available_slots]:
                        try:
                            # 현재 시세 조회
                            quote = self.get_quote(ticker)
                            if not quote:
                                logging.warning(f"{ticker} 시세 조회 실패")
                                continue
                            
                            # 주문 수량 계산
                            price = quote.price  # 튜토리얼에 따라 price 속성 사용
                            quantity = self.calculate_order_quantity(price)
                            
                            if quantity <= 0:
                                logging.warning(f"{ticker} 주문 수량이 0 이하 (가격: {price})")
                                continue
                            
                            buy_candidates.append({
                                "ticker": ticker,
                                "price": price,
                                "quantity": quantity,
                                "signal": "GOLDEN_CROSS"
                            })
                            
                            # API 호출 제한 방지
                            time.sleep(0.5)
                            
                        except Exception as e:
                            logging.error(f"{ticker} 매수 준비 중 오류: {str(e)}")
                
                # 매수 주문 실행
                if buy_candidates:
                    logging.info(f"{len(buy_candidates)}개 종목 매수 신호 발생")
                    
                    buy_results = []
                    for candidate in buy_candidates:
                        ticker = candidate["ticker"]
                        price = candidate["price"]
                        quantity = candidate["quantity"]
                        
                        # 매수 주문 실행
                        success = self.submit_order(
                            ticker=ticker,
                            price=price,
                            quantity=quantity,
                            order_type="BUY"
                        )
                        
                        buy_results.append({
                            "ticker": ticker,
                            "success": success,
                            "quantity": quantity,
                            "price": price,
                            "signal": candidate.get("signal")
                        })
                        
                        # API 호출 제한 방지 지연
                        time.sleep(1)
                    
                    results["buy_orders"] = buy_results
                else:
                    logging.info("매수 신호가 있는 종목이 없습니다.")
            
            # 4. 최종 보유종목 정보 업데이트 (진행 상황 확인)
            time.sleep(1)
            self.update_holdings()
            
            # 5. 거래 사이클 결과 요약
            cycle_duration = (datetime.now() - cycle_start_time).total_seconds()
            results["duration_seconds"] = cycle_duration
            
            logging.info(f"자동 거래 사이클 완료 (소요시간: {cycle_duration:.1f}초)")
            logging.info(f"- 매도 주문: {len(results['sell_orders'])}건")
            logging.info(f"- 매수 주문: {len(results['buy_orders'])}건")
            
            return results
            
        except Exception as e:
            logging.error(f"자동 거래 사이클 실행 중 오류: {str(e)}")
            logging.error(traceback.format_exc())
            
            results["error"] = str(e)
            return results 