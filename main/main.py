from pykis import PyKis
import logging
import time
from datetime import datetime, timedelta, time as datetime_time

from module.analysts import *
from module.traders import *
from module.securities import load_secure_config

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
    
    # KIS API 초기화
    try:
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
        logging.info("KIS API가 성공적으로 초기화되었습니다.")
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
        return
    
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
            logging.error(f"{ticker} 분석 중 예외 발생: {str(e)}")
    
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
        market_open_time = trader.kis.trading_hours("US").open_kst
        
        # datetime.time 객체에서 1시간을 빼는 연산 오류 수정
        # 날짜와 시간을 포함한 전체 datetime 객체를 생성하고 연산
        today = datetime.now().date()
        full_open_time = datetime.combine(today, market_open_time.time())
        pre_market_time = full_open_time - timedelta(hours=1)
        
        # 현재 시간이 pre_market_time과 market_open_time 사이에 있는지 확인
        current_time = datetime.combine(today, now.time())
        return pre_market_time <= current_time < full_open_time
    except Exception as e:
        logging.error(f"장 시작 시간 확인 중 오류 발생: {str(e)}")
        import traceback
        logging.error(f"상세 오류: {traceback.format_exc()}")
        return False

def execute_trading_cycle(trader, is_pre_market_cycle=False):
    """매매 사이클을 실행하는 함수"""
    try:
        cycle_type = "추가 (장 시작 전)" if is_pre_market_cycle else "정상"
        logging.info(f"{cycle_type} 매매 사이클 실행")
        
        result = trader.auto_trading_cycle()
        
        logging.info(f"{cycle_type} 매매 사이클 결과: 매도 {result['sell_count']}종목, 매수 {result['buy_count']}종목")
        return result
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
        
        # 종목 분석
        analyze_tickers(tickers, analyst)
        
        # 운영 사이클 설정
        operating_cycle = config.get("system", {}).get("operating_cycle", 3600)  # 기본 1시간
        
        logging.info(f"자동 매매 프로그램 시작 (사이클: {operating_cycle}초)")
        
        while True:
            # 미국 장 시작 1시간 전인지 확인
            if is_pre_market(trader):
                execute_trading_cycle(trader, is_pre_market_cycle=True)
            
            # 정상 매매 사이클 실행
            execute_trading_cycle(trader)
            
            # 다음 사이클까지 대기
            logging.info(f"다음 사이클까지 {operating_cycle}초 대기")
            time.sleep(operating_cycle)
            
    except KeyboardInterrupt:
        logging.info("사용자에 의해 프로그램이 종료되었습니다.")
    except Exception as e:
        logging.error(f"프로그램 실행 중 치명적 오류 발생: {str(e)}")
        import traceback
        logging.error(f"상세 오류: {traceback.format_exc()}")
        raise

if __name__ == '__main__':
    main()
