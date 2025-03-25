from pykis import PyKis
import logging
import time as time_module  # time 모듈 이름 변경
from datetime import datetime, timedelta, time as datetime_time  # time 클래스 이름 변경
import time

from module.analysts import *
from module.traders import *
from module.securities import load_secure_config

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

def is_us_market_open(kis):
    """미국 주식 시장 개장 여부를 확인합니다.
    
    Args:
        kis: PyKis 클라이언트 객체
        
    Returns:
        bool: 시장이 열려있으면 True, 아니면 False
    """
    try:
        # 대표 종목(애플)을 사용하여 시장 상태 확인
        stock = kis.stock('AAPL')
        quote = stock.quote()
        
        # 로그에 필요한 정보만 출력 (전체 정보는 너무 과하므로)
        props = {
            'market': getattr(quote, 'market', None),
            'volume': getattr(quote, 'volume', 0),
            'halt': getattr(quote, 'halt', True),
            'extended': getattr(quote, 'extended', False),
            'price': getattr(quote, 'price', None),
            'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        logging.info(f"AAPL 시장 상태 정보: {props}")
        
        # 거래 중단 여부 확인
        if getattr(quote, 'halt', True):
            logging.info("거래 중단 상태입니다.")
            return False
            
        # 거래량 확인 (거래량이 0이면 장이 열려있지 않을 가능성이 높음)
        if getattr(quote, 'volume', 0) <= 0:
            logging.info("거래량이 0입니다. 장이 열려있지 않을 가능성이 높습니다.")
            return False
        
        # 나스닥 시장은 보통 9:30 AM - 4:00 PM ET에 개장
        # 시간대 확인 (간단하게 미국 동부 시간으로 변환)
        et_hour, et_minute, et_weekday = get_us_eastern_time()
        
        # 주말 확인
        if et_weekday >= 5:  # 토,일
            logging.info(f"현재 미국 동부 시간대 기준 주말입니다 (요일: {et_weekday+1}).")
            return False
            
        # 시간 확인 (9:30 AM - 4:00 PM)
        is_market_hours = (
            (et_hour > 9 or (et_hour == 9 and et_minute >= 30)) and
            et_hour < 16
        )
        
        if not is_market_hours:
            logging.info(f"현재 미국 동부 시간대 기준 정규장 시간이 아닙니다 (현재: {et_hour:02d}:{et_minute:02d}).")
            return False
            
        logging.info("모든 조건으로 확인 결과, 미국 주식 시장은 현재 개장 중으로 판단됩니다.")
        return True
        
    except Exception as e:
        logging.error(f"미국 장 개장 여부 확인 실패: {str(e)}")
        # 안전을 위해 예외 발생 시 False 반환
        return False

def get_us_eastern_time():
    """현재 미국 동부 시간(ET)을 계산합니다.
    
    Returns:
        tuple: (시, 분, 요일)
    """
    # 현재 한국 시간
    now_kr = datetime.now()
    
    # 한국과 미국 동부의 시차 (한국 UTC+9, 미국 동부 UTC-4/-5)
    # 서머타임 여부에 따라 시차가 다름
    # 간단한 서머타임 확인 (3월 둘째 일요일 ~ 11월 첫째 일요일)
    year = now_kr.year
    dst_start = datetime(year, 3, 8 + (6 - datetime(year, 3, 8).weekday()) % 7, 2)  # 3월 둘째 일요일
    dst_end = datetime(year, 11, 1 + (6 - datetime(year, 11, 1).weekday()) % 7, 2)  # 11월 첫째 일요일
    
    # 서머타임 적용 여부에 따라 시차 계산
    if dst_start <= now_kr.replace(tzinfo=None) < dst_end:
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
    return us_eastern.hour, us_eastern.minute, us_eastern.weekday()

def calculate_time_to_market_open():
    """다음 미국 장 개장 시간까지 남은 시간(초)을 계산합니다.
    
    Returns:
        float: 다음 개장까지 남은 시간(초), 이미 개장 중이면 0 반환
    """
    # 미국 동부 시간 정보 가져오기
    et_hour, et_minute, weekday = get_us_eastern_time()
    
    # 현재 동부 시간 객체 생성
    now_kr = datetime.now()
    hour_diff = 13 if is_dst() else 14  # 서머타임 여부에 따른 시차
    now_et = now_kr - timedelta(hours=hour_diff)
    
    # 오늘 개장 시간 (9:30 AM ET)
    market_open_time = datetime_time(9, 30, 0)
    
    # 이미 개장 중인지 확인
    if (weekday < 5 and  # 평일이고
        now_et.time() >= market_open_time and  # 9:30 AM 이후이고
        now_et.time() < datetime_time(16, 0, 0)):  # 4:00 PM 이전
        return 0  # 이미 개장 중
    
    # 다음 개장일 계산 (동부 시간 기준)
    # 현재 동부 날짜 기준으로 datetime 객체 생성
    now_et_full = datetime.combine(now_et.date(), now_et.time())
    
    if weekday >= 5:  # 주말
        days_to_monday = 7 - weekday
        next_market_day_et = now_et_full + timedelta(days=days_to_monday)
    else:  # 평일
        if now_et.time() >= datetime_time(16, 0, 0):  # 오늘 장 마감 후
            next_market_day_et = now_et_full + timedelta(days=1)  # 내일
        else:  # 오늘 장 시작 전
            next_market_day_et = now_et_full  # 오늘
    
    # 다음 개장 시간 설정 (동부 시간 9:30 AM)
    next_open_time_et = next_market_day_et.replace(hour=9, minute=30, second=0)
    
    # 동부 시간을 한국 시간으로 변환
    next_open_time_kr = next_open_time_et + timedelta(hours=hour_diff)
    
    # 한국 시간으로 남은 시간 계산
    time_to_next_market_open = next_open_time_kr - now_kr
    
    return time_to_next_market_open.total_seconds()

def is_dst():
    """현재 미국 동부시간이 서머타임(EDT)인지 확인합니다.
    
    Returns:
        bool: 서머타임이면 True, 아니면 False
    """
    # 현재 한국 시간
    now_kr = datetime.now()
    year = now_kr.year
    
    # 미국 서머타임 기간: 3월 둘째 일요일 ~ 11월 첫째 일요일
    dst_start = datetime(year, 3, 8 + (6 - datetime(year, 3, 8).weekday()) % 7, 2)
    dst_end = datetime(year, 11, 1 + (6 - datetime(year, 11, 1).weekday()) % 7, 2)
    
    return dst_start <= now_kr.replace(tzinfo=None) < dst_end

# 로그 포맷 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)

def load_config():
    """설정 파일을 로드하는 함수"""
    return load_secure_config('data/config.yaml')

def init_kis(config):
    """KIS API 초기화 함수"""
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
    return kis

def init_analysts(kis, config):
    """분석기 초기화 함수"""
    macd_analyst = MACD_Analyst(kis, config)
    return macd_analyst

def init_trader(kis, config):
    """트레이더 초기화 함수"""
    trader = Trader(kis, config)
    return trader

def main():
    """메인 실행 함수"""
    try:
        # 설정 로드
        config = load_config()
        
        # KIS API 초기화
        kis = init_kis(config)
        
        # 분석기 및 트레이더 초기화
        analysts = init_analysts(kis, config)
        trader = init_trader(kis, config)
        
        # 종목 목록 가져오기
        tickers = []
        if config["companies_settings"]["auto_fetch"]:
            logging.info("나스닥 100 기업 목록을 자동으로 가져오는 중...")
            tickers = Analyst.get_nasdaq_top_100()
        else:
            tickers = config["companies_settings"]["manual_tickers"]
            
        # 종목 분석
        analyze_tickers(tickers)
        
        # 운영 사이클 설정
        operating_cycle = config.get("system", {}).get("operating_cycle", 3600)  # 기본 1시간
        
        logging.info("자동 매매 프로그램 시작")
        
        while True:
            try:
                # 현재 시간 확인
                now = datetime.now()
                
                # 미국 장 시작 시간 확인 (EDT 기준)
                try:
                    us_market_open = trader.get_trading_hours()
                    if us_market_open:
                        try:
                            market_open_time = trader.kis.trading_hours("US").open_kst
                            # 장 시작 1시간 전인지 확인
                            is_pre_market = (market_open_time - timedelta(hours=1)).time() <= now.time() < market_open_time.time()
                            
                            if is_pre_market:
                                logging.info("미국 장 시작 1시간 전 - 추가 매매 사이클 실행")
                                result = trader.auto_trading_cycle()
                                logging.info(f"추가 매매 사이클 결과: 매도 {result['sell_count']}종목, 매수 {result['buy_count']}종목")
                        except Exception as e:
                            logging.error(f"장 시작 시간 확인 중 오류 발생: {str(e)}")
                            # 오류 발생 시에도 정상 매매 사이클 실행
                except Exception as e:
                    logging.error(f"미국 장 개장 여부 확인 중 오류 발생: {str(e)}")
                    # 오류 발생 시에도 계속 진행
                
                # 정상 매매 사이클 실행
                logging.info("정상 매매 사이클 실행")
                result = trader.auto_trading_cycle()
                logging.info(f"매매 사이클 결과: 매도 {result['sell_count']}종목, 매수 {result['buy_count']}종목")
                
                # 다음 사이클까지 대기
                logging.info(f"다음 사이클까지 {operating_cycle}초 대기")
                time.sleep(operating_cycle)
                
            except Exception as e:
                logging.error(f"매매 사이클 실행 중 오류 발생: {str(e)}")
                import traceback
                logging.error(f"상세 오류: {traceback.format_exc()}")
                time.sleep(60)  # 오류 발생 시 1분 대기 후 재시도
                
    except Exception as e:
        logging.error(f"프로그램 실행 중 치명적 오류 발생: {str(e)}")
        import traceback
        logging.error(f"상세 오류: {traceback.format_exc()}")
        raise

if __name__ == '__main__':
    main()
