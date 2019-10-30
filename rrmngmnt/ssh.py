import os
import time
import uuid
import socket
import paramiko
import contextlib
import subprocess
from rrmngmnt.common import normalize_string
from rrmngmnt.executor import Executor, ExecutorFactory


AUTHORIZED_KEYS = os.path.join("%s", ".ssh/authorized_keys")
KNOWN_HOSTS = os.path.join("%s", ".ssh/known_hosts")
ID_RSA_PUB = os.path.join("%s", ".ssh/id_rsa.pub")
ID_RSA_PRV = os.path.join("%s", ".ssh/id_rsa")
CONNECTIVITY_TIMEOUT = 600
CONNECTIVITY_SAMPLE_TIME = 20


class RemoteExecutor(Executor):
    """
    Any resource which provides SSH service.

    This class is meant to replace our current utilities.machine.LinuxMachine
    class. This allows you to lower access to communicate with ssh.
    Like a live interaction, getting rid of True/False results, and
    mixing stdout with stderr.

    You can still use use 'run_cmd' method if you don't care.
    But I would recommend you to work like this:
    """

    TCP_TIMEOUT = 10.0

    class LoggerAdapter(Executor.LoggerAdapter):
        """
        Makes sure that all logs which are done via this class, has
        appropriate prefix. [user@IP/password]
        """
        def process(self, msg, kwargs):
            return (
                "[%s@%s/%s] %s" % (
                    self.extra['self'].user.name,
                    self.extra['self'].address,
                    self.extra['self'].user.password,
                    msg,
                ),
                kwargs,
            )

    class Session(Executor.Session):
        """
        Represents active ssh connection
        """
        def __init__(self, executor, timeout=None):
            super(RemoteExecutor.Session, self).__init__(executor)
            if timeout is None:
                timeout = RemoteExecutor.TCP_TIMEOUT
            self._timeout = timeout
            self._ssh = paramiko.SSHClient()
            self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            if self._executor.use_pkey:
                self.pkey = paramiko.RSAKey.from_private_key_file(
                    ID_RSA_PRV % os.path.expanduser('~')
                )
                self._executor.user.password = None
            else:
                self.pkey = None

        def __exit__(self, type_, value, tb):
            if type_ is socket.timeout:
                self._update_timeout_exception(value)
            try:
                self.close()
            except Exception as ex:
                if type_ is None:
                    raise
                else:
                    self._executor.logger.debug(
                        "Can not close ssh session %s", ex,
                    )

        def open(self):
            self._ssh.get_host_keys().clear()
            try:
                self._ssh.connect(
                    self._executor.address,
                    username=self._executor.user.name,
                    password=self._executor.user.password,
                    timeout=self._timeout,
                    pkey=self.pkey,
                    port=self._executor.port,
                )
            except (socket.gaierror, socket.herror) as ex:
                args = list(ex.args)
                message = "%s: %s" % (self._executor.address, args[1])
                args[1] = message
                ex.strerror = message
                ex.args = tuple(args)
                raise
            except socket.timeout as ex:
                self._update_timeout_exception(ex)
                raise

        def close(self):
            self._ssh.close()

        def _update_timeout_exception(self, ex, timeout=None):
            if getattr(ex, '_updated', False):
                return
            if timeout is None:
                timeout = self._timeout
            message = "%s: timeout(%s)" % (
                self._executor.address, timeout
            )
            ex.args = (message,)
            ex._updated = True

        def command(self, cmd):
            return RemoteExecutor.Command(cmd, self)

        def run_cmd(self, cmd, input_=None, timeout=None, follow_output=False):
            cmd = self.command(cmd)
            return (
                cmd.run_real_time(timeout) if follow_output
                else cmd.run(input_, timeout)
            )

        @contextlib.contextmanager
        def open_file(self, path, mode='r', bufsize=-1):
            with contextlib.closing(self._ssh.open_sftp()) as sftp:
                with contextlib.closing(
                    sftp.file(
                        path,
                        mode,
                        bufsize,
                    )
                ) as fh:
                    yield fh

    class Command(Executor.Command):
        """
        This class holds all data related to command execution.
         - the command itself
         - stdout/stderr streams
         - out/err string which were produced by command
         - returncode the exit status of command
        """
        def __init__(self, cmd, session):
            super(RemoteExecutor.Command, self).__init__(
                subprocess.list2cmdline(cmd),
                session,
            )
            self._in = None
            self._out = None
            self._err = None

        def get_rc(self, wait=False):
            if self._rc is None:
                if self._out is not None:
                    if self._out.channel.exit_status_ready() or wait:
                        self._rc = self._out.channel.recv_exit_status()
            return self._rc

        @contextlib.contextmanager
        def execute(
            self, bufsize=-1, timeout=None, get_pty=False, log_result=True
        ):
            """
            This method allows you to work directly with streams.

            with cmd.execute() as in_, out, err:
                # where in_, out and err are file-like objects
                # where you can read data from these
            """
            try:
                self.logger.debug("Executing: %s", self.cmd)
                self._in, self._out, self._err = self._ss._ssh.exec_command(
                    self.cmd,
                    bufsize=bufsize,
                    timeout=timeout,
                    get_pty=get_pty,
                )
                yield self._in, self._out, self._err
                self.get_rc(True)
            except socket.timeout as ex:
                self._ss._update_timeout_exception(ex, timeout)
                raise
            finally:
                if self._in is not None:
                    self._in.close()
                if self._out is not None:
                    self._out.close()
                if self._err is not None:
                    self._err.close()
                if log_result:
                    self.logger.debug("Results of command: %s", self.cmd)
                    self.logger.debug("  OUT: %s", self.out)
                    self.logger.debug("  ERR: %s", self.err)
                    self.logger.debug("  RC: %s", self.rc)

        def run(self, input_, timeout=None, get_pty=False):
            with self.execute(
                timeout=timeout, get_pty=get_pty
            ) as (in_, out, err):
                if input_:
                    in_.write(input_)
                    in_.close()
                self.out = normalize_string(out.read())
                self.err = normalize_string(err.read())
            return self.rc, self.out, self.err

        def run_real_time(self, timeout=None, get_pty=False):
            """
            This function executes command and continuously (line by line) logs
            its output on debug level.
            """
            with self.execute(
                timeout=timeout, get_pty=get_pty, log_result=False
            ) as (in_, out, err):
                self.logger.info("Following in real time: %s", self.cmd)
                captured_out = ""
                for line in iter(out.readline, ""):
                    captured_out += line
                    self.logger.debug(line.rstrip('\n'))
                self.logger.debug('')
                self.out = normalize_string(captured_out)
                self.err = normalize_string(err.read())
            return self.rc, self.out, self.err

    def __init__(self, user, address, use_pkey=False, port=22):
        """
        Args:
            use_pkey (bool): Use ssh private key in the connection
            user (instance of User): User
            address (str): Ip / hostname
            port (int): Port to connect
        """
        super(RemoteExecutor, self).__init__(user)
        self.address = address
        self.use_pkey = use_pkey
        self.port = port

    def session(self, timeout=None):
        """
        Args:
            timeout (float): Tcp timeout

        Returns:
            instance of RemoteExecutor.Session: The session
        """
        return RemoteExecutor.Session(self, timeout)

    def run_cmd(
        self, cmd, input_=None, tcp_timeout=None,
        io_timeout=None, follow_output=False
    ):
        """
        Args:
            tcp_timeout (float): Tcp timeout
            cmd (list): Command
            input_ (str): Input data
            io_timeout (float): Timeout for data operation (read/write)
            follow_output (bool): Log each line as soon as it gets to stdout

        Returns:
            tuple (int, str, str): Rc, out, err
        """
        with self.session(tcp_timeout) as session:
            return session.run_cmd(cmd, input_, io_timeout, follow_output)

    def is_connective(self, tcp_timeout=20.0):
        """
        Check if address is connective via ssh

        Args:
            tcp_timeout (float): Time to wait for response

        Returns:
            bool: True if address is connective, false otherwise
        """
        try:
            self.logger.info(
                "Check if address is connective via ssh in given timeout %s",
                tcp_timeout
            )
            self.run_cmd(['true'], tcp_timeout=tcp_timeout)
            return True
        except (socket.timeout, socket.error) as e:
            self.logger.debug("Socket error: %s", e)
        except Exception as e:
            self.logger.debug("SSH exception: %s", e)
        return False

    def wait_for_connectivity_state(
        self, positive,
        timeout=CONNECTIVITY_TIMEOUT,
        sample_time=CONNECTIVITY_SAMPLE_TIME
    ):
        """
        Wait until address will be connective or not via ssh

        Args:
            positive (bool): Wait for the positive or negative connective state
            timeout (int): Wait timeout
            sample_time (int): Sample the ssh each sample_time seconds

        Returns:
            bool: True, if positive and ssh is connective or negative and ssh
                does not connective, otherwise false
        """
        reachable = "unreachable" if positive else "reachable"
        timeout_counter = 0
        while self.is_connective() != positive:
            if timeout_counter > timeout:
                self.logger.error(
                    "Address %s is still %s via ssh, after %s seconds",
                    self.address, reachable, timeout
                )
                return False
            time.sleep(sample_time)
            timeout_counter += sample_time
        return True


