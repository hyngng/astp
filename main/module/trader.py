from pykis import KisBalance
import traceback
import logging
import time

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Trader:
    ''' 주문자: 매수&매도주문의 적절성을 판단 후 주문하는 클래스.
    '''
    def __init__(self, kis, config):
        '''주문자 초기화'''
        self.kis = kis
        self.config = config
        self.watchlist = []
        self.holdings = {}

        self.is_virtual = config.get("api_info", {}).get("is_virtual", False)

        self._optimize_kis_session()

        self.risk_level = config.get("trading_settings", {}).get("risk_level", 2)

        logging.info(f"{'모의투자' if self.is_virtual else '실제투자'} 형식으로 TRADER 초기화 완료")

    def _optimize_kis_session(self):
        '''PyKis 라이브러리 세션 최적화
        '''
        try:
            if hasattr(self.kis, 'session') and self.kis.session:
                session = self.kis.session

                session.keep_alive = True

                if hasattr(session, 'timeout'):
                    session.timeout = 30

                if hasattr(self.kis, 'retry'):
                    self.kis.retry = 3  # 기본 재시도 횟수 설정

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

    def get_balance(self):
        ''' 내 계좌 잔고 확인하는 함수

        returns:
            KisIntegrationBalance: 예수금, 보유종목 등 내 계좌에 대한 정보
        '''
        account = self.kis.account()
        balance: KisBalance = account.balance()
        return repr(balance)
    
    def update_holdings(self):
        '''보유 종목 정보 업데이트'''
        try:
            # 잔고 객체 가져오기
            balance = self.get_balance()
            
            # 보유종목 정보 저장
            self.holdings = {}
            
            # 튜토리얼에 따라 balance.stocks 활용
            for stock in balance.stocks:
                try:
                    # 종목 정보 형식화
                    stock_ticker = getattr(stock, 'symbol', getattr(stock, 'ticker', None))

                    # 종목 정보 저장
                    stock_info = {
                        'ticker': stock_ticker,
                        'quantity': getattr(stock, 'qty', 0),
                        'price': getattr(stock, 'price', 0),
                        'purchase_price': getattr(stock, 'avg_price', getattr(stock, 'purchase_price', 0)),
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
    
    def select_stocks_to_buy(self, recommendations, max_count=3):
        '''
        매수할 종목을 선정하는 함수
        
        Args:
            max_count (int): 최대 매수 종목 수
            
        Returns:
            List[Dict]: 매수 대상 종목 정보 리스트
        '''
        try:
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

    def get_quote(self, ticker: str):
        '''종목 시세 정보를 가져오는 함수
        '''
        try:
            return self.kis.stock(ticker).quote
        except Exception as e:
            logging.error(f"시세 정보 가져오기 실패 ({ticker}): {str(e)}")
            raise

    def auto_trading_cycle(self, buy_targets):
        '''자동 매매 사이클 실행'''
        result = {
            'sell_count': 0,
            'buy_count': 0,
            'errors': []
        }
        
        try:
            # 1. 보유 종목 정보 업데이트
            retry_count = 0
            max_retries = 3
            success = False
            
            while not success and retry_count < max_retries:
                try:
                    success = self.update_holdings()
                except Exception as e:
                    logging.error(f"보유 종목 업데이트 중 예외: {str(e)}")
                logging.info(f"보유 종목을 성공적으로 불러옴")
            
            # 2. 매도 대상 선정 및 처리
            try:
                # API 요청 간격 추가 (초당 요청 제한 대응)
                time.sleep(1)
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
                time.sleep(1)
                
                self.update_holdings()
            except Exception as e:
                logging.warning(f"매도 후 보유 종목 업데이트 실패: {str(e)}")
            
            # 4. 매수 대상 선정 및 처리
            try:
                # API 요청 간격 추가
                time.sleep(1)
                
                # 최대 매수 종목 수 설정값 가져오기
                max_buy_stocks = self._get_max_buy_stocks()
                
                # TBM 전략을 통한 추천 종목 가져오기
                buy_targets = self.select_stocks_to_buy(max_count=max_buy_stocks)
                
                if buy_targets:
                    logging.info(f"매수 대상 종목: {len(buy_targets)}개 (최대 {max_buy_stocks}개)")
                    for ticker in buy_targets:
                        try:
                            # 주문 제출 전 API 요청 간격 추가
                            time.sleep(1)
                            
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