# -*- coding: utf-8 -*-
"""
Tests for the NMCLI service class.
"""
import pytest

from rrmngmnt import Host, RootUser
from rrmngmnt.errors import CommandExecutionFailure
from rrmngmnt.nmcli import (
    ConnectionDoesNotExistException,
    DeviceDoesNotExistException
)
from tests.common import FakeExecutorFactory

MOCK_ROOT_PASSWORD = "11111"

MOCK_IP = "1.1.1.1"


@pytest.fixture(scope="class")
def provision_host(request):
    """
    Provisions a mock host.
    """
    ip = getattr(request.cls, "host_ip")
    root_password = getattr(request.cls, "root_password")
    data = getattr(request.cls, "data")

    mock = Host(ip=ip)
    mock.add_user(RootUser(password=root_password))
    mock.executor_factory = FakeExecutorFactory(
        cmd_to_data=data, files_content=None
    )
    return mock


@pytest.fixture(scope="function")
def mock(provision_host):
    return provision_host


class NmcliBase(object):
    """
    Base class for tests
    """
    host_ip = MOCK_IP
    root_password = MOCK_ROOT_PASSWORD
    data = {}


class TestNmcliBasic(NmcliBase):
    """
    Testing basic scenarios for existing connections.
    """
    data = {
        "nmcli connection show ovirtmgmt": (
            0,
            "",
            ""
        ),
        "nmcli connection show ovirtmgmtt": (
            10,
            "",
            "Error: ovirtmgmtt - no such connection profile."
        ),
        "nmcli device show ovirtmgmt": (
            0,
            "",
            ""
        ),
        "nmcli device show ovirtmgmtt": (
            10,
            "",
            "Error: Device 'ovirtmgmtt' not found."
        ),
        "nmcli -g connection.uuid connection show ovirtmgmt": (
            0,
            "f142311f-9e79-4b9e-9d8a-f591e0cec44a",
            ""
        ),
        "nmcli -g connection.uuid connection show ovirtmgmtt": (
            10,
            "",
            "Error: ovirtmgmtt - no such connection profile"
        ),
        "nmcli -m multiline connection show": (
            0,
            "\n".join(
                [
                    "NAME:                                   ovirtmgmt",
                    "UUID:                                   f142311f-9e79-4b9e-9d8a-f591e0cec44a",  # noqa: E501
                    "TYPE:                                   bridge",
                    "DEVICE:                                 ovirtmgmt",
                    "NAME:                                   virbr0",
                    "UUID:                                   56d36466-2a58-4461-98ba-fbe11700955a",  # noqa: E501
                    "TYPE:                                   bridge",
                    "DEVICE:                                 virbr0",
                    "NAME:                                   enp8s0f0",
                    "UUID:                                   f58d1962-459d-47de-b090-55091dd3d702",  # noqa: E501
                    "TYPE:                                   ethernet",
                    "DEVICE:                                 enp8s0f0"
                ]
            ),
            ""
        ),
        "nmcli connection show virbr0": (
            0,
            "",
            ""
        ),
        "nmcli connection show enp8s0f0": (
            0,
            "",
            ""
        ),
        "nmcli -g connection.uuid connection show virbr0": (
            0,
            "56d36466-2a58-4461-98ba-fbe11700955a",
            ""
        ),
        "nmcli -g connection.uuid connection show enp8s0f0": (
            0,
            "f58d1962-459d-47de-b090-55091dd3d702",
            ""
        ),
        "nmcli -g GENERAL.TYPE device show enp8s0f0": (
            0,
            "ethernet",
            ""
        ),
        "nmcli -g GENERAL.TYPE device show enp8s0f00": (
            10,
            "",
            "Error: Device 'enp8s0f00' not found."
        ),
        "nmcli connection up ovirtmgmt": (
            0,
            "Connection successfully activated (D-Bus active path: /org/freedesktop/NetworkManager/ActiveConnection/1985)",  # noqa: E501
            ""
        ),
        "nmcli connection down ovirtmgmt": (
            0,
            "Connection successfully terminated (D-Bus active path: /org/freedesktop/NetworkManager/ActiveConnection/1985)",  # noqa: E501
            ""
        ),
        "nmcli connection up ovirtmgmtt": (
            10,
            "",
            "Error: unknown connection 'ovirtmgmtt'."
        ),
        "nmcli connection down ovirtmgmtt": (
            10,
            "",
            "Error: unknown connection 'ovirtmgmtt'."
        ),
        "nmcli connection delete ovirtmgmt": (
            0,
            "Connection successfully removed (D-Bus active path: /org/freedesktop/NetworkManager/ActiveConnection/1985)",  # noqa: E501
            ""
        ),
        "nmcli connection delete ovirtmgmtt": (
            10,
            "",
            "Error: unknown connection 'ovirtmgmtt'."
        ),
    }

    def test_check_connection_exists(self, mock):
        assert mock.network.nmcli.is_connection_exist(connection="ovirtmgmt")

    def test_check_connection_exists_when_it_does_not(self, mock):
        assert not mock.network.nmcli.is_connection_exist(
            connection="ovirtmgmtt"
        )

    def test_check_device_exists(self, mock):
        assert mock.network.nmcli.is_device_exist(device="ovirtmgmt")

    def test_check_device_exists_when_it_does_not(self, mock):
        assert not mock.network.nmcli.is_device_exist(device="ovirtmgmtt")

    def test_get_connection_uuid(self, mock):
        assert (
                mock.network.nmcli.get_connection_uuid(con_name="ovirtmgmt")
                == "f142311f-9e79-4b9e-9d8a-f591e0cec44a"
        )

    def test_get_non_existing_connection_uuid(self, mock):
        with pytest.raises(
            expected_exception=ConnectionDoesNotExistException,
            match="connection ovirtmgmtt does not exist"
        ):
            mock.network.nmcli.get_connection_uuid(
                con_name="ovirtmgmtt"
            )

    def test_get_all_existing_connections_uuids(self, mock):
        all_cons_uuids = mock.network.nmcli.get_all_connections_uuids()
        assert all_cons_uuids == [
            "f142311f-9e79-4b9e-9d8a-f591e0cec44a",
            "56d36466-2a58-4461-98ba-fbe11700955a",
            "f58d1962-459d-47de-b090-55091dd3d702"
        ]

    def test_get_device_type(self, mock):
        assert (
                mock.network.nmcli.get_device_type(device="enp8s0f0")
                == "ethernet"
        )

    def test_get_non_existing_device_type(self, mock):
        with pytest.raises(
            expected_exception=CommandExecutionFailure,
            match="Error: Device 'enp8s0f00' not found."
        ):
            mock.network.nmcli.get_device_type(device="enp8s0f00")

    def test_set_connection_up(self, mock):
        mock.network.nmcli.set_connection_state(
            connection="ovirtmgmt", state="up"
        )

    def test_set_connection_down(self, mock):
        mock.network.nmcli.set_connection_state(
            connection="ovirtmgmt", state="down"
        )

    def test_set_non_existing_connection_up(self, mock):
        with pytest.raises(
                expected_exception=ConnectionDoesNotExistException,
                match="connection ovirtmgmtt does not exist"
        ):
            mock.network.nmcli.set_connection_state(
                connection="ovirtmgmtt", state="up"
            )

    def test_set_non_existing_connection_down(self, mock):
        with pytest.raises(
                expected_exception=ConnectionDoesNotExistException,
                match="connection ovirtmgmtt does not exist"
        ):
            mock.network.nmcli.set_connection_state(
                connection="ovirtmgmtt", state="down"
            )

    def test_delete_connection(self, mock):
        mock.network.nmcli.delete_connection(connection="ovirtmgmt")

    def test_delete_non_existing_connection(self, mock):
        with pytest.raises(
                expected_exception=ConnectionDoesNotExistException,
                match="connection ovirtmgmtt does not exist"
        ):
            mock.network.nmcli.delete_connection(connection="ovirtmgmtt")


