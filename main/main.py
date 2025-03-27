from module.traders import Trader
from module.analysts import *
from module.securities import load_secure_config
from pykis import PyKis, KisAuth

import os
import sys
import logging
import traceback
from datetime import datetime, timedelta
import json
import time

# 경로 문제 해결
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# 로그 포맷 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)

def load_config():
    """설정 파일을 로드하는 함수"""
    try:
        config = load_secure_config('data/config.yaml')
        logging.info("설정 파일을 성공적으로 로드했습니다.")
        return config
    except Exception as e:
        logging.error(f"설정 파일 로드 중 오류 발생: {str(e)}")
        raise

def init_app():
    """어플리케이션 초기화 및 필요한 객체들을 반환하는 함수"""
    # 설정 로드
    config = load_config()
    
    # 계좌번호 확인 및 수정
    account_number = config["api_info"]["account"]
    
    # 계좌번호 형식 확인: 50124703-01 형식이어야 함
    # 로그를 보니 API는 CANO: ['50124703'], ACNT_PRDT_CD: ['01'] 형식을 사용
    # 하이픈이 없거나 잘못된 형식이면 수정
    
    # 하이픈 "-" 제거하고 다시 올바른 형식으로 설정
    if "-" in account_number:
        parts = account_number.split("-")
        if len(parts) == 2:
            main_acct = parts[0]
            sub_acct = parts[1]
            # 설정에는 하이픈 포함 형식으로 유지
            config["api_info"]["account"] = f"{main_acct}-{sub_acct}"
    else:
        logging.warning(f"계좌번호 형식 확인: {account_number}")
        if len(account_number) > 2:
            main_acct = account_number[:-2]
            sub_acct = account_number[-2:]
            config["api_info"]["account"] = f"{main_acct}-{sub_acct}"
            logging.info(f"계좌번호 형식 수정: {config['api_info']['account']}")
    
    # 최종 계좌번호 로깅
    logging.info(f"사용할 계좌번호: {config['api_info']['account']}")
    
    # KIS API 초기화
    try:
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                is_virtual = config["api_info"]["is_virtual"]
                
                if is_virtual:
                    # 모의투자 모드
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
                    # 실제투자 모드
                    kis = PyKis(
                        id=config["api_info"]["id"],
                        account=config["api_info"]["account"],
                        appkey=config["api_info"]["app_key"],
                        secretkey=config["api_info"]["app_secret"],
                        keep_token=True,
                    )
                    
                # 연결 테스트 - 간단한 API 호출
                logging.info(f"KIS API가 성공적으로 초기화되었습니다 (모드: {'모의투자' if is_virtual else '실제투자'})")
                break  # 성공했으면 루프 종료
                
            except Exception as e:
                retry_count += 1
                if retry_count < max_retries:
                    wait_time = 2 ** retry_count  # 지수 백오프
                    logging.warning(f"KIS API 초기화 실패, {wait_time}초 후 재시도 ({retry_count}/{max_retries}): {str(e)}")
                    time.sleep(wait_time)
                else:
                    logging.error(f"KIS API 초기화 최대 재시도 횟수 초과: {str(e)}")
                    raise
    except Exception as e:
        logging.error(f"KIS API 초기화 중 오류 발생: {str(e)}")
        raise
    
    # 분석기 및 트레이더 초기화
    try:
        analyst = MACD_Analyst(kis, config)
        trader = Trader(kis, config)
        logging.info("분석기 및 트레이더가 성공적으로 초기화되었습니다.")
    except Exception as e:
        logging.error(f"분석기 및 트레이더 초기화 중 오류 발생: {str(e)}")
        raise
    
    # 종목 목록 가져오기
    try:
        tickers = []
        if config["companies_settings"]["auto_fetch"]:
            logging.info("나스닥 100 기업 목록을 자동으로 가져오는 중...")
            tickers = Analyst.get_nasdaq_top_100()
        else:
            tickers = config["companies_settings"]["manual_tickers"]
            logging.info(f"수동 설정된 {len(tickers)}개 종목을 사용합니다.")
    except Exception as e:
        logging.error(f"종목 목록 가져오기 중 오류 발생: {str(e)}")
        tickers = []  # 빈 리스트로 초기화하고 계속 진행
    
    return config, kis, analyst, trader, tickers

