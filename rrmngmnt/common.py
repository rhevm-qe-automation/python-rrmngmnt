import six
import socket


def fqdn2ip(fqdn):
    """
    translate fqdn to IP

    Args:
        fqdn (str): host name

    Returns:
        str: IP address
    """
    try:
        return socket.gethostbyname(fqdn)
    except (socket.gaierror, socket.herror) as ex:
        args = list(ex.args)
        message = "%s: %s" % (fqdn, args[1])
        args[1] = message
        ex.strerror = message
        ex.args = tuple(args)
        raise


def normalize_string(data):
    """
    get normalized string

    Args:
        data (object): data to process
    Returns:
        object: normalized string
    """
    if isinstance(data, six.binary_type):
        data = data.decode('utf-8', errors='replace')
    if isinstance(data, six.text_type):
        data = data.encode('utf-8', errors='replace')
    return data


class CommandReader(object):

    def __init__(self, executor, cmd, session_timeout=None, cmd_input=None):
        self.executor = executor
        self.cmd = cmd
        self.session_timeout = session_timeout
        self.cmd_input = cmd_input
        self.rc = None
        self.out = ''
        self.err = ''

    def read_lines(self):
        with self.executor.session(self.session_timeout) as ss:
            command = ss.command(self.cmd)
            with command.execute() as (in_, out, err):
                if self.cmd_input:
                    in_.write(self.cmd_input)
                    in_.close()
                while True:
                    line = out.readline()
                    self.out += line
                    if not line:
                        break
                    yield line.strip()
                self.rc = command.rc
                self.err = err.read()
