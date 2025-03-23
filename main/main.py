from pykis import PyKis
import yaml
import logging
import time
from datetime import datetime
import os
import sys

from module.analysts import *
from module.traders import *
from main.module.securities import load_secure_config  # 보안 설정 로드 함수 경로 수정
import argparse

#region variables
config           = None

trader           = None
macd_analyst     = None
#endregion variables

def init():
    ''' ASTP의 기본 동작여건을 설정하는 함수.
    '''
    global config, trader, macd_analyst

    # 환경 변수와 설정 파일을 결합하여 보안 설정 로드
    config = load_secure_config('data/config.yaml')

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

    return tickers

def analyze_tickers(tickers):
    '''주어진 종목들에 대해 MACD 분석을 수행하는 함수

    Args:
        tickers (list): 분석할 종목 코드 리스트
    '''
    # 신호 카운트 초기화
    golden_cross_count = 0
    dead_cross_count = 0
    no_signal_count = 0
    error_count = 0
    
    # 신호 목록 초기화
    golden_cross_tickers = []
    dead_cross_tickers = []
    
    # 각 종목 분석
    for ticker in tickers:
        success, result = macd_analyst.get_macd(ticker)
        if success:
            if result['signal'] == 'GOLDEN_CROSS':
                golden_cross_count += 1
                golden_cross_tickers.append(ticker)
                logging.info(f"{ticker}: {result['signal']} 발생 (MACD: {result['macd_value']:.4f}, Signal: {result['signal_value']:.4f})")
            elif result['signal'] == 'DEAD_CROSS':
                dead_cross_count += 1
                dead_cross_tickers.append(ticker)
                logging.info(f"{ticker}: {result['signal']} 발생 (MACD: {result['macd_value']:.4f}, Signal: {result['signal_value']:.4f})")
            else:
                no_signal_count += 1
        else:
            error_count += 1
            logging.error(f"{ticker}: {result['error']}")
    
    # 분석 결과 요약
    logging.info(f"===== MACD 분석 결과 요약 =====")
    logging.info(f"총 분석 종목: {len(tickers)}개")
    
    if golden_cross_count > 0:
        logging.info(f"골든크로스 발생: {golden_cross_count}개 기업 {golden_cross_tickers}")
    
    if dead_cross_count > 0:
        logging.info(f"데드크로스 발생: {dead_cross_count}개 기업 {dead_cross_tickers}")
    
    if no_signal_count > 0:
        logging.info(f"신호 없음: {no_signal_count}개 기업")
    
    if error_count > 0:
        logging.info(f"분석 오류: {error_count}개 기업")
    
    logging.info(f"===============================")

def main():
    logging.info("ASTP 프로그램 시작")
    
    # 초기화
    tickers = init()
    
    while True:
        try:
            # 현재 시간 로깅
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logging.info(f"분석 시작 시간: {current_time}")
            
            # 종목 분석
            analyze_tickers(tickers)
            
            # 자동 매매 실행
            if config.get("trading_settings", {}).get("auto_trading_enabled", False):
                logging.info("자동 매매 기능 실행 중...")
                trading_result = trader.auto_trading_cycle()
                logging.info(f"자동 매매 실행 결과: 매도 {trading_result['sell_count']}건, 매수 {trading_result['buy_count']}건")
            else:
                logging.info("자동 매매 기능이 비활성화되어 있습니다. config.yaml.trading_settings.auto_trading_enabled를 true로 설정하세요.")
            
            # 설정된 주기만큼 대기
            wait_time = config["system"]["operating_cycle"]
            logging.info(f"{wait_time}초 대기 중...")
            time.sleep(wait_time)
            
        except Exception as e:
            logging.error(f"오류 발생: {str(e)}")
            time.sleep(60)  # 오류 발생 시 1분 대기 후 재시도

if __name__ == "__main__":
    main()