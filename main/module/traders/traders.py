    def _get_buy_candidates(self, buy_targets):
        """매수 대상 종목 선정
        
        Args:
            buy_targets: 매수 대상 종목 리스트
            
        Returns:
            list: 매수 대상 종목 리스트
        """
        try:
            # 매수 대상이 없으면 빈 리스트 반환
            if not buy_targets:
                logging.info("매수 대상 종목이 없습니다.")
                return []
                
            # 매수 대상 종목 정보 조회
            buy_candidates = []
            for ticker in buy_targets:
                try:
                    quote = self.api_call_with_retry(lambda: self.kis.quote(ticker))
                    if quote and quote.price > 0:
                        buy_candidates.append({
                            'ticker': ticker,
                            'price': quote.price,
                            'name': getattr(quote, 'name', ticker)
                        })
                except Exception as e:
                    logging.error(f"종목 {ticker} 정보 조회 중 오류: {str(e)}")
                    continue
                    
            return buy_candidates
            
        except Exception as e:
            logging.error(f"매수 대상 선정 중 오류: {str(e)}")
            logging.error(traceback.format_exc())
            return []

    def _execute_buy_orders(self, buy_candidates):
        """매수 주문 실행
        
        Args:
            buy_candidates: 매수 대상 종목 리스트
            
        Returns:
            list: 매수 주문 결과 리스트
        """
        try:
            buy_results = []
            for candidate in buy_candidates:
                try:
                    # 주문 수량 계산
                    quantity = self.calculate_order_quantity(candidate['price'])
                    if quantity <= 0:
                        continue
                        
                    # 매수 주문 실행
                    order_result = self.submit_order(
                        ticker=candidate['ticker'],
                        order_type='buy',
                        price=candidate['price'],
                        quantity=quantity
                    )
                    
                    if order_result:
                        buy_results.append({
                            'ticker': candidate['ticker'],
                            'name': candidate['name'],
                            'quantity': quantity,
                            'price': candidate['price'],
                            'order_id': order_result.get('order_id')
                        })
                        
                except Exception as e:
                    logging.error(f"종목 {candidate['ticker']} 매수 주문 중 오류: {str(e)}")
                    continue
                    
            return buy_results
            
        except Exception as e:
            logging.error(f"매수 주문 실행 중 오류: {str(e)}")
            logging.error(traceback.format_exc())
            return []

    def _update_holdings(self):
        """보유 종목 정보 업데이트
        
        Returns:
            list: 보유 종목 리스트
        """
        try:
            # 계좌 객체로 보유 종목 조회
            account = self.kis.account()
            balance = self.api_call_with_retry(lambda: account.balance())
            
            # 튜토리얼에 따라 stocks에서 보유 종목 정보 가져오기
            holdings = []
            if hasattr(balance, 'stocks'):
                for stock in balance.stocks:
                    try:
                        # 종목 코드 가져오기 (여러 속성 시도)
                        ticker = getattr(stock, 'ticker', 
                                      getattr(stock, 'code', 
                                            getattr(stock, 'symbol', None)))
                        if not ticker:
                            continue
                            
                        # 현재가 조회
                        quote = self.api_call_with_retry(lambda: self.kis.quote(ticker))
                        if not quote or quote.price <= 0:
                            continue
                            
                        # 보유 수량 가져오기 (여러 속성 시도)
                        quantity = getattr(stock, 'quantity', 
                                        getattr(stock, 'amount', 
                                              getattr(stock, 'volume', 0)))
                        if quantity <= 0:
                            continue
                            
                        # 평균 매수가 가져오기 (여러 속성 시도)
                        avg_price = getattr(stock, 'avg_price', 
                                         getattr(stock, 'purchase_price', 
                                               getattr(stock, 'price', 0)))
                        
                        holdings.append({
                            'ticker': ticker,
                            'name': getattr(quote, 'name', ticker),
                            'quantity': quantity,
                            'avg_price': avg_price,
                            'current_price': quote.price,
                            'profit_loss': (quote.price - avg_price) * quantity
                        })
                        
                    except Exception as e:
                        logging.error(f"종목 {ticker} 정보 처리 중 오류: {str(e)}")
                        continue
                        
            return holdings
            
        except Exception as e:
            logging.error(f"보유 종목 정보 업데이트 중 오류: {str(e)}")
            logging.error(traceback.format_exc())
            return []

    def _get_sell_candidates(self, holdings):
        """매도 대상 종목 선정
        
        Args:
            holdings: 보유 종목 리스트
            
        Returns:
            list: 매도 대상 종목 리스트
        """
        try:
            sell_candidates = []
            for holding in holdings:
                try:
                    # 현재가 조회
                    quote = self.api_call_with_retry(lambda: self.kis.quote(holding['ticker']))
                    if not quote or quote.price <= 0:
                        continue
                        
                    # 수익률 계산
                    profit_rate = (quote.price - holding['avg_price']) / holding['avg_price'] * 100
                    
                    # 매도 조건 확인
                    if profit_rate >= self.sell_threshold:
                        sell_candidates.append({
                            'ticker': holding['ticker'],
                            'name': holding['name'],
                            'quantity': holding['quantity'],
                            'price': quote.price,
                            'profit_rate': profit_rate
                        })
                        
                except Exception as e:
                    logging.error(f"종목 {holding['ticker']} 매도 대상 선정 중 오류: {str(e)}")
                    continue
                    
            return sell_candidates
            
        except Exception as e:
            logging.error(f"매도 대상 선정 중 오류: {str(e)}")
            logging.error(traceback.format_exc())
            return []

    def _execute_sell_orders(self, sell_candidates):
        """매도 주문 실행
        
        Args:
            sell_candidates: 매도 대상 종목 리스트
            
        Returns:
            list: 매도 주문 결과 리스트
        """
        try:
            sell_results = []
            for candidate in sell_candidates:
                try:
                    # 매도 주문 실행
                    order_result = self.submit_order(
                        ticker=candidate['ticker'],
                        order_type='sell',
                        price=candidate['price'],
                        quantity=candidate['quantity']
                    )
                    
                    if order_result:
                        sell_results.append({
                            'ticker': candidate['ticker'],
                            'name': candidate['name'],
                            'quantity': candidate['quantity'],
                            'price': candidate['price'],
                            'profit_rate': candidate['profit_rate'],
                            'order_id': order_result.get('order_id')
                        })
                        
                except Exception as e:
                    logging.error(f"종목 {candidate['ticker']} 매도 주문 중 오류: {str(e)}")
                    continue
                    
            return sell_results
            
        except Exception as e:
            logging.error(f"매도 주문 실행 중 오류: {str(e)}")
            logging.error(traceback.format_exc())
            return []

    def auto_trading_cycle(self, buy_targets):
        """자동 매매 사이클 실행
        
        Args:
            buy_targets: 매수 대상 종목 리스트
            
        Returns:
            dict: 매매 결과 요약
        """
        try:
            # 1. 매수 대상 종목 선정
            buy_candidates = self._get_buy_candidates(buy_targets)
            if not buy_candidates:
                logging.info("매수 대상 종목이 없습니다.")
                return {'status': 'no_buy_candidates'}
                
            # 2. 매수 주문 실행
            buy_results = self._execute_buy_orders(buy_candidates)
            
            # 3. 보유 종목 정보 업데이트
            holdings = self._update_holdings()
            
            # 4. 매도 대상 종목 선정
            sell_candidates = self._get_sell_candidates(holdings)
            
            # 5. 매도 주문 실행
            sell_results = self._execute_sell_orders(sell_candidates)
            
            # 결과 요약
            return {
                'status': 'success',
                'buy_results': buy_results,
                'sell_results': sell_results,
                'holdings': holdings
            }
            
        except Exception as e:
            logging.error(f"자동 매매 사이클 실행 중 오류: {str(e)}")
            logging.error(traceback.format_exc())
            return {'status': 'error', 'error': str(e)} 