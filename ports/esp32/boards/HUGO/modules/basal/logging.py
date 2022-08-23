#  Copyright (c) 2022 Jakub Vesely
#  This software is published under MIT license. Full text of the license is available at https://opensource.org/licenses/MIT

import sys
import os


class LoggerBase():
    critical_id = 51
    error_id = 41
    warning_id = 31
    info_id = 21
    value_id = 22
    debug_id = 11
    not_set_id = 0

    def log(self, level, message):
        raise NotImplementedError


class Logging():
    loggers = list()

    def __init__(self, tag=""):
        self.level = LoggerBase.info_id
        self.tag = tag

    @staticmethod
    def add_logger(logger):
        Logging.loggers.append(logger)

    def _fit(self, msg_length, is_first):
        len_prefix = 3 + len(self.tag) if is_first else 0  # 2: level + ": "
        # < MP_BLUETOOTH_DEFAULT_ATTR_LEN ('\f' can be added)
        return len_prefix + msg_length < 512

    def log(self, level, message, *args, has_prefix=True):
        if level < self.level or not self.loggers:
            return

        prefix = (self.tag + ": ").encode("utf-8") if has_prefix else b""
        try:
            complete = prefix + \
                ((message % args) if args else message).encode("utf-8")
        except (AttributeError, TypeError):
            complete = prefix + (str((message, args))
                                 if args else str(message)).encode("utf-8")
        for logger in self.loggers:
            logger.log(level, complete)

    def exception(self, exc, level=LoggerBase.error_id, extra_message=None):
        if level < self.level:
            return

        file_name = ".error"
        with open(file_name, "w") as file:
            #pylint: disable=no-member
            sys.print_exception(exc, file)
        is_first = True
        with open(file_name, "r") as file:
            content = extra_message + "\n" if extra_message else ""
            while True:
                line = file.readline()
                if not line:
                    break

                if not self._fit(len(content) + len(line), is_first):
                    content += "\f"  # add page separator indicating message continuation to the message reader
                    self.log(level, content, has_prefix=is_first)
                    content = ""
                    is_first = False
                content += line
            if content:
                self.log(level, content, has_prefix=is_first)
        os.remove(file_name)

    def debug(self, msg, *args):
        self.log(LoggerBase.debug_id, msg, *args)

    def info(self, msg, *args):
        self.log(LoggerBase.info_id, msg, *args)

    def value(self, msg, *args):
        self.log(LoggerBase.value_id, msg, *args)

    def warning(self, msg, *args):
        self.log(LoggerBase.warning_id, msg, *args)

    def error(self, msg, *args):
        self.log(LoggerBase.error_id, msg, *args)

    def critical(self, msg, *args):
        self.log(LoggerBase.critical_id, msg, *args)
