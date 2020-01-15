# -*- coding: utf-8 -*-
"""
This module introduces support for the nmcli command which is provided by
NetworkManager.
"""
import shlex

import netaddr

from rrmngmnt.errors import CommandExecutionFailure, GeneralResourceError
from rrmngmnt.service import Service

IPV4_STATIC = "ipv4.addresses {address} ipv4.gateway {gateway}"
IPV6_STATIC = "ipv6.addresses {address} ipv6.gateway {gateway}"

IPV4_METHOD = "ipv4.method {method}"
IPV6_METHOD = "ipv6.method {method}"

COMMON_OPTIONS = (
    "type {type} "
    "con-name {con_name} "
    "ifname {ifname} "
    "autoconnect {auto_connect} "
    "save {save}"
)

IP_MANUAL_METHOD = "manual"

DEFAULT_BOND_MODE = "active-backup"

DEFAULT_MIIMON = 100

ERROR_MSG_FORMAT = "command -> {command}\nRC -> {rc}\nOUT -> {out}\nERROR -> {err}"  # noqa: E501

NMCLI_COMMAND = "nmcli {options} {object} {command}"
NMCLI_CONNECTION_DELETE = "nmcli connection delete {id}"
NMCLI_CONNECTION_ADD = "nmcli connection add"


