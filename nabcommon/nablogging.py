import logging
import logging.handlers
import os


def setup_logging(daemon):
    logdir = os.environ.get("LOGDIR", "/var/log/")
    loglevel = os.environ.get("LOGLEVEL", "INFO")
    log_handler = logging.handlers.WatchedFileHandler(f"{logdir}/{daemon}.log")
    formatter = logging.Formatter(
        f"%(asctime)s [%(levelname)s] {daemon}: %(message)s"
    )
    log_handler.setFormatter(formatter)
    logger = logging.getLogger()
    logger.addHandler(log_handler)
    try:
        logger.setLevel(loglevel)
    except ValueError:
        loglevel = "DEBUG"
        logger.setLevel(loglevel)
    logging.info(f"started with log level {loglevel}")
