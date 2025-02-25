from pykis import PyKis
import yaml

from module.analysts import *
from module.traders import *

#region variables
config       = None

trader       = None
macd_analyst = None
#endregion variables

def init():
    ''' ASTP의 기본 동작여건을 설정하는 함수.
    '''
    config = yaml.safe_load(
        open('../data/config.yaml', 'r', encoding='utf-8')
    )

    kis = PyKis(
        id                = config["api_info"]["id"],
        account           = config["api_info"]["account"],
        appkey            = config["api_info"]["app_key"],
        secretkey         = config["api_info"]["app_secret"],
        virtual_id        = config["api_info"]["id"],
        virtual_appkey    = config["api_info"]["virtual_app_key"],
        virtual_secretkey = config["api_info"]["virtual_app_secret"],
        keep_token        = True,
    )

    trader       = Trader(kis)
    macd_analyst = MACD_Analyst(kis)

    # print(trader.get_balance())
    # print(macd_analyst.get_stock_quote("MSFT"))

    # 상위 10개 기업에 대해 MACD 알아내기
    # corps = [상위 10개]
    # for corp in corps:
    #     print(macd_analyst.get_macd(corp)

    macd_analyst.get_nasdaq_100()

def main():
    init()

    # while문 안에 넣을거
    # macd_analyst.generate_recommendations()

    # while True:
        # 잔고조회
        # trader.get_balance()
        # time.sleep(config["system"]["operating_cycle"])

if __name__ == "__main__":
    main()