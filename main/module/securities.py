"""
보안 설정 관리 모듈
PythonAnywhere에서 안전하게 설정을 로드하기 위한 유틸리티 함수
"""
import os
import re
import yaml
import logging
from datetime import datetime, timedelta

def load_secure_config(config_path="data/config.yaml"):
    """
    환경 변수를 사용하여 안전하게 설정 파일을 로드합니다.
    설정 파일 내의 ${ENV_VAR} 형태의 문자열을 해당 환경 변수 값으로 대체합니다.
    
    Args:
        config_path (str): 설정 파일 경로
        
    Returns:
        dict: 보안 처리된 설정 정보
    """
    try:
        with open(config_path, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
        
        # 환경 변수 패턴을 찾기 위한 정규식
        env_pattern = re.compile(r'\${([^}]+)}')
        
        # 설정 파일 내용을 재귀적으로 순회하며 환경 변수 값으로 대체
        def replace_env_vars(config_item):
            if isinstance(config_item, dict):
                return {k: replace_env_vars(v) for k, v in config_item.items()}
            elif isinstance(config_item, list):
                return [replace_env_vars(item) for item in config_item]
            elif isinstance(config_item, str):
                # ${ENV_VAR} 형태의 문자열에서 환경 변수 추출 및 값 대체
                matches = env_pattern.findall(config_item)
                result = config_item
                
                for env_var in matches:
                    env_value = os.environ.get(env_var)
                    if env_value is None:
                        logging.warning(f"환경 변수 {env_var}가 설정되지 않았습니다.")
                        # 환경 변수가 없는 경우 원래 값 유지
                    else:
                        # 해당 패턴을 환경 변수 값으로 대체
                        result = result.replace(f"${{{env_var}}}", env_value)
                
                return result
            else:
                return config_item
        
        secure_config = replace_env_vars(config)
        logging.info("보안 설정을 성공적으로 로드했습니다.")
        return secure_config
        
    except Exception as e:
        logging.error(f"설정 파일 로드 중 오류 발생: {str(e)}")
        raise 