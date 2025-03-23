from pykis import KisTradingHours, KisBalance
import datetime

class Trader:
    ''' 주문자: 매수&매도주문의 적절성을 판단 후 주문하는 클래스.
    '''
    def __init__(self, kis, config):
        self.kis       = kis
        self.config    = config

        self.watchlist = []
    
    def get_trading_hours(self):
        ''' 현재 미국 장이 열려있는지 확인하는 함수.

        returns:
            bool: 미국 장이 열려있는지.
        '''
        opening_time = self.kis.trading_hours("US").open_kst
        closing_time = self.kis.trading_hours("US").close_kst
        now          = datetime.datetime.now().time()

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
    
    def submit_order(ticker):
        # 주문
        # order = hynix.buy(price=194700, qty=1)

        pass