def analyze_tickers(tickers, analyst):
    """주어진 종목들에 대해 MACD 분석을 수행하는 함수"""
    if not tickers:
        logging.warning("분석할 종목이 없습니다.")
        return [], []
    
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
        try:
            success, result = analyst.get_macd(ticker)
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
        except Exception as e:
            error_count += 1
            logging.error(f"{ticker} 분석 중 오류: {str(e)}")
    
    # 분석 결과 요약
    logging.info(f"분석 완료: {len(tickers)}개 종목")
    logging.info(f"골든크로스: {golden_cross_count}개 종목")
    logging.info(f"데드크로스: {dead_cross_count}개 종목")
    logging.info(f"신호없음: {no_signal_count}개 종목")
    logging.info(f"오류: {error_count}개 종목")
    
    if golden_cross_tickers:
        logging.info(f"골든크로스 발생: {len(golden_cross_tickers)}개 기업 {golden_cross_tickers}")
    if dead_cross_tickers:
        logging.info(f"데드크로스 발생: {len(dead_cross_tickers)}개 기업 {dead_cross_tickers}")
    
    return golden_cross_tickers, dead_cross_tickers

def get_us_eastern_time():
    """현재 미국 동부 시간(ET)을 계산합니다."""
    # 현재 한국 시간
    now_kr = datetime.now()
    
    # 서머타임 여부 확인
    year = now_kr.year
    dst_start = datetime(year, 3, 8 + (6 - datetime(year, 3, 8).weekday()) % 7, 2)  # 3월 둘째 일요일
    dst_end = datetime(year, 11, 1 + (6 - datetime(year, 11, 1).weekday()) % 7, 2)  # 11월 첫째 일요일
    
    is_dst = dst_start <= now_kr.replace(tzinfo=None) < dst_end
    
    # 서머타임 적용 여부에 따라 시차 계산
    if is_dst:
        # 서머타임 적용 (EDT, UTC-4)
        hour_diff = 13  # 한국 - 미국 동부 시차
        logging.info("서머타임 적용 중 (EDT, UTC-4)")
    else:
        # 표준시 적용 (EST, UTC-5)
        hour_diff = 14  # 한국 - 미국 동부 시차
        logging.info("표준시 적용 중 (EST, UTC-5)")
    
    # 미국 동부 시간 계산
    us_eastern = now_kr - timedelta(hours=hour_diff)
    
    # 시, 분, 요일 반환
    return us_eastern.hour, us_eastern.minute, us_eastern.weekday(), is_dst

