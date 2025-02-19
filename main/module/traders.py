from pykis import KisTradingHours, KisBalance
import datetime

class Trader:
    ''' 주문자: 매수&매도주문의 적절성을 판단 후 주문하는 클래스.
    '''
    def __init__(self, kis):
        self.kis       = kis

        self.watchlist = []
    
    def get_trading_hours(self):
        opening_time = self.kis.trading_hours("US").open_kst
        closing_time = self.kis.trading_hours("US").close_kst
        now          = datetime.datetime.now().time()

        is_open = True

        if closing_time < now < opening_time:
            is_open = False

        return is_open

        print(now)
        print(self.kis.trading_hours("US").open_kst)
        print(self.kis.trading_hours("US").close_kst)

    def get_balance(self):
        account = self.kis.account()
        balance: KisBalance = account.balance()
        print(repr(balance))
    
    def submit_order(ticker):
        # 주문
        # order: KisOrder = hynix.buy(price=194700, qty=1)

        pass
