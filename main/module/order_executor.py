import logging
from typing import List, Dict, Any
from datetime import datetime

class OrderExecutor:
    def __init__(self, kis):
        self.kis = kis
        self.holdings = {}  # 보유 종목 정보 저장
        self.config = {}    # 설정 정보 저장
        
    def update_holdings(self):
        """보유 종목 정보를 업데이트합니다."""
        try:
            account = self.kis.account()
            balance = account.balance()
            
            if hasattr(balance, 'stocks'):
                for stock in balance.stocks:
                    try:
                        ticker = getattr(stock, 'ticker', 
                                      getattr(stock, 'code', 
                                            getattr(stock, 'symbol', None)))
                        if not ticker:
                            continue
                            
                        self.holdings[ticker] = {
                            'quantity': getattr(stock, 'quantity', 
                                             getattr(stock, 'amount', 
                                                   getattr(stock, 'volume', 0))),
                            'avg_price': getattr(stock, 'avg_price', 
                                              getattr(stock, 'purchase_price', 
                                                    getattr(stock, 'price', 0))),
                            'buy_date': getattr(stock, 'buy_date', 
                                             datetime.now().strftime("%Y-%m-%d"))
                        }
                    except Exception as e:
                        logging.error(f"종목 {ticker} 정보 업데이트 중 오류: {str(e)}")
                        continue
                        
        except Exception as e:
            logging.error(f"보유 종목 정보 업데이트 중 오류: {str(e)}")
            
    def get_sell_recommendations(self) -> List[Dict[str, Any]]:
        """모든 보유 종목에 대한 매도 추천을 생성합니다.
        
        Returns:
            List[Dict[str, Any]]: 매도 추천 종목 리스트
        """
        try:
            # 보유 종목 정보 업데이트
            self.update_holdings()
            
            sell_recommendations = []
            
            for ticker, holding_info in self.holdings.items():
                try:
                    # 1. 현재 시장 가격 확인
                    quote = self.kis.quote(ticker)
                    current_price = quote.price
                    
                    # 2. 손익률 계산
                    avg_price = holding_info['avg_price']
                    if not avg_price:
                        continue
                        
                    profit_rate = (current_price - avg_price) / avg_price * 100
                    
                    # 3. 매도 신호 목록
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
                        
                    # 홀딩 기간 초과
                    max_holding_days = settings.get("max_holding_days", 30)
                    buy_date_str = holding_info['buy_date']
                    
                    try:
                        buy_date = datetime.strptime(buy_date_str, "%Y-%m-%d")
                        days_held = (datetime.now() - buy_date).days
                        if days_held > max_holding_days:
                            sell_signals.append(f"홀딩 기간 초과 ({days_held}일)")
                    except (ValueError, TypeError):
                        pass
                        
                    # 매도 신호가 있는 경우만 추가
                    if sell_signals:
                        sell_recommendations.append({
                            'ticker': ticker,
                            'name': getattr(quote, 'name', ticker),
                            'current_price': current_price,
                            'avg_price': avg_price,
                            'profit_rate': profit_rate,
                            'quantity': holding_info['quantity'],
                            'sell_signals': sell_signals,
                            'total_value': holding_info['quantity'] * current_price
                        })
                        
                except Exception as e:
                    logging.error(f"종목 {ticker} 매도 추천 생성 중 오류: {str(e)}")
                    continue
                    
            return sell_recommendations
            
        except Exception as e:
            logging.error(f"매도 추천 생성 중 오류: {str(e)}")
            return []
            
    def execute_buy_orders(self, recommendations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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
                ticker = recommendation['ticker']
                price = recommendation['price']
                quantity = recommendation['quantity']
                name = recommendation.get('name', ticker)
                
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
        
    def submit_order(self, ticker: str, order_type: str, price: float, quantity: int) -> bool:
        """주문을 제출합니다.
        
        Args:
            ticker: 종목 코드
            order_type: 주문 유형 ("buy" 또는 "sell")
            price: 주문 가격
            quantity: 주문 수량
            
        Returns:
            bool: 주문 성공 여부
        """
        try:
            # 계좌 객체로 주문 실행
            account = self.kis.account()
            
            if order_type == "buy":
                # 매수 주문
                order_result = account.buy(ticker, price, quantity)
            else:
                # 매도 주문
                order_result = account.sell(ticker, price, quantity)
                
            # 주문 결과 확인
            if order_result and order_result.get('order_id'):
                return True
                
            return False
            
        except Exception as e:
            logging.error(f"주문 제출 중 오류: {str(e)}")
            return False 