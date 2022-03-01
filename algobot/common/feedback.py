import logging

logger = logging.getLogger(__name__)

class RequestResult:
    pass


class RequestSuccess(RequestResult):
    pass


class RequestFail(RequestResult):
    def __init__(self, message: str, *args):
        self.message = message
        self.extra = args
        logger.warn(f'Request failed with message: {message}')