class NmcliConnectionType(NmcliBase):
    """
    Base class for testing different connection types.
    """
    def test_add_connection_defaults(self, mock):
        pass

    def test_add_connection_with_autoconnect(self, mock):
        pass

    def test_add_connection_with_save(self, mock):
        pass

    def test_add_connection_with_static_ips(self, mock):
        pass


class TestNmcliEthernetConnection(NmcliConnectionType):
    """
    Testing scenarios for ethernet type connections.
    """
    data = {
        (
            "nmcli connection add "
            "type ethernet con-name ethernet_con ifname enp8s0f0 "
            "autoconnect no save no"
        ): (
            0,
            "",
            ""
        ),
        (
            "nmcli connection add "
            "type ethernet con-name ethernet_con ifname enp8s0f0 "
            "autoconnect yes save no"
        ): (
            0,
            "",
            ""
        ),
        (
            "nmcli connection add "
            "type ethernet con-name ethernet_con ifname enp8s0f0 "
            "autoconnect no save yes"
        ): (
            0,
            "",
            ""
        ),
        (
            "nmcli connection add "
            "type ethernet con-name ethernet_con ifname enp8s0f0 "
            "autoconnect no save no "
            "ipv4.method manual ipv4.addresses 192.168.23.2 "
            "ipv4.gateway 192.168.23.254 "
            "ipv6.method manual ipv6.addresses 2a02:ed0:52fe:ec00:dc3f:f939:a573:5984/64 "  # noqa: E501
            "ipv6.gateway 2a02:ed0:52fe:ec00::/56"
        ): (
            0,
            "",
            ""
        ),
        (
            "nmcli connection add "
            "type ethernet con-name ethernet_con ifname enp8s0f0 "
            "autoconnect no save no "
            "mac e8:6a:64:7d:d3:b1"
        ): (
            0,
            "",
            ""
        ),
        (
            "nmcli connection add "
            "type ethernet con-name ethernet_con ifname enp8s0f0 "
            "autoconnect no save no "
            "mtu 1600"
        ): (
            0,
            "",
            ""
        ),
    }

    def test_add_connection_defaults(self, mock):
        mock.network.nmcli.add_ethernet(
            con_name="ethernet_con",
            ifname="enp8s0f0"
        )

    def test_add_connection_with_autoconnect(self, mock):
        mock.network.nmcli.add_ethernet(
            con_name="ethernet_con",
            ifname="enp8s0f0",
            auto_connect=True
        )

    def test_add_connection_with_save(self, mock):
        mock.network.nmcli.add_ethernet(
            con_name="ethernet_con",
            ifname="enp8s0f0",
            save=True
        )

    def test_add_connection_with_static_ips(self, mock):
        mock.network.nmcli.add_ethernet(
            con_name="ethernet_con",
            ifname="enp8s0f0",
            ipv4_method="manual",
            ipv4_addr="192.168.23.2",
            ipv4_gw="192.168.23.254",
            ipv6_method="manual",
            ipv6_addr="2a02:ed0:52fe:ec00:dc3f:f939:a573:5984/64",
            ipv6_gw="2a02:ed0:52fe:ec00::/56"
        )

    def test_add_ethernet_with_mac(self, mock):
        mock.network.nmcli.add_ethernet(
            con_name="ethernet_con",
            ifname="enp8s0f0",
            mac="e8:6a:64:7d:d3:b1"
        )

    def test_add_ethernet_with_mtu(self, mock):
        mock.network.nmcli.add_ethernet(
            con_name="ethernet_con",
            ifname="enp8s0f0",
            mtu=1600
        )


