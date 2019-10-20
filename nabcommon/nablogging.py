import logging
import logging.handlers


def setup_logging(daemon):
    log_handler = logging.handlers.WatchedFileHandler(
        "/var/log/{daemon}.log".format(daemon=daemon)
    )
    formatter = logging.Formatter("%(levelname)s %(asctime)s %(message)s")
    log_handler.setFormatter(formatter)
    logger = logging.getLogger()
    logger.addHandler(log_handler)
    logger.setLevel(logging.DEBUG)
    logging.info("{daemon} started".format(daemon=daemon))
