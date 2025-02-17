from pykis import KisAuth
import yaml

from module.analyst import Analyst
from module.leader import Leader

#region variables
config = None
#endregion variables

def init():
    ''' ASTP의 기본 동작여건을 설정하는 함수 '''
    macd_analyst = Analyst()

    with open('data/config.yaml', 'r', encoding='utf-8') as file:
        config = yaml.safe_load(file)

    auth = KisAuth(
        id=config["id"],
        appkey=config["app_key"],
        secretkey=config["app_secret"],
        account=config["account"],
        virtual=True,
    )

    auth.save("secret.json")

def main():
    init()

if __name__ == "__main__":
    main()