class NMCLI(Service):
    """
    This class implements network operations using nmcli.
    """

    def __init__(self, host):
        super(NMCLI, self).__init__(host)
        self._executor = host.executor()

    def _exec_command(self, command):
        """
        Executes a command on the remote host.

        Args:
            command (str): a command to run remotely.

        Returns:
            str: command execution output.

        Raises:
            CommandExecutionFailure: if the remote host returned a code
            indicating a failure in execution.
        """
        split = shlex.split(command)

        rc, out, err = self._executor.run_cmd(split)

        if rc != 0:
            self.logger.error(
                ERROR_MSG_FORMAT.format(command=command, rc=rc, out=out, err=err)  # noqa: E501
            )
            raise CommandExecutionFailure(
                executor=self._executor, cmd=split, rc=rc, err=err
            )
        return out

    def is_connection_exist(self, connection):
        """
        Checks if a connection exists.

        Args:
            connection (str):  name, UUID or path.

        Returns:
            bool: True if the connection exists, or False if it does not.
        """
        command = "nmcli connection show {con}".format(con=connection)
        try:
            self._exec_command(command=command)
        except CommandExecutionFailure:
            return False
        return True

    def is_device_exist(self, device):
        """
        Checks if a device exists.

        Args:
            device (str): device name.

        Returns:
            bool: True if the device exists, or False if it does not.
        """
        command = "nmcli device show {dev}".format(dev=device)
        try:
            self._exec_command(command=command)
        except CommandExecutionFailure:
            return False
        return True

    def get_all_connections_uuids(self):
        """
        Gets existing NetworkManager profiles UUIDs.

        Returns:
            list[str]: all connection UUIDs.

        Raises:
            CommandExecutionFailure: if the remote host returned a code
            indicating a failure in execution.
        """
        command = NMCLI_COMMAND.format(
            options="-m multiline", object="connection", command="show"
        )
        out = self._exec_command(command=command)
        con_names = [
            line.strip("NAME:").strip() for line in out.splitlines() if "NAME:" in line  # noqa: E501
        ]
        return [self.get_connection_uuid(con_name=name) for name in con_names]

    def get_connection_uuid(self, con_name):
        """
        Gets a connection's UUID by the connection's name.

        Args:
            con_name (str): the connection's name.

        Returns:
            str: the connection's UUID.

        Raises:
            ConnectionDoesNotExistException: if a connection with the given
            name does not exist.
        """
        if self.is_connection_exist(connection=con_name):
            return self._exec_command(
                command=NMCLI_COMMAND.format(
                    options="-g connection.uuid",
                    object="connection",
                    command="show {con}".format(con=con_name),
                )
            ).strip()
        raise ConnectionDoesNotExistException(con_name)

    def get_device_type(self, device):
        """
        Gets the device type.

        Args:
            device (str): device name.

        Returns:
            str: the device type.

        Raises:
            CommandExecutionFailure: if the remote host returned a code
            indicating a failure in execution.
        """
        return self._exec_command(
            command=NMCLI_COMMAND.format(
                options="-g GENERAL.TYPE",
                object="device",
                command="show {device}".format(device=device),
            )
        ).strip()

    def set_connection_state(self, connection, state):
        """
        Sets a connection's state.

        Args:
            connection (str): name, UUID or path.
            state (str): the desired state.
                available states are: ["up", "down"].

        Raises:
            ConnectionDoesNotExistException: if a connection with the given
            name does not exist.
        """
        command = "nmcli connection {state} {con}".format(state=state, con=connection)  # noqa: E501
        if self.is_connection_exist(connection=connection):
            self._exec_command(command=command)
        else:
            raise ConnectionDoesNotExistException(connection)

    def add_ethernet(
        self,
        con_name,
        ifname,
        auto_connect=False,
        save=False,
        mac=None,
        mtu=None,
        ipv4_method=None,
        ipv4_addr=None,
        ipv4_gw=None,
        ipv6_method=None,
        ipv6_addr=None,
        ipv6_gw=None,
    ):
        """
        Creates an ETHERNET connection.

        Args:
            con_name (str): the created connection's name.
            ifname (str): the interface name to use.
            auto_connect (bool): True to connect automatically, or False for
                manual.
            save (bool): True to persist the connection, or False.
            mac (str): MAC address to set for the connection.
            mtu (int): MTU to set for the connection.
            ipv4_method (str): setting method.
                Available methods: auto, disabled, link-local, manual, shared.
            ipv4_addr (str): a static address.
            ipv4_gw (str): a gateway address.
            ipv6_method (str): setting method.
                Available methods: auto, dhcp, disabled, ignore, link-local,
                manual, shared.
            ipv6_addr (str): a static address.
            ipv6_gw (str): a gateway address.

        Raises:
            CommandExecutionFailure: if the remote host returned a code
                indicating a failure in execution.
            InvalidMACException: if an invalid MAC address was passed.
            InvalidIPException: if an invalid IP address was passed.
        """
        common_options = self._generate_common_options(
            con_type="ethernet",
            con_name=con_name,
            ifname=ifname,
            auto_connect=auto_connect,
            save=save,
        )

        command = NMCLI_CONNECTION_ADD + " " + common_options

        if mac:
            if not self._is_mac_valid(mac_address=mac):
                raise InvalidMACException(mac=mac)
            command += " mac {mac}".format(mac=mac)

        command += self._extend_add_command(
            ipv4_addr=ipv4_addr,
            ipv4_gw=ipv4_gw,
            ipv4_method=ipv4_method,
            ipv6_addr=ipv6_addr,
            ipv6_gw=ipv6_gw,
            ipv6_method=ipv6_method,
            mtu=mtu,
        )

        self._exec_command(command=command)

    def add_bond(
        self,
        con_name,
        ifname,
        mode=DEFAULT_BOND_MODE,
        miimon=DEFAULT_MIIMON,
        auto_connect=False,
        save=False,
        ipv4_method=None,
        ipv4_addr=None,
        ipv4_gw=None,
        ipv6_method=None,
        ipv6_addr=None,
        ipv6_gw=None,
    ):
        """
        Creates a bond connection.

        Args:
            con_name (str): the created connection's name.
            ifname (str): the created bond's name.
            mode (str): bond mode.
                Available modes are: balance-rr (0) | active-backup (1) |
                balance-xor (2) | broadcast (3)
                802.3ad (4) | balance-tlb (5) | balance-alb (6)
            miimon (int): specifies (in milliseconds) how often MII link
                monitoring occurs.
            auto_connect (bool): True to connect automatically, or False for
                manual.
            save (bool): True to persist the connection, or False.
            ipv4_method (str): setting method.
                Available methods: auto, disabled, link-local, manual, shared.
            ipv4_addr (str): a static address.
            ipv4_gw (str): a gateway address.
            ipv6_method (str): setting method.
                Available methods: auto, dhcp, disabled, ignore, link-local,
                manual, shared.
            ipv6_addr (str): a static address.
            ipv6_gw (str): a gateway address.

        Raises:
            CommandExecutionFailure: if the remote host returned a code
            indicating a failure in execution.

        Notes:
            The parameters [ipv4_addr, ipv4_gw, ipv6_addr, ipv6_gw] are to be
            used with a 'manual' IP method respectively.
        """
        common_options = self._generate_common_options(
            con_type="bond",
            con_name=con_name,
            ifname=ifname,
            auto_connect=auto_connect,
            save=save,
        )

        type_options = "mode {mode} miimon {miimon}".format(mode=mode, miimon=miimon)  # noqa: E501

        command = NMCLI_CONNECTION_ADD + " " + common_options + " " + type_options  # noqa: E501

        command += self._extend_add_command(
            ipv4_addr=ipv4_addr,
            ipv4_gw=ipv4_gw,
            ipv4_method=ipv4_method,
            ipv6_addr=ipv6_addr,
            ipv6_gw=ipv6_gw,
            ipv6_method=ipv6_method,
            mtu=0,
        )

        self._exec_command(command=command)

    def add_slave(self, con_name, ifname, master, auto_connect=False, save=False):  # noqa: E501
        """
        Creates a bond slave.

        Args:
            con_name (str): the created connection's name.
            ifname (str): the created bond's name.
            master (str): ifname, connection UUID or name.
            auto_connect (bool): True to connect automatically, or False for
                manual.
            save (bool): True to persist the connection, or False.

        Raises:
            CommandExecutionFailure: if the remote host returned a code
            indicating a failure in execution.
        """
        slave_type = self.get_device_type(device=ifname)

        common_options = self._generate_common_options(
            con_type=slave_type,
            con_name=con_name,
            ifname=ifname,
            auto_connect=auto_connect,
            save=save,
        )

        command = (
            NMCLI_CONNECTION_ADD
            + " "
            + common_options
            + " master {master}".format(master=master)
        )

        self._exec_command(command=command)

    def add_vlan(
        self,
        con_name,
        dev,
        vlan_id,
        auto_connect=False,
        save=False,
        mtu=None,
        ipv4_method=None,
        ipv4_addr=None,
        ipv4_gw=None,
        ipv6_method=None,
        ipv6_addr=None,
        ipv6_gw=None,
    ):
        """
        Creates a VLAN connection.

        Args:
            con_name (str): the created connection's name.
            dev (str): parent device.
            vlan_id (int): VLAN ID.
            auto_connect (bool): True to connect automatically, or False for
                manual.
            save (bool): True to persist the connection, or False.
            mtu (int): MTU to set for the connection.
            ipv4_method (str): setting method.
                Available methods: auto, disabled, link-local, manual, shared.
            ipv4_addr (str): a static address.
            ipv4_gw (str): a gateway address.
            ipv6_method (str): setting method.
                Available methods: auto, dhcp, disabled, ignore, link-local,
                manual, shared.
            ipv6_addr (str): a static address.
            ipv6_gw (str): a gateway address.

        Raises:
            CommandExecutionFailure: if the remote host returned a code
            indicating a failure in execution.
        """
        if not self.is_device_exist(device=dev):
            raise DeviceDoesNotExistException(dev)

        common_options = self._generate_common_options(
            con_type="vlan",
            con_name=con_name,
            ifname=dev,
            auto_connect=auto_connect,
            save=save,
        )

        command = (
            NMCLI_CONNECTION_ADD
            + " "
            + common_options
            + " dev {dev}".format(dev=dev)
            + " id {id}".format(id=vlan_id)
        )

        command += self._extend_add_command(
            ipv4_addr=ipv4_addr,
            ipv4_gw=ipv4_gw,
            ipv4_method=ipv4_method,
            ipv6_addr=ipv6_addr,
            ipv6_gw=ipv6_gw,
            ipv6_method=ipv6_method,
            mtu=mtu,
        )

        self._exec_command(command=command)

    def add_dummy(
        self,
        con_name,
        ifname,
        auto_connect=False,
        save=False,
        ipv4_method=None,
        ipv4_addr=None,
        ipv4_gw=None,
        ipv6_method=None,
        ipv6_addr=None,
        ipv6_gw=None,
    ):
        """
        Creates a dummy connection.

        Args:
            con_name (str): the created connection's name.
            ifname (str): the interface name to use.
            auto_connect (bool): True to connect automatically, or False for
                manual.
            save (bool): True to persist the connection, or False.
            ipv4_method (str): setting method.
                Available methods: auto, disabled, link-local, manual, shared.
            ipv4_addr (str): a static address.
            ipv4_gw (str): a gateway address.
            ipv6_method (str): setting method.
                Available methods: auto, dhcp, disabled, ignore, link-local,
                manual, shared.
            ipv6_addr (str): a static address.
            ipv6_gw (str): a gateway address.

        Raises:
            CommandExecutionFailure: if the remote host returned a code
            indicating a failure in execution.
        """
        common_options = self._generate_common_options(
            con_type="dummy",
            con_name=con_name,
            ifname=ifname,
            auto_connect=auto_connect,
            save=save,
        )

        command = NMCLI_CONNECTION_ADD + " " + common_options

        command += self._extend_add_command(
            ipv4_addr=ipv4_addr,
            ipv4_gw=ipv4_gw,
            ipv4_method=ipv4_method,
            ipv6_addr=ipv6_addr,
            ipv6_gw=ipv6_gw,
            ipv6_method=ipv6_method,
            mtu=0,
        )

        self._exec_command(command=command)

    def modify_connection(self, connection, properties):
        """
        Modifies a connection.

        Args:
            connection (str): name, UUID or path.
            properties (dict): properties mapping to values

        Raises:
            ConnectionDoesNotExistException: if a connection with the given
                name does not exist.
            CommandExecutionFailure: if the remote host returned a code
                indicating a failure in execution.

        Notes:
            For multi-value properties e.g: ipv4.addresses, it is possible to
            pass a property key with a '+' prefix to append a value e.g:
            {"+ipv4.addresses": "192.168.23.2"}, or a '-' in order to remove
            a property.
        """
        if not self.is_connection_exist(connection=connection):
            raise ConnectionDoesNotExistException(connection)

        command = "nmcli connection modify {con}".format(con=connection)

        for prop, val in properties.items():
            command += " " + prop + " " + val

        self._exec_command(command=command)

    def delete_connection(self, connection):
        """
        Deletes a connection.

        Args:
            connection (str): name, UUID or path.

        Raises:
            ConnectionDoesNotExistException: if a connection with the given
                name does not exist.
        """
        if self.is_connection_exist(connection=connection):
            self._exec_command(command=NMCLI_CONNECTION_DELETE.format(id=connection))  # noqa: E501
        else:
            raise ConnectionDoesNotExistException(connection)

    def _extend_add_command(
        self, ipv4_addr, ipv4_gw, ipv4_method, ipv6_addr, ipv6_gw, ipv6_method, mtu  # noqa: E501
    ):
        """
        Extends a connection adding command with optional parameters.

        Args:
            ipv4_addr (str): a static address.
            ipv4_gw (str): a gateway address.
            ipv4_method (str): setting method.
                Available methods: auto, disabled, link-local, manual, shared.
            ipv6_addr (str): a static address.
            ipv6_gw (str): a gateway address.
            ipv6_method (str): setting method.
                Available methods: auto, dhcp, disabled, ignore, link-local,
                manual, shared.
            mtu (int): MTU to set for the connection.

        Returns:
            str: an nmcli connection add command with the passed in optional
                parameters.
        """
        command = ""
        if mtu:
            command += " mtu {mtu}".format(mtu=mtu)
        if ipv4_addr:
            if not self._get_ip_version(ip_address=ipv4_addr) == 4:
                raise InvalidIPException(ip=ipv4_addr)
        if ipv4_gw:
            if not self._get_ip_version(ip_address=ipv4_gw) == 4:
                raise InvalidIPException(ip=ipv4_gw)
        if ipv6_addr:
            if not self._get_ip_version(ip_address=ipv6_addr) == 6:
                raise InvalidIPException(ip=ipv6_addr)
        if ipv6_gw:
            if not self._get_ip_version(ip_address=ipv6_gw) == 6:
                raise InvalidIPException(ip=ipv6_gw)
        if ipv4_method:
            command += " " + self._generate_ip_options(
                ip_method=ipv4_method, address=ipv4_addr, gateway=ipv4_gw, version=4  # noqa: E501
            )
        if ipv6_method:
            command += " " + self._generate_ip_options(
                ip_method=ipv6_method, address=ipv6_addr, gateway=ipv6_gw, version=6  # noqa: E501
            )
        return command

    @staticmethod
    def _generate_common_options(con_type, con_name, ifname, auto_connect, save):  # noqa: E501
        """
        Generates a string containing common options for the nmcli tool.

        Args:
            con_type (str): the connection type.
            con_name (str): the created connection's name.
            ifname (str): the interface name to use.
            auto_connect (bool): True to connect automatically, or False for
                manual.
            save (bool): True to persist the connection, or False.

        Returns:
            str: a common options string.
        """
        return COMMON_OPTIONS.format(
            type=con_type,
            con_name=con_name,
            ifname=ifname,
            auto_connect="yes" if auto_connect else "no",
            save="yes" if save else "no",
        )

    @staticmethod
    def _generate_ip_options(ip_method, address, gateway, version):
        """
        Generates a string containing ip options for the nmcli tool.

        Args:
            ip_method (str): setting method.
                Available methods: auto, disabled, link-local, manual, shared.
            address (str): a static address.
            gateway (str): a gateway address.
            version (int): IP version.

        Returns:
            str: an ip options string.
        """
        ip_options = ""

        if ip_method:
            ip_options += (
                IPV4_METHOD.format(method=ip_method)
                if version == 4
                else IPV6_METHOD.format(method=ip_method)
            )
            if ip_method == IP_MANUAL_METHOD:
                if address and gateway:
                    ip_options += " " + (
                        IPV4_STATIC.format(address=address, gateway=gateway)
                        if version == 4
                        else IPV6_STATIC.format(address=address, gateway=gateway)  # noqa: E501
                    )
        return ip_options

    @staticmethod
    def _is_mac_valid(mac_address):
        """
        Checks if a given MAC address is valid.

        Args:
            mac_address (str): MAC address.

        Returns:
            bool: True if the MAC address is valid, or False if not.
        """
        try:
            netaddr.EUI(addr=mac_address)
        except netaddr.AddrFormatError:
            return False
        return True

    @staticmethod
    def _is_ip_valid(ip_address):
        """
        Checks if a given IP address is valid.

        Args:
            ip_address (str): IP address.

        Returns:
            bool: True if the MAC address is valid, or False if not.
        """
        try:
            netaddr.IPAddress(addr=ip_address)
        except netaddr.AddrFormatError:
            return False
        return True

    def _get_ip_version(self, ip_address):
        """
        Gets the IP version of an IP address.

        Args:
            ip_address (str): IP address.

        Returns:
            int: the IP version.

        Raises:
            InvalidIPException: if the ip_address parameter does not represent
                a valid IP address.
        """
        if self._is_ip_valid(ip_address=ip_address):
            return netaddr.IPAddress(addr=ip_address).version


class ConnectionDoesNotExistException(GeneralResourceError):
    def __init__(self, con_name):
        super(ConnectionDoesNotExistException, self).__init__(con_name)
        self.con_name = con_name

    def __str__(self):
        return "connection {con} does not exist".format(con=self.con_name)


class DeviceDoesNotExistException(GeneralResourceError):
    def __init__(self, device):
        super(DeviceDoesNotExistException, self).__init__(device)
        self.device = device

    def __str__(self):
        return "device {dev} does not exist".format(dev=self.device)


class InvalidIPException(GeneralResourceError):
    def __init__(self, ip):
        super(InvalidIPException, self).__init__(ip)
        self.ip = ip

    def __str__(self):
        return "IP address {addr} is in-valid".format(addr=self.ip)


class InvalidMACException(GeneralResourceError):
    def __init__(self, mac):
        super(InvalidMACException, self).__init__(mac)
        self.mac = mac

    def __str__(self):
        return "MAC address {addr} is invalid".format(addr=self.mac)
