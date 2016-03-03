import sys
import logging


class Resource(object):
    """
    Common base for any kind of resource across rhevm tests
    """
    class LoggerAdapter(logging.LoggerAdapter):
        def warn(self, *args, **kwargs):
            """
            Just alias for warning, the warn is provided by logger instance,
            but not by adapter.
            """
            self.warning(*args, **kwargs)

    class ProgressHandler(logging.StreamHandler):
        """
        Handle progress bar output and show it under sys.stdout
        """
        def emit(self, record):
            show_progress_bar = hasattr(record, 'show_progress_bar')
            if show_progress_bar:
                super(Resource.ProgressHandler, self).emit(record)

    def __init__(self):
        super(Resource, self).__init__()
        logger = logging.getLogger(self.__class__.__name__)
        ph = self.ProgressHandler(sys.stdout)
        ph.setLevel(logging.DEBUG)
        logger.addHandler(ph)
        self._logger_adapter = self.LoggerAdapter(logger, {'self': self})

    @property
    def logger(self):
        return self._logger_adapter
