# 간략한 설명

ASTP는 다음과 같은 구조로 이루어져있음

- main.py
    - analyst.py
        - macd_analyst.py
    - trader.py

TBM_Analyst 클래스 보면 risk_level를 매개변수로 받음. 의미는 다음과 같음.
- 리스크 레벨: 1(보수), 2(중간), 3(공격)