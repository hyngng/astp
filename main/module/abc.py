    def update_holdings(self):
        """보유 종목 정보 업데이트
        """
        try:
            # 새로운 보유 종목 정보 딕셔너리
            updated_holdings = {}
            
            # 계좌 객체 생성
            account = self.kis.account()
            
            # 1. PyKis 튜토리얼 방식 - 계좌 잔고 조회
            try:
                # balance.stocks에서 보유 종목 정보 확인
                balance = account.balance()
                
                # 디버깅: 잔고 정보 구조 확인
                logging.info(f"잔고 정보 타입: {type(balance)}")
                logging.info(f"잔고 정보 속성: {dir(balance)}")
                
                # stocks 속성이 있는 경우
                if hasattr(balance, 'stocks'):
                    for stock in balance.stocks:
                        try:
                            # 종목 코드 확인
                            ticker = getattr(stock, 'ticker', 
                                         getattr(stock, 'symbol', 
                                               getattr(stock, 'code', None)))
                            
                            if not ticker:
                                continue
                            
                            # 디버깅: 개별 종목 정보 구조 확인
                            logging.info(f"종목 {ticker} 정보 타입: {type(stock)}")
                            logging.info(f"종목 {ticker} 정보 속성: {dir(stock)}")
                            
                            # 평균 매수가 - 여러 가능한 속성명 시도
                            avg_price = getattr(stock, 'avg_price', 
                                             getattr(stock, 'purchase_price', 
                                                   getattr(stock, 'book_price', 0)))
                            
                            # 보유 수량 - 여러 가능한 속성명 시도
                            quantity = getattr(stock, 'quantity', 
                                            getattr(stock, 'amount', 
                                                  getattr(stock, 'volume', 0)))
                            
                            # 매수일 - 여러 가능한 속성명 시도
                            buy_date = getattr(stock, 'buy_date', 
                                            getattr(stock, 'purchase_date', 
                                                  datetime.now().strftime("%Y-%m-%d")))
                            
                            # 정보 저장
                            updated_holdings[ticker] = {
                                'ticker': ticker,
                                'avg_price': avg_price,
                                'quantity': quantity,
                                'buy_date': buy_date if isinstance(buy_date, str) else buy_date.strftime("%Y-%m-%d")
                            }
                            
                            logging.info(f"종목 {ticker} 정보 업데이트 성공: 평균가 {avg_price}, 수량 {quantity}")
                            
                        except Exception as e:
                            logging.error(f"종목 {ticker} 정보 처리 중 오류: {str(e)}")
                            continue
                
                # 2. PyKis 튜토리얼 방식 - 보유 종목 상세 정보 조회
                if not updated_holdings:
                    # balance에서 확인 실패한 경우 상세 보유종목 조회
                    try:
                        holdings_detail = account.holdings()
                        
                        # 디버깅: holdings 정보 구조 확인
                        logging.info(f"holdings 타입: {type(holdings_detail)}")
                        logging.info(f"holdings 내용: {holdings_detail}")
                        
                        # 리스트 형태인 경우
                        if isinstance(holdings_detail, list):
                            for holding in holdings_detail:
                                # 종목 코드 확인
                                ticker = holding.get('ticker', holding.get('symbol', holding.get('code')))
                                
                                if not ticker:
                                    continue
                                    
                                # 정보 저장
                                updated_holdings[ticker] = {
                                    'ticker': ticker,
                                    'avg_price': holding.get('avg_price', holding.get('purchase_price', 0)),
                                    'quantity': holding.get('quantity', holding.get('amount', 0)),
                                    'buy_date': holding.get('buy_date', datetime.now().strftime("%Y-%m-%d"))
                                }
                        
                        # 딕셔너리 형태인 경우
                        elif isinstance(holdings_detail, dict):
                            for ticker, holding in holdings_detail.items():
                                # 정보 저장
                                updated_holdings[ticker] = {
                                    'ticker': ticker,
                                    'avg_price': holding.get('avg_price', holding.get('purchase_price', 0)),
                                    'quantity': holding.get('quantity', holding.get('amount', 0)),
                                    'buy_date': holding.get('buy_date', datetime.now().strftime("%Y-%m-%d"))
                                }
                        
                    except Exception as e:
                        logging.error(f"보유 종목 상세 정보 조회 중 오류: {str(e)}")
            
            except Exception as e:
                logging.error(f"계좌 잔고 조회 중 오류: {str(e)}")
            
            # 업데이트된 정보 저장
            self.holdings = updated_holdings
            logging.info(f"보유종목 업데이트 완료: {len(self.holdings)}개 종목")
            
            return self.holdings
            
        except Exception as e:
            logging.error(f"보유 종목 정보 업데이트 중 오류: {str(e)}")
            logging.error(traceback.format_exc())
            return {} 