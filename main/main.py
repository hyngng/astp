from pykis import PyKis, KisBalance
import yaml

from module.analysts import Analyst
from module.traders import Trader

#region variables
config  = None
account = None
#endregion variables

def init():
    ''' ASTP의 기본 동작여건을 설정하는 함수
    '''
    config = yaml.safe_load(
        open('../data/config.yaml', 'r', encoding='utf-8')
    )

    kis = PyKis(
        id                = config["info"]["id"],
        account           = config["info"]["account"],
        appkey            = config["info"]["app_key"],
        secretkey         = config["info"]["app_secret"],
        virtual_id        = config["info"]["id"],
        virtual_appkey    = config["info"]["virtual_app_key"],
        virtual_secretkey = config["info"]["virtual_app_secret"],
        keep_token        = True,
    )

    macd_analyst = Analyst(kis)
    trader       = Trader(kis)

    print(macd_analyst.get_stock_quote("MSFT"))
    trader.get_balance(kis)

def main():
    init()

    # for i in range():
        # 잔고조회
        # account = kis.account()
        # balance: KisBalance = account.balance()
        # print(repr(balance))

if __name__ == "__main__":
    main()