class PlaybookExecutor(RemoteExecutor):
    """
    This is basically enriched RemoteExecutor created specifically for remote
    execution of Ansible playbooks. It differs from RemoteExecutor in three
    aspects:
        - Each instance of PlaybookExecutor generates a globally unique ID in
          compliance with RFC 4122. This GUID is used to identify one specific
          execution of Ansible playbook. We'll be using only the first part of
          that GUID, which admittedly does not guarantee complete uniqueness.
          But the chance of collision is so low that the benefir of having
          short identifier outweights that risk.
        - RemoteExecutor usually instantiates its own logger (called
          RemoteExecutor by the class name) that has no handlers or formatters
          specified and that inherits them from a parent logger. This is also
          the default behavior of PlaybookExecutor. However, if we instantiated
          our Host object with playbook_logger, we can pass it to
          PlaybookExecutorFactory and the resulting instance of
          PlaybookExecutor will use that logger (along with its handlers and
          formatters) instead. This is useful when you want to redirect Ansible
          output to other destination than what your app's main logger logs to.
        - We also provide different LoggerAdapter here. Its main purpose is to
          enrich emitted LogRecord with run's GUID.
    """
    playbook_cmd = 'ansible-playbook'
    check_mode_param = '--check'

    def __init__(self, user, address, port, executor_logger):
        """
        Args:
            user (instance of User): User
            address (str): Ip / hostname
            port (int): Port to connect
            executor_logger (logging.Logger): This logger will be used to log
            Ansible playbook output if provided
        """
        super(PlaybookExecutor, self).__init__(
            user, address, use_pkey=False, port=22,
        )
        self.run_uuid = uuid.uuid4()
        self.short_run_uuid = str(self.run_uuid).split('-')[0]
        if executor_logger is not None:
            self.logger.logger = executor_logger

    class LoggerAdapter(Executor.LoggerAdapter):
        """
        Makes sure that all logs which are done via this class have run's GUID
        preffixed.
        """
        def process(self, msg, kwargs):
            return (
                "[%s] %s" % (self.extra['self'].short_run_uuid, msg),
                kwargs,
            )


class RemoteExecutorFactory(ExecutorFactory):

    def __init__(self, use_pkey=False, port=22):
        self.use_pkey = use_pkey
        self.port = port

    def build(self, host, user):
        return RemoteExecutor(
            user, host.ip, use_pkey=self.use_pkey, port=self.port)


class PlaybookExecutorFactory(ExecutorFactory):

    def __init__(self, port=22):
        self.port = port

    def build(self, host, user, executor_logger):
        return PlaybookExecutor(
            user, host.ip, port=self.port, executor_logger=executor_logger,
        )
