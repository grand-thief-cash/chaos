# components/logging/schema.py
# pyinfra/components/logging/schema.py
from core.component import ComponentConfig

class LoggingConfig(ComponentConfig):
    level: str = "INFO"
    format: str = "[%(asctime)s][%(filename)s:%(lineno)d][%(levelname)s][%(thread)d][%(traceid)s][%(execution_time).2fs][%(message)s]"
    log_dir: str = "logs"
    when: str = "MIDNIGHT"
    interval: int = 1
    backup_count: int = 15
    app_name: str
    suffix: str = "%Y%m%d"