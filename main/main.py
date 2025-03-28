from pykis import PyKis
import logging
import yaml

from module.analysts.tbm_analyst import TBM_Analyst
from module.trader import Trader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

#region variables
tbm_analyst = None
trader      = None

config      = None
#endregion variables

#region functions
def init():
    global tbm_analyst
    global trader
    global config

    # data/config.yaml 불러오기
    try:
        with open('data/config.yaml', 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
        logging.info("설정 파일을 성공적으로 불러옴")
    except Exception as e:
        logging.error(f"설정 파일 로드 중 오류 발생: {str(e)}")
        raise

    # kis 객체 초기화
    try:
        if config["api_info"]["is_virtual"]:
            kis = PyKis(
                id=config["api_info"]["id"],
                account=config["api_info"]["account"],
                appkey=config["api_info"]["app_key"],
                secretkey=config["api_info"]["app_secret"],
                virtual_id=config["api_info"]["id"],
                virtual_appkey=config["api_info"]["virtual_app_key"],
                virtual_secretkey=config["api_info"]["virtual_app_secret"],
                keep_token=True,
            )
        else:
            kis = PyKis(
                id=config["api_info"]["id"],
                account=config["api_info"]["account"],
                appkey=config["api_info"]["app_key"],
                secretkey=config["api_info"]["app_secret"],
                keep_token=True,
            )
        logging.info(f"{'모의투자' if config['api_info']['is_virtual'] else '실제투자'} 형식으로 KIS 객체 초기화 완료")
    except Exception as e:
        logging.error(f"KIS API 초기화 실패: {str(e)}")
        raise

    # 필요한 내부 객체 인스턴스화
    tbm_analyst = TBM_Analyst(kis, config)
    trader      = Trader(kis, config)

def main():
    tickers         = tbm_analyst.get_nasdaq_top_100()
    recommendations = tbm_analyst.generate_recommendations(tickers)
    buy_targets     = trader.select_stocks_to_buy(recommendations)
    trader.auto_trading_cycle(buy_targets)

    # 리스트 받아와서 구입
    pass
#endregion functions

#region main
if __name__ == "__main__":
    init()
    main()
#endregion main