class TestNmcliBondConnection(NmcliConnectionType):
    """
    Testing scenarios for bond type connections.
    """
    data = {
        (
            "nmcli connection add "
            "type bond con-name bond_con ifname bond0 "
            "autoconnect no save no mode active-backup miimon 100"
        ): (
            0,
            "",
            ""
        ),
        (
            "nmcli connection add "
            "type bond con-name bond_con ifname bond0 "
            "autoconnect yes save no mode active-backup miimon 100"
        ): (
            0,
            "",
            ""
        ),
        (
            "nmcli connection add "
            "type bond con-name bond_con ifname bond0 "
            "autoconnect no save yes mode active-backup miimon 100"
        ): (
            0,
            "",
            ""
        ),
        (
            "nmcli connection add "
            "type bond con-name bond_con ifname bond0 "
            "autoconnect no save no mode active-backup miimon 100 "
            "ipv4.method manual ipv4.addresses 192.168.23.2 "
            "ipv4.gateway 192.168.23.254 "
            "ipv6.method manual ipv6.addresses 2a02:ed0:52fe:ec00:dc3f:f939:a573:5984/64 "  # noqa: E501
            "ipv6.gateway 2a02:ed0:52fe:ec00::/56"
        ): (
            0,
            "",
            ""
        ),
        (
            "nmcli connection add "
            "type bond con-name bond_con ifname bond0 "
            "autoconnect no save no mode balance-rr miimon 100"
        ): (
            0,
            "",
            ""
        ),
        (
            "nmcli connection add "
            "type bond con-name bond_con ifname bond0 "
            "autoconnect no save no mode active-backup miimon 100"
        ): (
            0,
            "",
            ""
        ),
        (
            "nmcli connection add "
            "type bond con-name bond_con ifname bond0 "
            "autoconnect no save no mode balance-xor miimon 100"
        ): (
            0,
            "",
            ""
        ),
        (
            "nmcli connection add "
            "type bond con-name bond_con ifname bond0 "
            "autoconnect no save no mode broadcast miimon 100"
        ): (
            0,
            "",
            ""
        ),
        (
            "nmcli connection add "
            "type bond con-name bond_con ifname bond0 "
            "autoconnect no save no mode 802.3ad miimon 100"
        ): (
            0,
            "",
            ""
        ),
        (
            "nmcli connection add "
            "type bond con-name bond_con ifname bond0 "
            "autoconnect no save no mode balance-tlb miimon 100"
        ): (
            0,
            "",
            ""
        ),
        (
            "nmcli connection add "
            "type bond con-name bond_con ifname bond0 "
            "autoconnect no save no mode balance-alb miimon 100"
        ): (
            0,
            "",
            ""
        ),
        (
            "nmcli connection add "
            "type bond con-name bond_con ifname bond0 "
            "autoconnect no save no mode active-backup miimon 50"
        ): (
            0,
            "",
            ""
        ),
    }

    def test_add_connection_defaults(self, mock):
        mock.network.nmcli.add_bond(
            con_name="bond_con",
            ifname="bond0"
        )

    def test_add_connection_with_autoconnect(self, mock):
        mock.network.nmcli.add_bond(
            con_name="bond_con",
            ifname="bond0",
            auto_connect=True
        )

    def test_add_connection_with_save(self, mock):
        mock.network.nmcli.add_bond(
            con_name="bond_con",
            ifname="bond0",
            save=True
        )

    def test_add_connection_with_static_ips(self, mock):
        mock.network.nmcli.add_bond(
            con_name="bond_con",
            ifname="bond0",
            ipv4_method="manual",
            ipv4_addr="192.168.23.2",
            ipv4_gw="192.168.23.254",
            ipv6_method="manual",
            ipv6_addr="2a02:ed0:52fe:ec00:dc3f:f939:a573:5984/64",
            ipv6_gw="2a02:ed0:52fe:ec00::/56"
        )

    @pytest.mark.parametrize(
        "bond_mode",
        [
            "balance-rr",
            "active-backup",
            "balance-xor",
            "broadcast",
            "802.3ad",
            "balance-tlb",
            "balance-alb"
        ]
    )
    def test_add_bond_with_mode(self, mock, bond_mode):
        mock.network.nmcli.add_bond(
            con_name="bond_con",
            ifname="bond0",
            mode=bond_mode
        )

    def test_add_bond_with_miimon(self, mock):
        mock.network.nmcli.add_bond(
            con_name="bond_con",
            ifname="bond0",
            miimon=50
        )


