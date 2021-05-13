import logging
import logging.handlers
import os


def setup_logging(daemon):
    logdir = os.environ.get("NABD_LOGDIR", "/var/log/")
    log_handler = logging.handlers.WatchedFileHandler(f"{logdir}/{daemon}.log")
    formatter = logging.Formatter("%(levelname)s %(asctime)s %(message)s")
    log_handler.setFormatter(formatter)
    logger = logging.getLogger()
    logger.addHandler(log_handler)
    logger.setLevel(logging.DEBUG)
    logging.info(f"{daemon} started")
