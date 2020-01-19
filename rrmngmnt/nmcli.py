# -*- coding: utf-8 -*-
"""
This module introduces support for the nmcli command which is provided by
NetworkManager.
"""
import shlex

from rrmngmnt.errors import CommandExecutionFailure
from rrmngmnt.service import Service

ERROR_MSG_FORMAT = "command -> {command}\nRC -> {rc}\nOUT -> {out}\nERROR -> {err}"  # noqa: E501

NMCLI_COMMAND = "nmcli {options} {object} {command}"


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

    def get_all_connections(self):
        """
        Gets existing NetworkManager profiles details.

        Returns:
            list[dict]: each dict in the returned list represents a profile,
                and has the following keys:
                    - "name"
                    - "uuid"
                    - "type"
                    - "device"

        Raises:
            CommandExecutionFailure: if the remote host returned a code
            indicating a failure in execution.
        """
        cons = list()

        out = self._exec_command(command="nmcli -t con show")
        for line in out.splitlines():
            properties = line.split(":")
            cons.append(
                {
                    "name": properties[0],
                    "uuid": properties[1],
                    "type": properties[2],
                    "device": properties[3],
                }
            )

        return cons

    def get_all_devices(self):
        """
        Gets existing devices details.

        Returns:
            list[dict]: each dict in the returned list represents a device,
                and has the following keys:
                    - "name"
                    - "type"
                    - "mac"
                    - "mtu"
        """
        devices = list()
        con_names = [con.get("name") for con in self.get_all_connections()]

        for name in con_names:
            out = self._exec_command(
                command=(
                    "nmcli -e no "
                    "-g GENERAL.DEVICE,GENERAL.TYPE,GENERAL.HWADDR,GENERAL.MTU "  # noqa: E501
                    "dev show {con}"
                ).format(con=name)
            )
            properties = out.splitlines()
            devices.append(
                {
                    "name": properties[0],
                    "type": properties[1],
                    "mac": properties[2],
                    "mtu": properties[3],
                }
            )

        return devices

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
            command="nmcli -g GENERAL.TYPE device show {dev}".format(dev=device)  # noqa: E501
        ).strip()

    def set_connection_state(self, connection, state):
        """
        Sets a connection's state.

        Args:
            connection (str): name, UUID or path.
            state (str): the desired state.
                available states are: ["up", "down"].

        Raises:
            CommandExecutionFailure: if the remote host returned a code
            indicating a failure in execution.
        """
        self._exec_command(
            command="nmcli connection {state} {con}".format(state=state, con=connection)  # noqa: E501
        )

    def add_ethernet_connection(
        self,
        con_name,
        ifname,
        auto_connect=None,
        save=None,
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
        """
        type_options = {}
        if mac:
            type_options["mac"] = mac
        if mtu:
            type_options["mtu"] = mtu

        command = self._nmcli_con_cmd_builder(
            operation="add",
            con_type="ethernet",
            con_name=con_name,
            ifname=ifname,
            auto_connect=auto_connect,
            save=save,
            ipv4_method=ipv4_method,
            ipv4_addr=ipv4_addr,
            ipv4_gw=ipv4_gw,
            ipv6_method=ipv6_method,
            ipv6_addr=ipv6_addr,
            ipv6_gw=ipv6_gw,
            type_options=type_options,
        )

        self._exec_command(command=command)

    def add_bond(
        self,
        con_name,
        ifname,
        mode=None,
        miimon=None,
        auto_connect=None,
        save=None,
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
        type_options = {}
        if mode:
            type_options["mode"] = mode
        if miimon:
            type_options["miimon"] = miimon

        command = self._nmcli_con_cmd_builder(
            operation="add",
            con_type="bond",
            con_name=con_name,
            ifname=ifname,
            auto_connect=auto_connect,
            save=save,
            ipv4_method=ipv4_method,
            ipv4_addr=ipv4_addr,
            ipv4_gw=ipv4_gw,
            ipv6_method=ipv6_method,
            ipv6_addr=ipv6_addr,
            ipv6_gw=ipv6_gw,
            type_options=type_options,
        )

        self._exec_command(command=command)

    def add_slave(self, con_name, ifname, master, auto_connect=None, save=None):  # noqa: E501
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
        type_options = {"master": master}

        command = self._nmcli_con_cmd_builder(
            operation="add",
            con_type=slave_type,
            con_name=con_name,
            ifname=ifname,
            auto_connect=auto_connect,
            save=save,
            type_options=type_options,
        )

        self._exec_command(command=command)

    def add_vlan(
        self,
        con_name,
        dev,
        vlan_id,
        mtu=None,
        auto_connect=None,
        save=None,
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
            mtu (int): MTU to set for the connection.
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
        type_options = {"dev": dev, "id": vlan_id}
        if mtu:
            type_options["mtu"] = mtu

        command = self._nmcli_con_cmd_builder(
            operation="add",
            con_type="vlan",
            con_name=con_name,
            ifname=dev,
            auto_connect=auto_connect,
            save=save,
            ipv4_method=ipv4_method,
            ipv4_addr=ipv4_addr,
            ipv4_gw=ipv4_gw,
            ipv6_method=ipv6_method,
            ipv6_addr=ipv6_addr,
            ipv6_gw=ipv6_gw,
            type_options=type_options,
        )

        self._exec_command(command=command)

    def add_dummy(
        self,
        con_name,
        ifname,
        auto_connect=None,
        save=None,
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
        command = self._nmcli_con_cmd_builder(
            operation="add",
            con_type="dummy",
            con_name=con_name,
            ifname=ifname,
            auto_connect=auto_connect,
            save=save,
            ipv4_method=ipv4_method,
            ipv4_addr=ipv4_addr,
            ipv4_gw=ipv4_gw,
            ipv6_method=ipv6_method,
            ipv6_addr=ipv6_addr,
            ipv6_gw=ipv6_gw,
        )

        self._exec_command(command=command)

    def modify_connection(self, connection, properties):
        """
        Modifies a connection.

        Args:
            connection (str): name, UUID or path.
            properties (dict): properties mapping to values

        Raises:
            CommandExecutionFailure: if the remote host returned a code
                indicating a failure in execution.

        Notes:
            For multi-value properties e.g: ipv4.addresses, it is possible to
            pass a property key with a '+' prefix to append a value e.g:
            {"+ipv4.addresses": "192.168.23.2"}, or a '-' in order to remove
            a property.
        """
        command = self._nmcli_con_cmd_builder(
            operation="modify", con_name=connection, type_options=properties
        )

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
        command = self._nmcli_con_cmd_builder(operation="delete", con_name=connection)  # noqa: E501

        self._exec_command(command=command)

    def modify_device(self, device, properties):
        """
        Modifies a connection.

        Args:
            device (str): device name.
            properties (dict): properties mapping to values

        Raises:
            CommandExecutionFailure: if the remote host returned a code
                indicating a failure in execution.

        Notes:
            For multi-value properties e.g: ipv4.addresses, it is possible to
            pass a property key with a '+' prefix to append a value e.g:
            {"+ipv4.addresses": "192.168.23.2"}, or a '-' in order to remove
            a property.
        """
        command = "nmcli dev modify {device}".format(device=device)

        for k, v in properties.items():
            command += " {k} {v}".format(k=k, v=v)

        self._exec_command(command=command)

    @staticmethod
    def _ip_options_builder(
        ipv4_addr, ipv4_gw, ipv4_method, ipv6_addr, ipv6_gw, ipv6_method
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

        Returns:
            str: an nmcli connection add command with the passed in optional
                parameters.
        """
        command = ""

        if ipv4_method:
            command += " ipv4.method {method}".format(method=ipv4_method)
        if ipv6_method:
            command += " ipv6.method {method}".format(method=ipv6_method)
        if ipv4_addr:
            command += " ipv4.addresses {ipv4_addr}".format(ipv4_addr=ipv4_addr)  # noqa: E501
        if ipv4_gw:
            command += " ipv4.gateway {ipv4_gw}".format(ipv4_gw=ipv4_gw)
        if ipv6_addr:
            command += " ipv6.addresses {ipv6_addr}".format(ipv6_addr=ipv6_addr)  # noqa: E501
        if ipv6_gw:
            command += " ipv6.gateway {ipv6_gw}".format(ipv6_gw=ipv6_gw)
        return command

    @staticmethod
    def _common_options_builder(
        con_type, con_name, ifname, auto_connect=None, save=None
    ):
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
        common_options = (
            "type {type} " "con-name {con_name} " "ifname {ifname} "
        ).format(type=con_type, con_name=con_name, ifname=ifname)
        if auto_connect is not None:
            common_options += "autoconnect {val}".format(
                val="yes" if auto_connect is True else "no"
            )
        if save is not None:
            common_options += "save {val}".format(val="yes" if save is True else "no")  # noqa: E501

        return common_options

    def _nmcli_con_cmd_builder(
        self,
        operation,
        con_name,
        con_type=None,
        ifname=None,
        auto_connect=None,
        save=None,
        ipv4_method=None,
        ipv4_addr=None,
        ipv4_gw=None,
        ipv6_method=None,
        ipv6_addr=None,
        ipv6_gw=None,
        type_options=None,
    ):
        """
        Builds an nmcli command.

        Args:
            operation (str): the operation to perform. e.g: "add", "delete" ...
            con_name (str): the created connection's name.
            con_type (str): the connection type. e.g: "ethernet", "bond" ...
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
            type_options (dict): type specific options. e.g: {"mtu": "1500"}.

        Returns:
            str: an nmcli command.
        """
        command = "nmcli con {operation}".format(operation=operation, con=con_name)  # noqa: E501

        if operation == "delete":
            command += " {con}".format(con=con_name)

        elif operation == "modify":
            command += " {con}".format(con=con_name)
            if type_options:
                for k, v in type_options.items():
                    command += " {k} {v}".format(k=k, v=v)

        elif operation == "add":
            command += " {common}".format(
                common=self._common_options_builder(
                    con_type=con_type,
                    con_name=con_name,
                    ifname=ifname,
                    auto_connect=auto_connect,
                    save=save,
                )
            )

            if type_options:
                for k, v in type_options.items():
                    command += " {k} {v}".format(k=k, v=v)

            command += self._ip_options_builder(
                ipv4_addr=ipv4_addr,
                ipv4_gw=ipv4_gw,
                ipv4_method=ipv4_method,
                ipv6_addr=ipv6_addr,
                ipv6_gw=ipv6_gw,
                ipv6_method=ipv6_method,
            )

        return command
