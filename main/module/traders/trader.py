from pykis import KisBalance
import traceback
import logging

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

    # tbm_analyst에도 있음. 개념적으론 안 맞는데데
    def get_balance(self):
        ''' 내 계좌 잔고 확인하는 함수

        returns:
            KisIntegrationBalance: 예수금, 보유종목 등 내 계좌에 대한 정보
        '''
        account = self.kis.account()
        balance: KisBalance = account.balance()
        return balance
    
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
            
            # 최대 종목 수만큼 선택
            buy_targets = recommendations
            
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
        
    def execute_buy_orders(self, recommendations):
        """매수 주문을 실행합니다.
        
        Args:
            recommendations: 매수 추천 종목 리스트
                각 종목은 다음 정보를 포함:
                - ticker: 종목 코드
                - price: 현재가
                - quantity: 주문 수량
                - name: 종목명
                - buy_signals: 매수 신호 정보
                
        Returns:
            List[Dict[str, Any]]: 매수 주문 결과 리스트
        """
        buy_results = []
        
        for recommendation in recommendations:
            try:
                ticker   = recommendation['ticker']
                price    = recommendation['price']
                quantity = recommendation['quantity']
                name     = recommendation.get('name', ticker)
                
                # 매수 주문 실행
                success = self.submit_order(
                    ticker=ticker,
                    order_type="buy",
                    price=price,
                    quantity=quantity
                )
                
                # 주문 결과 저장
                result = {
                    'ticker': ticker,
                    'name': name,
                    'price': price,
                    'quantity': quantity,
                    'total_value': price * quantity,
                    'success': success,
                    'buy_signals': recommendation.get('buy_signals', {})
                }
                
                buy_results.append(result)
                
                # 로깅
                if success:
                    logging.info(
                        f"매수 주문 성공: {name}({ticker}), "
                        f"{quantity:,}주 @ {price:,.0f}원, "
                        f"총액: {price * quantity:,.0f}원"
                    )
                else:
                    logging.error(f"매수 주문 실패: {name}({ticker})")
                    
            except Exception as e:
                logging.error(f"종목 {ticker} 매수 주문 처리 중 오류: {str(e)}")
                continue
                
        return buy_results

    def execute_sell_orders(self, recommendations):
        sell_results = []
        
        for recommendation in recommendations:
            ticker = recommendation['ticker']
            price = recommendation['current_price']
            quantity = recommendation['quantity']

            success = self.submit_order(ticker, price, quantity, order_type="sell")

            result = {
                'ticker': ticker,
                'price': price,
                'quantity': quantity,
                'total_value': price * quantity,
                'success': success,
                'profit_rate': recommendation['profit_rate'],
                'sell_signals': recommendation['sell_signals']
            }

            sell_results.append(result)

            if success:
                logging.info(f"매도 주문 성공: {ticker}, {quantity}주 @ {price:,.0f}원, 총액: {price * quantity:,.0f}원, 손익률: {candidate['profit_rate']:.2f}%")
            else:
                logging.error(f"매도 주문 실패: {ticker}")
        
        logging.error(f"{len(recommendations)}개의 매도 주문을 완료했습니다.")

        return sell_results

    def submit_order(self, ticker, price, quantity, order_type="buy"):
        '''주문 제출 함수 (매수/매도)
        '''
        if not ticker or not price or not quantity:
            logging.error(f"주문 정보 부족: ticker={ticker}, price={price}, quantity={quantity}")
            return False
        
        if quantity <= 0:
            logging.warning(f"주문 수량이 0 이하입니다: {quantity}. 주문을 취소합니다.")
            return False
        
        order_type = order_type.upper()
        
        try:
            # 실제 주문이 아닌 모의 투자 모드인지 확인
            is_virtual = self.config.get("api_info", {}).get("is_virtual", False)
            
            logging.info(f"{'모의' if is_virtual else '실제'} 주문 시도: {ticker} {order_type} {quantity}주 @ {price:,.2f}")

            retry_count = 0
            while retry_count < 4:
                try:
                    stock = self.kis.stock(ticker)
                    
                    if order_type == "BUY":
                        stock.buy(price=price, qty=quantity)
                        logging.info(f"매수 주문 성공: {ticker} {order_type} {quantity}주 @ {price:,.2f}")
                    else:
                        stock.sell(price=price, qty=quantity)
                        logging.info(f"매도 주문 성공: {ticker} {order_type} {quantity}주 @ {price:,.2f}")
                    
                    return True  # 성공 시 함수 종료
                
                except Exception as e:
                    logging.warning(f"매수 또는 매도 주문 호출 실패 (시도 {retry_count + 1}/4): {str(e)}")
                    retry_count += 1
            
            logging.error(f"주문 실패: {ticker} {order_type} {quantity}주 @ {price:,.2f} (최대 재시도 횟수 초과)")
            return False
        
        except Exception as outer_e:
            logging.error(f"{ticker} {order_type} 주문 초기화 중 오류: {str(outer_e)}")
            logging.error(f"주문 오류 상세: {traceback.format_exc()}")
            return False