class TestNmcliSlaveConnection(NmcliConnectionType):
    """
    Testing scenarios for bond type connections.
    """
    data = {
        (
            "nmcli connection add "
            "type ethernet con-name bond0_slave ifname enp8s0f0 "
            "autoconnect no save no master bond0"
        ): (
            0,
            "",
            ""
        ),
        (
            "nmcli connection add "
            "type ethernet con-name bond0_slave ifname enp8s0f0 "
            "autoconnect yes save no master bond0"
        ): (
            0,
            "",
            ""
        ),
        (
            "nmcli connection add "
            "type ethernet con-name bond0_slave ifname enp8s0f0 "
            "autoconnect no save yes master bond0"
        ): (
            0,
            "",
            ""
        ),
        "nmcli -g GENERAL.TYPE device show enp8s0f0": (
            0,
            "ethernet",
            ""
        ),
    }

    def test_add_connection_defaults(self, mock):
        mock.network.nmcli.add_slave(
            con_name="bond0_slave",
            ifname="enp8s0f0",
            master="bond0"
        )

    def test_add_connection_with_autoconnect(self, mock):
        mock.network.nmcli.add_slave(
            con_name="bond0_slave",
            ifname="enp8s0f0",
            master="bond0",
            auto_connect=True
        )

    def test_add_connection_with_save(self, mock):
        mock.network.nmcli.add_slave(
            con_name="bond0_slave",
            ifname="enp8s0f0",
            master="bond0",
            save=True
        )


