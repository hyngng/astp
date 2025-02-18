from pykis import PyKis
import yaml

from module.analysts import Analyst
from module.traders import Trader

#region variables
config = None
#endregion variables

def init():
    ''' ASTP의 기본 동작여건을 설정하는 함수 '''
    with open('data/config.yaml', 'r', encoding='utf-8') as file:
        config = yaml.safe_load(file)

    kis = PyKis(
        id                = config["id"],
        account           = config["account"],
        appkey            = # 
        secretkey         = #
        virtual_id        = config["id"],
        virtual_appkey    = config["virtual_app_key"],
        virtual_secretkey = config["virtual_app_secret"],
        keep_token=True,
    )

    macd_analyst = Analyst(kis)

def main():
    init()

if __name__ == "__main__":
    main()