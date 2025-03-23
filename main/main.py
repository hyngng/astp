from pykis import PyKis
import yaml
import logging

from module.analysts import *
from module.traders import *

#region variables
config           = None

trader           = None
macd_analyst     = None
#endregion variables

def init():
    ''' ASTP의 기본 동작여건을 설정하는 함수.
    '''
    global config, trader, macd_analyst

    config = yaml.safe_load(
        open('data/config.yaml', 'r', encoding='utf-8')
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

    trader       = Trader(kis, config)
    macd_analyst = MACD_Analyst(kis, config)

    # 종목 목록 가져오기
    tickers = []
    if config["companies_settings"]["auto_fetch"]:
        logging.info("나스닥 100 기업 목록을 자동으로 가져오는 중...")
        tickers = Analyst.get_nasdaq_top_100()
    else:
        tickers = config["companies_settings"]["manual_tickers"]

    # MACD 분석 실행
    for ticker in tickers:
        success, result = macd_analyst.get_macd(ticker)
        if success:
            if result['signal'] != 'NO_SIGNAL':
                logging.info(f"{ticker}: {result['signal']} 발생 (MACD: {result['macd_value']:.4f}, Signal: {result['signal_value']:.4f})")
        else:
            logging.error(f"{ticker}: {result['error']}")

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