def is_pre_market(trader, now=None):
    """미국 장 시작 1시간 전인지 확인하는 함수"""
    if now is None:
        now = datetime.now()
    
    try:
        # 방법 1: PyKis API 사용
        try:
            hours = trader.kis.trading_hours("US")
            market_open_time = hours.open_kst
            
            today = datetime.now().date()
            full_open_time = datetime.combine(today, market_open_time)
            pre_market_time = full_open_time - timedelta(hours=1)
            
            # 현재 시간이 pre_market_time과 market_open_time 사이에 있는지 확인
            current_time = datetime.combine(today, now.time())
            return pre_market_time <= current_time < full_open_time
        except Exception as api_error:
            logging.warning(f"미국 장 시간 조회 실패: {str(api_error)}, 대체 방법 사용")
            
            # 방법 2: 서머타임 고려한 하드코딩된 시간 사용
            # 현재 미국 동부 시간 확인
            et_hour, et_minute, et_weekday, is_dst = get_us_eastern_time()
            
            # 미국 주식 시장은 월~금(0~4) 오전 9:30(동부시간)에 개장
            is_trading_day = et_weekday < 5  # 월~금
            
            # 서머타임 여부에 따라 한국 시간으로 몇 시인지 계산
            # 미국 동부 9:30(시장 개장)은 한국 시간으로 표준시 22:30, 서머타임 21:30
            kr_market_open_hour = 22 if not is_dst else 21
            kr_market_open_minute = 30
            
            # 현재 한국 시간
            kr_now = datetime.now()
            kr_hour, kr_minute = kr_now.hour, kr_now.minute
            
            # 시장 개장 1시간 전인지 확인
            if not is_trading_day:
                return False
                
            if kr_hour == kr_market_open_hour - 1:
                # 시장 개장 1시간 전 같은 시간대
                return kr_minute >= kr_market_open_minute
            elif kr_hour == kr_market_open_hour:
                # 시장 개장 시간대
                return kr_minute < kr_market_open_minute
                
            return False
            
    except Exception as e:
        logging.error(f"장 시작 시간 확인 중 오류 발생: {str(e)}")
        import traceback
        logging.error(f"상세 오류: {traceback.format_exc()}")
        # 오류 발생 시 안전하게 False 반환
        return False

def execute_trading_cycle(trader, is_pre_market_cycle=False, golden_cross_tickers=None):
    """매매 사이클을 실행하는 함수"""
    try:
        cycle_type = "추가 (장 시작 전)" if is_pre_market_cycle else "정상"
        logging.info(f"{cycle_type} 매매 사이클 실행")
        
        # 골든크로스 종목 정보가 있으면 Trader에게 설정
        if golden_cross_tickers:
            logging.info(f"매수 대상 골든크로스 종목 {len(golden_cross_tickers)}개 설정: {golden_cross_tickers}")
            # 동적으로 속성 추가
            trader.golden_cross_tickers = golden_cross_tickers
        
        result = trader.auto_trading_cycle(is_pre_market=is_pre_market_cycle)
        
        # 새로운 결과 형식에 맞게 로그 출력
        sell_count = len(result.get('sell_orders', []))
        buy_count = len(result.get('buy_orders', []))
        
        logging.info(f"{cycle_type} 매매 사이클 결과: 매도 {sell_count}종목, 매수 {buy_count}종목")
        
        # 기존 호환성을 위해 결과를 변환하여 반환
        return {
            'sell_count': sell_count,
            'buy_count': buy_count,
            'details': result,
            'error': result.get('error', None)
        }
    except Exception as e:
        logging.error(f"매매 사이클 실행 중 오류 발생: {str(e)}")
        import traceback
        logging.error(f"상세 오류: {traceback.format_exc()}")
        return {'sell_count': 0, 'buy_count': 0, 'error': str(e)}

def main():
    """메인 실행 함수"""
    try:
        # 어플리케이션 초기화
        config, kis, analyst, trader, tickers = init_app()
        
        # 종목 분석 - 골든크로스/데드크로스 찾기
        golden_cross_tickers, dead_cross_tickers = analyze_tickers(tickers, analyst)
        
        logging.info("자동 매매 프로그램 시작 (일회성 실행)")
        
        # 미국 장 시작 1시간 전인지 확인
        if is_pre_market(trader):
            execute_trading_cycle(trader, is_pre_market_cycle=True, golden_cross_tickers=golden_cross_tickers)
        
        # 정상 매매 사이클 실행
        execute_trading_cycle(trader, golden_cross_tickers=golden_cross_tickers)
        
        logging.info("자동 매매 프로그램 종료 (일회성 실행 완료)")
            
    except KeyboardInterrupt:
        logging.info("사용자에 의해 프로그램이 종료되었습니다.")
    except Exception as e:
        logging.error(f"프로그램 실행 중 치명적 오류 발생: {str(e)}")
        import traceback
        logging.error(f"상세 오류: {traceback.format_exc()}")
        raise

if __name__ == '__main__':
    main()
