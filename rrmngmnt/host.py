"""
This module define resource Host which is entry point to various services.
It should hold methods / properties which returns you Instance of specific
Service hosted on that Host.
"""
import copy
import json
import os
import socket
import threading
import warnings

import netaddr
from rrmngmnt import errors
from rrmngmnt import power_manager
from rrmngmnt import ssh
from rrmngmnt.common import fqdn2ip
from rrmngmnt.filesystem import FileSystem
from rrmngmnt.firewall import Firewall
from rrmngmnt.network import Network
from rrmngmnt.operatingsystem import OperatingSystem
from rrmngmnt.package_manager import PackageManagerProxy
from rrmngmnt.resource import Resource
from rrmngmnt.service import Systemd, SysVinit, InitCtl
from rrmngmnt.storage import NFSService, LVMService


class Host(Resource):
    """
    This resource could represents any physical / virtual machine
    """

    # The purpose of inventory variable is keeping all instances of
    # interesting resources in single place.
    inventory = list()
    lock = threading.Lock()

    default_service_providers = [
        Systemd,
        SysVinit,
        InitCtl,
    ]
    executor_factory = ssh.RemoteExecutorFactory()
    playbook_executor_factory = ssh.PlaybookExecutorFactory()

    class LoggerAdapter(Resource.LoggerAdapter):
        """
        Makes sure that all logs which are done via this class, has
        appropriate prefix. [IP]
        """
        def process(self, msg, kwargs):
            return (
                "[%s] %s" % (
                    self.extra['self'].ip,
                    msg,
                ),
                kwargs,
            )

    def __init__(self, ip, service_provider=None, playbook_logger=None):
        """
        Args:
            ip (str): IP address of machine or resolvable FQDN
            service_provider (Service): system service handler
            playbook_logger (logging.Logger): You may provide alternative
            logger only for Ansible-related events
        """
        super(Host, self).__init__()
        if not netaddr.valid_ipv4(ip) and not netaddr.valid_ipv6(ip):
            ip = fqdn2ip(ip)
        self.ip = ip
        self.users = list()
        self._executor_user = None
        self._power_managers = dict()
        self._service_provider = service_provider
        self._package_manager = PackageManagerProxy(self)
        self.os = OperatingSystem(self)
        self.playbook_logger = playbook_logger
        self.add()  # adding host to inventory

    def __str__(self):
        return "Host(%s)" % self.ip

    @classmethod
    def get(cls, ip):
        """
        Get host from inventory

        Args:
            ip (str): IP address of machine or resolvable FQDN

        Returns:
            Host: host instance
        """
        host = [h for h in cls.inventory if h.ip == ip or h.fqdn == ip]
        if not host:
            raise ValueError("There is no host with %s" % ip)
        return host[0]

    def add(self):
        """
        Add host to inventory
        """
        with self.lock:
            try:
                host = self.get(self.ip)
            except ValueError:
                pass
            else:
                self.inventory.remove(host)
            self.logger.debug("Adding host with ip '%s' to inventory", self.ip)
            self.inventory.append(self)

    @property
    def fqdn(self):
        return socket.getfqdn(self.ip)

    def add_power_manager(self, pm_type, **init_params):
        """
        Add power power manager to host

        Args:
            pm_type (str): power manager type
                (power_manager.SSH_TYPE for example)
            init_params (dict): power manager init parameters
        """
        self._power_managers[pm_type] = getattr(
            power_manager, power_manager.MANAGERS[pm_type]
        )(self, **init_params)

    def get_power_manager(self, pm_type=None):
        """
        Get host power manager

        Args:
            pm_type (str): power manager type(power_manager.SSH_TYPE for
                example)

        Returns:
            PowerManager: instance of powermanager

        Raises:
            Exception: If power manager not supported
        """
        if self._power_managers:
            if pm_type:
                if pm_type in self._power_managers:
                    return self._power_managers[pm_type]
                raise Exception(
                    "PM with type '%s' is not associated with the host %s" %
                    (pm_type, self)
                )
            else:
                return self._power_managers.values()[0]
        raise Exception("No PM is associated with the host %s" % self)

    def get_user(self, name):
        for user in self.users:
            if user.get_full_name() == name:
                return user
        raise Exception(
            "User '%s' is not associated with host %s" % (name, self)
        )

    def add_user(self, user):
        """
        Adds user to users collection, and tries remove duplicities.

        Args:
            user (User): user to add
        """
        for u in self.users[:]:
            if user.get_full_name() == u.get_full_name():
                self.users.remove(u)
        self.users.append(user)

    def _set_executor_user(self, user):
        """
        This method explicitly set user which is used to execute commands
        on host. And adds user into users collection.

        Args:
            user (User): specific user
        """
        self._executor_user = user
        self.add_user(user)

    def _get_executor_user(self):
        """
        The user which is supposed to be used for command execution.

        Returns:
            user: instance of User
        """
        if self._executor_user:
            return copy.copy(self._executor_user)
        return copy.copy(self.root_user)

    executor_user = property(_get_executor_user, _set_executor_user)
    """
    You can set or get the user which is used to execute commands.
    For more info see _set_executor_user and _get_executor_user.
    """

    @property
    def root_user(self):
        return self.get_user('root')

    @property
    def package_manager(self):
        return self._package_manager

    @property
    def power_manager(self):
        return self.get_power_manager()

    def executor(self, user=None, pkey=False):
        """
        Gives you executor to allowing command execution

        Args:
            user (User): the executed commands will be executed under this
                user. when it is None, the default executor user is used,
                see set_executor_user method for more info.
        """
        if user is None:
            user = self.executor_user
        if pkey:
            warnings.warn(
                "Parameter 'pkey' is deprecated and will be removed in future."
                "Please use ssh.RemoteExecutorFactory to set this parameter."
            )
            ef = copy.copy(ssh.RemoteExecutorFactory)
            ef.use_pkey = pkey
            return ef(self.ip, user)
        return self.executor_factory.build(self, user)

    def playbook_executor(self):
        """
        Gives you executor allowing you Ansible playbook execution.
        Current implementation does not allow for specifying user.

        Returns:
            ssh.PlaybookExecutor: Ansible playbook executor
        """
        return self.playbook_executor_factory.build(
            self,
            self.executor_user,
            executor_logger=self.playbook_logger
        )

    def run_command(
        self, command, input_=None, tcp_timeout=None, io_timeout=None,
        user=None, pkey=False,
    ):
        """
        Run command on host

        Args:
            command (list): command
            input_ (str): input data
            tcp_timeout (float): tcp timeout
            `io_timeout (float): timeout for data operation (read/write)

        Returns:
            tuple: tuple of (rc, out, err)
        """
        self.logger.info("Executing command %s", ' '.join(command))
        rc, out, err = self.executor(user=user, pkey=pkey).run_cmd(
            command, input_=input_, tcp_timeout=tcp_timeout,
            io_timeout=io_timeout
        )
        if rc:
            self.logger.error(
                "Failed to run command %s ERR: %s OUT: %s", command, err, out
            )
        return rc, out, err

    def run_playbook(
        self, playbook_path_local, playbook_remote_dir="/root",
        extra_vars=None, run_in_check_mode=False, vars_files=None,
        verbose_level=1, inventory=None, tcp_timeout=None, io_timeout=None
    ):
        """
        Run Ansible playbook on host

        Args:
            playbook_path_local (str): Path to playbook on your machine
            playbook_remote_dir (str): Directory on host where you want the
            playbook to be place
            extra_vars (dict): Dictionary of extra variables that are to be
            provided to playbook execution. They will be dumpled into JSON file
            and included using -e@ parameter
            run_in_check_mode (bool): If True, playbook will not actually be
            executed, but instead run with --check parameter
            vars_files (list): List of additional variable files on your local
            file system to be included using -e@ parameter. Variables specified
            in those files will override those specified in extra_vars param
            verbose_level (int): How much should playbook be verbose. Possible
            values are 1 through 5
            inventory (str): Path to an inventory file on your local file
            system. If none is provided, inventory including localhost will be
            generated and used
            tcp_timeout (float): tcp timeout
            io_timeout (float): timeout for data operation (read/write)

        Returns:
            tuple: tuple of (rc, out, err)
        """
        files = []  # Files created on host by this function

        executor = self.playbook_executor()

        # Upload playbook to the host
        playbook_path_remote = os.path.join(
            playbook_remote_dir, os.path.basename(playbook_path_local),
        )
        self.fs.put(
            path_src=playbook_path_local, path_dst=playbook_path_remote
        )
        files.append(playbook_path_remote)

        # Dump user-provided extra vars to a file
        if extra_vars:
            extra_vars_file = os.path.join(
                playbook_remote_dir, "extra_vars.json"
            )
            self.fs.create_file(
                content=json.dumps(extra_vars), path=extra_vars_file,
            )
            files.append(extra_vars_file)

        # Either upload user-provided inventory or create a default one
        if inventory is None:
            default_inventory_file = os.path.join(
                playbook_remote_dir, "inventory",
            )
            inventory = default_inventory_file
            self.fs.create_file(
                content='localhost ansible_connection=local', path=inventory,
            )
        else:
            inventory_on_host = os.path.join(
                playbook_remote_dir, os.path.basename(inventory),
            )
            self.fs.put(path_src=inventory, path_dst=inventory_on_host)
            inventory = inventory_on_host
        files.append(inventory)

        # Upload other variable files to be included in playbook execution
        if vars_files:
            vars_files_on_host = []
            for vars_file in vars_files:
                vars_file_on_host = os.path.join(
                    playbook_remote_dir, os.path.basename(vars_file),
                )
                self.fs.put(path_src=vars_file, path_dst=vars_file_on_host)
                vars_files_on_host.append(vars_file_on_host)
            files.extend(vars_files_on_host)

        # Compose command that will be executed on host
        cmd = [
            executor.playbook_cmd,
            "-{}".format("v" * verbose_level),
            "-i",
            inventory,
        ]
        if extra_vars:
            cmd.append("-e@{}".format(extra_vars_file))
        if vars_files:
            for vars_file in vars_files_on_host:
                cmd.append("-e@{}".format(vars_file))
        if run_in_check_mode:
            cmd.append(executor.check_mode_param)
        cmd.append(playbook_path_remote)

        # Execute the playbook
        self.logger.info(
            "Executing Ansible playbook with ID: %s", executor.short_run_uuid,
        )
        self.logger.info("Ansible playbook command: %s", " ".join(cmd))
        self.logger.info("Ansible extra vars: %s", extra_vars)
        rc, out, err = executor.run_cmd(
            cmd, tcp_timeout=tcp_timeout,
            io_timeout=io_timeout, follow_output=True,
        )
        self.logger.info(
            "Ansible playbook with ID %s finished with RC %s",
            executor.short_run_uuid, rc,
        )

        # Clean-up
        for f in files:
            self.fs.remove(f)

        return rc, out, err

    def copy_to(self, resource, src, dst, mode=None, ownership=None):
        """
        Copy to host from another resource

        Args:
            src (str): Path to source
            dst (str): Path to destination
            resource (instance of Host): Resource to copy from
            mode (str): File permissions
            ownership (tuple): File ownership(ex. ('root', 'root'))
        """
        warnings.warn(
            "This method is deprecated and will be removed. "
            "Use Host.fs.transfer instead."
        )
        with resource.executor().session() as resource_session:
            with self.executor().session() as host_session:
                with resource_session.open_file(src, 'rb') as resource_file:
                    with host_session.open_file(dst, 'wb') as host_file:
                        host_file.write(resource_file.read())
        if mode:
            self.fs.chmod(path=dst, mode=mode)
        if ownership:
            self.fs.chown(dst, *ownership)

    def _create_service(self, name, timeout):
        for provider in self.default_service_providers:
            try:
                service = provider(self, name, timeout=timeout)
            except provider.CanNotHandle:
                pass
            else:
                self.logger.info(
                    "Setting %s as service provider", provider
                )
                self._service_provider = provider
                break
        else:
            msg = (
                "Can not find suitable service provider: %s" %
                self.default_service_providers
            )
            self.logger.error(msg)
            raise Exception(msg)
        return service

    def service(self, name, timeout=None):
        """
        Create service provider for desired service

        :Args:
            name (string): Service name
            timeout (int): Expected time to complete operations

        Returns:
            instance of SystemService: Service provider for desired service

        """
        if self._service_provider is None:
            # we need to pick up service provider,
            # assume same provider for all next services.
            service = self._create_service(name, timeout)
            self._service_provider = service.__class__
            return service
        try:
            return self._service_provider(self, name, timeout=timeout)
        except self._service_provider.CanNotHandle:
            # it may happen there is some special service
            # which needs different provider.
            # try to select different one
            service = self._create_service(name, timeout)
            self._service_provider = service.__class__
            return service

    def get_ssh_public_key(self, user=None):
        """
        Get SSH public key

        Args:
            user (instance of rrmngmnt.User): What user to get ssh keys for,
                default is root

        Returns:
            str: Ssh public key

        """
        if user is None:
            user = copy.copy(self.root_user)
        id_rsa_pub = ssh.ID_RSA_PUB % os.path.expanduser(
            "~%s" % user.name
        )
        id_rsa_prv = ssh.ID_RSA_PRV % os.path.expanduser(
            "~%s" % user.name
        )
        if not self.fs.exists(id_rsa_pub):
            # Generating SSH key if not exist
            cmd = [
                "ssh-keygen", "-q", "-t", "rsa", "-N", '', "-f",
                id_rsa_prv
            ]
            rc = self.run_command(cmd)[0]
            if rc:
                return ""

        cmd = ["cat", id_rsa_pub]
        return self.run_command(cmd)[1]

    def remove_remote_host_ssh_key(self, remote_host, user=None):
        """
        Remove remote host keys (ip, fqdn) from KNOWN_HOSTS file

        Args:
            remote_host (Host): Remote host resource object
            user (instance of rrmngmnt.User): What user to remove ssh keys for,
                default is root

        Returns:
            bool: True/false
        """
        if user is None:
            user = copy.copy(self.root_user)
        known_hosts = ssh.KNOWN_HOSTS % os.path.expanduser(
            "~%s" % user.name
        )
        ssh_keygen = ["ssh-keygen", "-R"]
        if self.fs.exists(known_hosts):
            # Remove old keys from local host if any
            for i in [remote_host.ip, remote_host.fqdn]:
                rc = self.run_command(ssh_keygen + [i])[0]
                if rc:
                    return False
        return True

    def remove_remote_key_from_authorized_keys(self, user=None):
        """
        Remove remote ssh key from AUTHORIZED_KEYS file

        Args:
            user (instance of rrmngmnt.User): What user to remove from
                authorized_keys, default is root

        Returns:
            bool: True/false
        """
        if user is None:
            user = copy.copy(self.root_user)
        authorized_keys = ssh.AUTHORIZED_KEYS % os.path.expanduser(
            "~%s" % user.name
        )
        local_fqdn = self.fqdn
        cmd = ["sed", "-c", "-i", "/%s/d" % local_fqdn, authorized_keys]
        rc = self.run_command(cmd)[0]
        if rc:
            return False
        return True

    def get_os_info(self):
        """
        Get OS info (Distro, version and code name)

        Returns:
            dict: Results {dist: , ver: , name:}

        Examples:
            {
             'dist': 'Red Hat Enterprise Linux Server',
             'name': 'Maipo',
             'ver': '7.1'
             }
        """
        warnings.warn(
            "This method is deprecated and will be removed. "
            "Use Host.os.distribution instead."
        )
        values = ["dist", "ver", "name"]
        try:
            return {
                'dist': self.os.distribution.distname,
                'ver': self.os.distribution.version,
                'name': self.os.distribution.id,
            }
        except errors.CommandExecutionFailure:
            return dict([(x, None) for x in values])

    def get_network(self):
        return Network(self)

    @property
    def network(self):
        return self.get_network()

    @property
    def nfs(self):
        return NFSService(self)

    @property
    def lvm(self):
        return LVMService(self)

    @property
    def fs(self):
        return FileSystem(self)

    @property
    def ssh_public_key(self):
        return self.get_ssh_public_key()

    @property
    def os_info(self):
        return self.get_os_info()

    def create_script(
        self, content, name_of_script, destination_path
    ):
        """
        Create script on resource

        Args:
            content (str): Content of the script
            name_of_script (str): Name of script to create
            destination_path (str): Directory on host to copy script

        Returns:
            str: Script absolute path, if creation success, otherwise empty
                string
        """
        warnings.warn(
            "This method is deprecated and will be removed. "
            "Use Host.fs.create_script instead."
        )
        dst = os.path.join(destination_path, name_of_script)
        try:
            self.fs.create_script(content, dst)
        except errors.CommandExecutionFailure:
            return ""
        return dst

    def is_connective(self, tcp_timeout=20.0):
        """
        Check if host is connective via ssh

        Args:
            tcp_timeout (float): Time to wait for response

        Returns:
            bool: True if host is connective, false otherwise
        """
        warnings.warn(
            "This method is deprecated and will be removed. "
            "Use Host.executor().is_connective() instead."
        )
        return self.executor().is_connective(tcp_timeout=tcp_timeout)

    @property
    def firewall(self):
        return Firewall(self)
