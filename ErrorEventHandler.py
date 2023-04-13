import logging as log
import APRSFriendAlert

class ErrorHandler(log.Handler):
    def emit(self, record):
        if record.levelno == log.CRITICAL or record.levelno == log.ERROR:
            APRSFriendAlert.handleError(record)