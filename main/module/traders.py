from pykis import KisBalance

class Trader:
    ''' 주문자: 매수&매도주문의 적절성을 판단 후 주문하는 클래스
    '''
    def __init__(self, kis):
        self.kis       = kis

        self.watchlist = []
    
    def get_balance(self, kis):
        account = self.kis.account()
        balance: KisBalance = account.balance()
        print(repr(balance))