## **Auto Stock Trading Program**

### **Features**

- The goal is to implement a specific trading strategy, which is as follows:
    - Buy stocks based on the ratio of the NDX index to the top 1st and 2nd companies listed on NASDAQ.
    - Sell all held stocks and stop trading for 20 business days if the NDX index crashes or if there is excessive currency fluctuation.
- Python is used along with the Open API provided by Korea Investment & Securities.
- The NDX index is utilized through [Yahoo Finance](https://finance.yahoo.com/quote/NQ=F?p=NQ=F&.tsrc=fin-srch) crawling.
- _Designed with **PAYANG**._

### **Areas for Improvement**

- Modify the code to work without the FinanceDataReader library.
- Display the timestamp with a format like [2022-02-22-22:22:22] and an information message.
- Implement the ability to build output logs as a .txt or similar file format (Y/N).
- Add a function to handle panic situations.
- Add buy limits and sell conditions.
- Create classes and organize functions.
- Build an Android application using Android Studio.

<br>

- More details can be found **[here](https://hyngng.github.io/posts/astp/)**.