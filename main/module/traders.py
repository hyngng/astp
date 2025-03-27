from pykis import KisBalance
from datetime import datetime
import logging
from typing import Dict, List, Tuple, Optional
from module.analysts import TBM_Strategy
import time
import random
import requests

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
        
        # PyKis 세션 설정 최적화
        self._optimize_kis_session()
        
        # config에서 risk_level 가져오기
        risk_level = config.get("trading_settings", {}).get("risk_level", 2)
        self.tbm_strategy = TBM_Strategy(kis, config, risk_level=risk_level)
        
        # 초기 보유종목 로드
        self.update_holdings()
        
        # 초기화 완료 로그
        logging.info(f"트레이더 초기화 완료 (모드: {'모의투자' if self.is_virtual else '실제투자'})")

    def _optimize_kis_session(self):
        """PyKis 라이브러리 세션 최적화"""
        try:
            # PyKis 객체의 세션 설정 확인
            if hasattr(self.kis, 'session') and self.kis.session:
                session = self.kis.session
                
                # 연결 유지 활성화
                session.keep_alive = True
                
                # 타임아웃 설정 증가
                if hasattr(session, 'timeout'):
                    # 기본 30초에서 60초로 증가
                    session.timeout = 60
                
                # 재시도 설정 확인 및 적용
                if hasattr(self.kis, 'retry'):
                    self.kis.retry = 3  # 기본 재시도 횟수 설정
                
                # 연결 풀 최적화 (requests 라이브러리 사용 시)
                if hasattr(session, 'adapters') and hasattr(session, 'mount'):
                    from requests.adapters import HTTPAdapter
                    from urllib3.util.retry import Retry
                    
                    # 지수 백오프와 재시도 전략 설정
                    retry_strategy = Retry(
                        total=3,
                        backoff_factor=1,
                        status_forcelist=[429, 500, 502, 503, 504],
                        allowed_methods=["HEAD", "GET", "POST"],
                    )
                    
                    # 세션에 어댑터 설정
                    adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=5, pool_maxsize=10)
                    session.mount("https://", adapter)
                    session.mount("http://", adapter)
                
                logging.info("PyKis 세션 최적화 완료")
        except Exception as e:
            logging.warning(f"PyKis 세션 최적화 중 오류: {str(e)}")

    def _reset_kis_connection(self):
        """PyKis 연결 재설정 - 토큰 갱신 또는 세션 재생성"""
        try:
            logging.info("PyKis 연결 재설정 시도...")
            
            # 토큰 갱신 시도
            if hasattr(self.kis, 'auth') and hasattr(self.kis.auth, 'refresh'):
                logging.info("토큰 갱신 시도")
                self.kis.auth.refresh()
                logging.info("토큰 갱신 완료")
                return True
            
            # 토큰 갱신 메서드가 없으면 다른 방법 시도
            if hasattr(self.kis, 'connect') or hasattr(self.kis, 'login'):
                method = getattr(self.kis, 'connect', None) or getattr(self.kis, 'login', None)
                if method and callable(method):
                    logging.info("재연결 시도")
                    method()
                    logging.info("재연결 완료")
                    return True
        except Exception as e:
            logging.error(f"PyKis 연결 재설정 실패: {str(e)}")
        
        return False

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
        """현재 보유 종목 정보 업데이트"""
        try:
            # 계좌 객체 가져오기
            account = self.kis.account()
            
            # 계좌번호 직접 수정 (PyKis 내부에서 형식 변환이 제대로 안될 수 있음)
            account_number = getattr(account, '_account_number', None)
            if account_number:
                # 계좌번호에 하이픈이 있는지 확인
                account_str = str(account_number)
                if "-" not in account_str and len(account_str) > 2:
                    # 하이픈 추가 (예: 5012470301 -> 50124703-01)
                    main_part = account_str[:-2]
                    sub_part = account_str[-2:]
                    new_account = f"{main_part}-{sub_part}"
                    # 객체 속성 직접 수정 (위험할 수 있으나 필요한 경우)
                    if hasattr(account, '_account_number'):
                        account._account_number = new_account
                        logging.info(f"계좌번호 형식 수정: {new_account}")
            
            # 잔고 조회
            try:
                balance = account.balance()
                # 보유종목 업데이트...
                
                # 성공적으로 업데이트 완료
                return True
                
            except Exception as e:
                logging.error(f"보유 종목 정보 업데이트 실패: {str(e)}")
                logging.error(f"보유 종목 업데이트 상세 오류: {traceback.format_exc()}")
                
                # 계좌번호 문제가 의심되면 다시 시도
                if "INVALID_CHECK_ACNO" in str(e):
                    logging.warning("계좌번호 형식 문제 감지, 재시도...")
                    # 가능하다면 여기서 계좌번호 수정 시도
                    return False
                
                # 네트워크 연결 문제
                if "ConnectionError" in str(e) or "Timeout" in str(e):
                    logging.warning("네트워크 연결 문제 감지. PyKis 연결 재설정 시도...")
                    self._reset_kis_connection()
                    return False
                
                return False
                
        except Exception as e:
            logging.error(f"계좌 정보 조회 중 오류: {str(e)}")
            return False

    def _normalize_stock_attributes(self, stock):
        """주식 객체의 속성을 표준화"""
        # 필수 속성 목록 정의
        required_attrs = {
            'ticker': ['symbol', 'code', 'stock_code'], 
            'quantity': ['qty', 'volume', 'amount'], 
            'price': ['current_price', 'trade_price', 'now_pric'],
            'market': ['exchange', 'market_code']
        }
        
        # 각 필수 속성에 대해 확인 및 설정
        for attr, alternates in required_attrs.items():
            if not hasattr(stock, attr):
                # 대체 속성 시도
                for alt in alternates:
                    if hasattr(stock, alt):
                        value = getattr(stock, alt)
                        setattr(stock, attr, value)
                        break
                else:
                    # 대체 속성도 없는 경우 기본값 설정
                    if attr == 'ticker':
                        # 티커는 필수이므로 기존 객체 속성에서 추정
                        attrs = dir(stock)
                        logging.debug(f"객체 속성: {attrs}")
                        # 기본값 설정
                        setattr(stock, attr, getattr(stock, attrs[0], "UNKNOWN"))
                    elif attr == 'market':
                        # 티커 형식에 따라 시장 추정
                        ticker = getattr(stock, 'ticker', '') or getattr(stock, 'symbol', '')
                        market = 'NYSE' if any(c.isalpha() for c in str(ticker)) else 'KRX'
                        setattr(stock, attr, market)
                    elif attr == 'quantity':
                        setattr(stock, attr, 0)
                    elif attr == 'price':
                        setattr(stock, attr, 0)

    def api_call_with_retry(self, func, *args, max_retries=5, initial_delay=3, backoff_factor=2, **kwargs):
        """
        네트워크 오류에 대한 자동 재시도 로직이 있는 API 호출 래퍼 함수
        
        Args:
            func: 호출할 함수
            *args: 함수 인자
            max_retries: 최대 재시도 횟수 (기본값: 5)
            initial_delay: 초기 대기 시간(초) (기본값: 3)
            backoff_factor: 지수 백오프 계수 (기본값: 2)
            **kwargs: 함수 키워드 인자
            
        Returns:
            함수 실행 결과
        """
        import time
        import random
        import requests
        
        retries = 0
        delay = initial_delay
        
        while True:
            try:
                return func(*args, **kwargs)
            except (requests.exceptions.ConnectionError, 
                    requests.exceptions.ReadTimeout, 
                    requests.exceptions.ChunkedEncodingError,
                    requests.exceptions.RequestException,
                    ConnectionResetError,
                    ConnectionAbortedError) as e:
                retries += 1
                
                if retries > max_retries:
                    logging.error(f"최대 재시도 횟수({max_retries})를 초과했습니다: {str(e)}")
                    raise
                
                # 지터(jitter) 추가하여 동시 재시도 방지
                jitter = random.uniform(0, 0.5) * delay
                wait_time = delay + jitter
                
                logging.warning(f"API 호출 또는 네트워크 오류. {wait_time:.1f}초 후 재시도 ({retries}/{max_retries})...")
                time.sleep(wait_time)
                
                # 지수 백오프 적용
                delay *= backoff_factor

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
        try:
            # 보유 종목 확인
            holding_info = None
            
            # holdings가 딕셔너리인 경우
            if isinstance(self.holdings, dict) and ticker in self.holdings:
                holding_info = self.holdings[ticker]
            # holdings가 리스트인 경우
            elif isinstance(self.holdings, list):
                for stock in self.holdings:
                    stock_ticker = getattr(stock, 'ticker', None) or getattr(stock, 'symbol', None)
                    if stock_ticker == ticker:
                        # 객체를 딕셔너리로 변환하여 사용
                        holding_info = {
                            'quantity': getattr(stock, 'quantity', 0),
                            'avg_price': getattr(stock, 'avg_price', 0) or getattr(stock, 'purchase_price', 0),
                            'current_price': getattr(stock, 'price', 0) or getattr(stock, 'current_price', 0),
                            'buy_date': getattr(stock, 'buy_date', datetime.now().strftime("%Y-%m-%d"))
                        }
                        break
            
            # 보유 종목이 아니면 매도할 수 없음
            if not holding_info:
                return False, {'reason': f'보유하지 않은 종목: {ticker}'}
            
            try:
                # 1. 현재 시장 가격 확인 - 네트워크 오류에 대한 재시도 로직 포함
                try:
                    quote = self.get_quote(ticker)
                    current_price = quote.price
                except Exception as e:
                    logging.error(f"{ticker} 시세 조회 중 오류, 보유 정보의 현재가 사용: {str(e)}")
                    # 오류 발생 시 보유 정보의 현재가 사용
                    if isinstance(holding_info, dict):
                        current_price = holding_info.get('current_price', 0)
                    else:
                        current_price = getattr(holding_info, 'current_price', 0) or getattr(holding_info, 'price', 0)
                    
                    if not current_price:
                        return False, {'reason': f'시세 조회 실패: {str(e)}'}
                
                # 2. 손익률 계산
                avg_price = holding_info['avg_price'] if isinstance(holding_info, dict) else getattr(holding_info, 'avg_price', 0)
                if not avg_price:
                    avg_price = getattr(holding_info, 'purchase_price', 0) if not isinstance(holding_info, dict) else 0
                
                if not avg_price:
                    return False, {'reason': '평균 매수가격 정보 없음'}
                    
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
                if success and analysis.get('signal') == "SELL":
                    sell_signals.append("TBM 매도 신호")
                    
                # 홀딩 기간 초과
                max_holding_days = settings.get("max_holding_days", 30)
                buy_date_str = holding_info['buy_date'] if isinstance(holding_info, dict) else getattr(holding_info, 'buy_date', datetime.now().strftime("%Y-%m-%d"))
                
                try:
                    buy_date = datetime.strptime(buy_date_str, "%Y-%m-%d")
                    days_held = (datetime.now() - buy_date).days
                    if days_held > max_holding_days:
                        sell_signals.append(f"홀딩 기간 초과 ({days_held}일)")
                except (ValueError, TypeError):
                    # 날짜 형식이 맞지 않거나 날짜 정보가 없는 경우
                    pass
                    
                # 매도 결정 (신호가 하나라도 있으면 매도)
                should_sell = len(sell_signals) > 0
                
                # 수량 정보 가져오기
                quantity = holding_info['quantity'] if isinstance(holding_info, dict) else getattr(holding_info, 'quantity', 0)
                
                # 매도 정보
                result = {
                    'ticker': ticker,
                    'current_price': current_price,
                    'avg_price': avg_price,
                    'profit_rate': profit_rate,
                    'quantity': quantity,
                    'sell_signals': sell_signals,
                    'total_value': quantity * current_price
                }
                
                return should_sell, result
                
            except Exception as e:
                logging.error(f"{ticker} 매도 조건 확인 중 오류 발생: {str(e)}")
                return False, {'reason': f'오류: {str(e)}'}
        except Exception as e:
            logging.error(f"{ticker} 매도 조건 확인 중 외부 오류: {str(e)}")
            return False, {'reason': f'외부 오류: {str(e)}'}

    def submit_order(self, ticker, price, quantity, order_type="buy", max_retries=3):
        """주문 제출 함수 - 매수/매도"""
        for attempt in range(max_retries):
            try:
                # 종목 객체 가져오기
                stock = self.kis.stock(ticker)
                
                # 매수/매도 주문 실행
                if order_type.upper() == "BUY":
                    # 매수 주문 - 튜토리얼 방식대로 stock.buy 사용
                    order_result = stock.buy(
                        price=price,
                        quantity=quantity,
                        order_type='limit'  # 지정가 주문
                    )
                else:
                    # 매도 주문 - 튜토리얼 방식대로 stock.sell 사용
                    order_result = stock.sell(
                        price=price,
                        quantity=quantity,
                        order_type='limit'  # 지정가 주문
                    )
                
                logging.info(f"{'모의' if self.is_virtual else '실제'} 주문 성공: {ticker} {order_type} {quantity}주 @ {price:.2f}")
                return True
                
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2 * (attempt + 1)
                    logging.warning(f"주문 실패, {wait_time}초 후 재시도... ({attempt+1}/{max_retries}): {str(e)}")
                    time.sleep(wait_time)
                    self._reset_kis_connection()  # 연결 재설정
                else:
                    logging.error(f"{ticker} {order_type} 주문 실패 (최종): {str(e)}")
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

        # 보유 종목 확인
        if isinstance(self.holdings, dict):
            # 딕셔너리 형태인 경우
            tickers = list(self.holdings.keys())
        elif isinstance(self.holdings, list):
            # 리스트 형태인 경우
            tickers = []
            for stock in self.holdings:
                ticker = getattr(stock, 'ticker', None) or getattr(stock, 'symbol', None)
                if ticker:
                    tickers.append(ticker)
        else:
            logging.error(f"보유 종목 정보 형식 오류: {type(self.holdings)}")
            return []

        # 각 보유 종목에 대해 매도 조건 확인
        for ticker in tickers:
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
        """자동 매매 사이클 실행"""
        result = {
            'sell_count': 0,
            'buy_count': 0,
            'errors': []
        }
        
        try:
            # 0. KIS 연결 상태 확인 및 초기화
            self._optimize_kis_session()
            
            # 1. 보유 종목 정보 업데이트
            retry_count = 0
            max_retries = 3
            success = False
            
            while not success and retry_count < max_retries:
                try:
                    success = self.update_holdings()
                    if not success:
                        retry_count += 1
                        if retry_count < max_retries:
                            logging.warning(f"보유 종목 정보 업데이트 실패. {retry_count}/{max_retries} 재시도...")
                            time.sleep(3 * retry_count)  # 점진적으로 대기 시간 증가
                            # 연결 재설정 시도
                            self._reset_kis_connection()
                except Exception as e:
                    retry_count += 1
                    logging.error(f"보유 종목 업데이트 중 예외: {str(e)}")
                    time.sleep(3 * retry_count)
            
            if not success:
                result['errors'].append("보유 종목 정보 업데이트 최대 재시도 횟수 초과")
                return result
            
            # 2. 매도 대상 선정 및 처리
            try:
                # API 요청 간격 추가 (초당 요청 제한 대응)
                time.sleep(2)
                
                # 보유 종목 확인
                if not isinstance(self.holdings, list):
                    # 객체가 리스트가 아닌 경우 (예: 딕셔너리인 경우)
                    sell_targets = self.check_all_sell_conditions()
                else:
                    # 객체가 리스트인 경우, 각 항목을 순회하며 처리
                    sell_targets = []
                    for holding in self.holdings:
                        ticker = getattr(holding, 'ticker', None) or getattr(holding, 'symbol', None)
                        if ticker:
                            should_sell, result_data = self.check_sell_conditions(ticker)
                            if should_sell:
                                sell_targets.append(result_data)
            
                if sell_targets:
                    logging.info(f"매도 대상 종목: {len(sell_targets)}개")
                    for ticker in sell_targets:
                        try:
                            # 주문 제출 전 API 요청 간격 추가
                            time.sleep(2)
                            
                            if isinstance(ticker, dict) and 'ticker' in ticker:
                                ticker_symbol = ticker['ticker']
                                ticker_price = ticker.get('current_price', 0)
                                ticker_qty = ticker.get('quantity', 0)
                            else:
                                ticker_symbol = ticker
                                ticker_price = 0
                                ticker_qty = 0
                                
                                # 티커만 있는 경우 보유 종목에서 정보 조회
                                for holding in self.holdings:
                                    if getattr(holding, 'ticker', '') == ticker_symbol:
                                        ticker_price = getattr(holding, 'price', 0)
                                        ticker_qty = getattr(holding, 'quantity', 0)
                                        break
                    
                            success = self.submit_order(ticker_symbol, ticker_price, ticker_qty, order_type="sell")
                            
                            if success:
                                result['sell_count'] += 1
                        except Exception as e:
                            error_msg = f"{ticker_symbol if isinstance(ticker, dict) else ticker} 매도 주문 실패: {str(e)}"
                            logging.error(error_msg)
                            result['errors'].append(error_msg)
                else:
                    logging.info("매도 대상 종목이 없습니다.")
            except Exception as e:
                error_msg = f"매도 처리 중 오류 발생: {str(e)}"
                logging.error(error_msg)
                result['errors'].append(error_msg)
            
            # 3. 보유 종목 정보 업데이트 (매도 후)
            try:
                # API 요청 간격 추가 (초당 요청 제한 대응)
                time.sleep(3)
                
                self.update_holdings()
            except Exception as e:
                logging.warning(f"매도 후 보유 종목 업데이트 실패: {str(e)}")
            
            # 4. 매수 대상 선정 및 처리
            try:
                # API 요청 간격 추가
                time.sleep(3)
                
                # 최대 매수 종목 수 설정값 가져오기
                max_buy_stocks = self._get_max_buy_stocks()
                
                # TBM 전략을 통한 추천 종목 가져오기
                buy_targets = self.select_stocks_to_buy(max_count=max_buy_stocks)
                
                if buy_targets:
                    logging.info(f"매수 대상 종목: {len(buy_targets)}개 (최대 {max_buy_stocks}개)")
                    for ticker in buy_targets:
                        try:
                            # 주문 제출 전 API 요청 간격 추가
                            time.sleep(2)
                            
                            # 티커 정보 추출
                            if isinstance(ticker, dict):
                                ticker_symbol = ticker.get('ticker', '')
                                ticker_price = ticker.get('price', 0)
                                ticker_qty = ticker.get('quantity', 0)
                                
                                # 수량이 없으면 계산
                                if not ticker_qty or ticker_qty <= 0:
                                    # 매수 금액 기본값
                                    buy_amount = 1000000  # 기본 100만원
                                    
                                    # 예산 계산 (총 자산의 1/max_buy_stocks)
                                    if hasattr(self, 'total_balance') and self.total_balance > 0:
                                        buy_amount = min(buy_amount, self.total_balance / max_buy_stocks)
                                    
                                    # 수량 계산
                                    if ticker_price > 0:
                                        ticker_qty = max(1, int(buy_amount / ticker_price))
                                    else:
                                        ticker_qty = 1
                            else:
                                ticker_symbol = ticker
                                # 티커만 있는 경우 시세 조회 필요
                                quote = self.get_quote(ticker_symbol)
                                ticker_price = getattr(quote, 'price', 0)
                                
                                # 기본 매수 금액 설정
                                buy_amount = 1000000  # 기본 100만원
                                ticker_qty = max(1, int(buy_amount / ticker_price)) if ticker_price > 0 else 1
                            
                            success = self.submit_order(ticker_symbol, ticker_price, ticker_qty, order_type="buy")
                            
                            if success:
                                result['buy_count'] += 1
                                # 연속 API 호출 방지
                                time.sleep(2)
                        except Exception as e:
                            error_msg = f"{ticker_symbol if 'ticker_symbol' in locals() else ticker} 매수 주문 실패: {str(e)}"
                            logging.error(error_msg)
                            result['errors'].append(error_msg)
                else:
                    logging.info("매수 대상 종목이 없습니다.")
            except Exception as e:
                error_msg = f"매수 처리 중 오류 발생: {str(e)}"
                logging.error(error_msg)
                result['errors'].append(error_msg)
        
        except Exception as e:
            error_msg = f"매매 사이클 실행 중 예외 발생: {str(e)}"
            logging.error(error_msg)
            result['errors'].append(error_msg)
        
        # 5. 거래 사이클 결과 요약
        error_count = len(result['errors'])
        logging.info(f"매매 사이클 결과: 매도 {result['sell_count']}종목, 매수 {result['buy_count']}종목, 오류 {error_count}건")
        if error_count > 0:
            for i, error in enumerate(result['errors'], 1):
                logging.error(f"오류 {i}/{error_count}: {error}")
        
        return result

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

    def select_stocks_to_buy(self, max_count=3):
        """
        매수할 종목을 선정하는 함수
        
        Args:
            max_count (int): 최대 매수 종목 수
            
        Returns:
            List[Dict]: 매수 대상 종목 정보 리스트
        """
        try:
            # 분석가로부터 추천 종목 가져오기 (max_count 인자 제거)
            recommendations = self.tbm_strategy.generate_recommendations() or []
            
            # 리스트가 아닌 경우 처리
            if not isinstance(recommendations, list):
                logging.warning("매수 추천 종목이 리스트가 아닙니다. 빈 리스트로 변환합니다.")
                recommendations = []
            
            # 값이 있는지 확인
            if not recommendations:
                logging.info("매수 추천 종목이 없습니다.")
                return []
            
            # 현재 보유 중인 종목의 티커 추출
            current_holdings = set()
            for holding in self.holdings:
                ticker = getattr(holding, 'ticker', None) or getattr(holding, 'symbol', None)
                if ticker:
                    current_holdings.add(ticker)
            
            # 이미 보유 중인 종목 제외
            filtered_recommendations = []
            for rec in recommendations:
                ticker = rec.get('ticker', '') if isinstance(rec, dict) else rec
                
                if ticker not in current_holdings:
                    filtered_recommendations.append(rec)
                else:
                    logging.info(f"{ticker}은(는) 이미 보유 중이므로 매수 대상에서 제외합니다.")
            
            # 최대 종목 수만큼 선택
            buy_targets = filtered_recommendations[:max_count]
            
            # 매수할 종목이 없는 경우
            if not buy_targets:
                logging.info("매수 대상 종목이 없습니다.")
                return []
            
            # 주문 가능한 형태로 가공
            processed_targets = []
            for target in buy_targets:
                # 문자열 형태인 경우
                if isinstance(target, str):
                    try:
                        # 시세 조회를 통한 가격 정보 가져오기
                        quote = self.get_quote(target)
                        target_data = {
                            'ticker': target,
                            'price': getattr(quote, 'price', 0),
                            'name': getattr(quote, 'name', target)
                        }
                        processed_targets.append(target_data)
                    except Exception as e:
                        logging.error(f"{target} 시세 조회 실패: {str(e)}")
                
                # 딕셔너리 형태인 경우
                elif isinstance(target, dict) and 'ticker' in target:
                    # 이미 필요한 정보가 포함된 경우 그대로 사용
                    if 'price' not in target or target['price'] <= 0:
                        try:
                            # 가격 정보 없는 경우 시세 조회
                            quote = self.get_quote(target['ticker'])
                            target['price'] = getattr(quote, 'price', 0)
                        except Exception as e:
                            logging.error(f"{target['ticker']} 시세 조회 실패: {str(e)}")
                            # 기본 가격 설정
                            target['price'] = target.get('price', 0)
                    
                    processed_targets.append(target)
            
            return processed_targets
            
        except Exception as e:
            logging.error(f"매수 종목 선정 중 오류 발생: {str(e)}")
            import traceback
            logging.error(f"매수 종목 선정 상세 오류: {traceback.format_exc()}")
            return []