class TestNmcliVlanConnection(NmcliConnectionType):
    """
    Testing scenarios for VLAN type connections.
    """
    data = {
        (
            "nmcli connection add "
            "type vlan con-name vlan_con ifname enp8s0f0 "
            "autoconnect no save no "
            "dev enp8s0f0 id 163"
        ): (
            0,
            "",
            ""
        ),
        (
            "nmcli connection add "
            "type vlan con-name vlan_con ifname enp8s0f0 "
            "autoconnect yes save no "
            "dev enp8s0f0 id 163"
        ): (
            0,
            "",
            ""
        ),
        (
            "nmcli connection add "
            "type vlan con-name vlan_con ifname enp8s0f0 "
            "autoconnect no save yes "
            "dev enp8s0f0 id 163"
        ): (
            0,
            "",
            ""
        ),
        (
            "nmcli connection add "
            "type vlan con-name vlan_con ifname enp8s0f0 "
            "autoconnect no save no "
            "dev enp8s0f0 id 163 "
            "ipv4.method manual ipv4.addresses 192.168.23.2 "
            "ipv4.gateway 192.168.23.254 "
            "ipv6.method manual ipv6.addresses 2a02:ed0:52fe:ec00:dc3f:f939:a573:5984/64 "  # noqa: E501
            "ipv6.gateway 2a02:ed0:52fe:ec00::/56"
        ): (
            0,
            "",
            ""
        ),
        (
            "nmcli connection add "
            "type vlan con-name vlan_con ifname enp8s0f0 "
            "autoconnect no save no "
            "dev enp8s0f0 id 163 "
            "mtu 1600"
        ): (
            0,
            "",
            ""
        ),
        "nmcli device show enp8s0f0": (
            0,
            "ethernet",
            ""
        ),
        "nmcli device show enp8s0f00": (
            10,
            "",
            "Error: Device 'enp8s0f00' not found."
        ),
    }

    def test_add_connection_defaults(self, mock):
        mock.network.nmcli.add_vlan(
            con_name="vlan_con",
            dev="enp8s0f0",
            vlan_id=163
        )

    def test_add_connection_with_autoconnect(self, mock):
        mock.network.nmcli.add_vlan(
            con_name="vlan_con",
            dev="enp8s0f0",
            vlan_id=163,
            auto_connect=True
        )

    def test_add_connection_with_save(self, mock):
        mock.network.nmcli.add_vlan(
            con_name="vlan_con",
            dev="enp8s0f0",
            vlan_id=163,
            save=True
        )

    def test_add_connection_with_static_ips(self, mock):
        mock.network.nmcli.add_vlan(
            con_name="vlan_con",
            dev="enp8s0f0",
            vlan_id=163
        )

    def test_add_vlan_with_invalid_dev(self, mock):
        with pytest.raises(
            expected_exception=DeviceDoesNotExistException,
            match="device enp8s0f00 does not exist"
        ):
            mock.network.nmcli.add_vlan(
                con_name="vlan_con",
                dev="enp8s0f00",
                vlan_id=163
            )

    def test_add_vlan_with_mtu(self, mock):
        mock.network.nmcli.add_vlan(
            con_name="vlan_con",
            dev="enp8s0f0",
            vlan_id=163,
            mtu=1600
        )


class TestNmcliDummyConnection(NmcliConnectionType):
    """
    Testing scenarios for dummy type connections.
    """
    data = {
        (
            "nmcli connection add "
            "type dummy con-name dummy_con ifname dummy_0 "
            "autoconnect no save no"
        ): (
            0,
            "",
            ""
        ),
        (
            "nmcli connection add "
            "type dummy con-name dummy_con ifname dummy_0 "
            "autoconnect yes save no"
        ): (
            0,
            "",
            ""
        ),
        (
            "nmcli connection add "
            "type dummy con-name dummy_con ifname dummy_0 "
            "autoconnect no save yes"
        ): (
            0,
            "",
            ""
        ),
        (
            "nmcli connection add "
            "type dummy con-name dummy_con ifname dummy_0 "
            "autoconnect no save no "
            "ipv4.method manual ipv4.addresses 192.168.23.2 "
            "ipv4.gateway 192.168.23.254 "
            "ipv6.method manual ipv6.addresses 2a02:ed0:52fe:ec00:dc3f:f939:a573:5984/64 "  # noqa: E501
            "ipv6.gateway 2a02:ed0:52fe:ec00::/56"
        ): (
            0,
            "",
            ""
        ),
    }

    def test_add_connection_defaults(self, mock):
        mock.network.nmcli.add_dummy(
            con_name="dummy_con",
            ifname="dummy_0"
        )

    def test_add_connection_with_autoconnect(self, mock):
        mock.network.nmcli.add_dummy(
            con_name="dummy_con",
            ifname="dummy_0",
            auto_connect=True
        )

    def test_add_connection_with_save(self, mock):
        mock.network.nmcli.add_dummy(
            con_name="dummy_con",
            ifname="dummy_0",
            save=True
        )

    def test_add_connection_with_static_ips(self, mock):
        mock.network.nmcli.add_dummy(
            con_name="dummy_con",
            ifname="dummy_0",
            ipv4_method="manual",
            ipv4_addr="192.168.23.2",
            ipv4_gw="192.168.23.254",
            ipv6_method="manual",
            ipv6_addr="2a02:ed0:52fe:ec00:dc3f:f939:a573:5984/64",
            ipv6_gw="2a02:ed0:52fe:ec00::/56"
        )
