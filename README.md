# **Auto Stock Trading Program**

If you don't know Korean, **[English support](https://github.com/hyngng/astp/blob/master/README-en.md)** is here.

### **특징**

- 특정한 매매전략을 구현하는 것이 목표로, 전략은 다음과 같습니다.
    - NDX 지수와 NASDAQ 상장 1, 2위 기업의 비율을 고려하여 주식을 매수합니다.
    - NDX 지수가 폭락하거나, 환율이 과도하게 상승하는 등의 상황에서 보유주식을 전량 매도하고 20영업일간 매매활동을 중지합니다.  
- 파이썬과 한국투자증권이 배포하는 Open API를 사용합니다.
- [Yahoo Finance](https://finance.yahoo.com/quote/NQ=F?p=NQ=F&.tsrc=fin-srch) 크롤링을 통해 NDX 지수를 활용합니다.
- _Designed with **PAYANG**_

### **개선 가능한 사항**

- FinanceDataReader 라이브러리 없이 코드가 동작 가능하도록 변경.
- 출력물 앞에 [2022-02-22-22:22:22]와 안내문 출력 시간대 표시
- 안내문 출력 기록 .txt 등 확장자의 파일로 빌드하는 기능 (Y/N)
- 공황 상황에 대응할 수 있는 함수 추가.
- 매수 한도와 매도 조건 추가
- 클래스 작성 및 함수 유형화
- Android Studio를 통한 안드로이드 어플리케이션 빌드

<br>

더 자세한 사항은 **[여기](https://hyngng.github.io/posts/astp/)**에서 확인하실 수 있습니다.
