# -*- coding: utf-8 -*-
from subprocess import list2cmdline

import pytest

import rrmngmnt.package_manager as pm
from rrmngmnt import Host, User
from rrmngmnt.package_manager import PackageManagerProxy as PMProxy

from .common import FakeExecutorFactory

host_executor_factory = Host.executor_factory


def _extend_cmd(cmd, sudo, *args):
    cmd = list(cmd)
    if sudo:
        cmd.insert(0, "sudo")

    cmd.extend(args)
    return list2cmdline(cmd)


def extend_cmd(cmd, *args):
    return _extend_cmd(cmd, False, *args)


def sudo_extend_cmd(cmd, *args):
    return _extend_cmd(cmd, True, *args)


def _join_cmd(sudo, *args):
    cmd = []
    if sudo:
        cmd.append("sudo")

    for _cmd in args:
        cmd += list(_cmd)
    return list2cmdline(cmd)


def join_cmds(*args):
    return _join_cmd(False, *args)


def sudo_join_cmds(*args):
    return _join_cmd(True, *args)


def teardown_module():
    Host.executor_factory = host_executor_factory


def fake_cmd_data(cmd_to_data, files=None):
    Host.executor_factory = FakeExecutorFactory(cmd_to_data, files)


@pytest.mark.parametrize("sudo", [False, True])
class BasePackageManager(object):
    __test__ = False

    # Define manager in child class like 'dnf', 'yum', 'apt' or 'rpm'
    manager = None
    managers = PMProxy.managers

    packages = {
        "installed_1": "p-installed-1",
        "installed_2": "p-installed-2",
        "installed_3": "p-installed-3",
        "not_installed": "p-not-installed",
        "non_existing": "p-non-existing",
        "list": "p-installed-1\np-installed-2\np-installed-3\n",
        "pattern": "p-installed-(1|2)",
    }
    rc1 = (1, "", "")
    rc0 = (0, "", "")
    data = {}

    @classmethod
    def setup_class(cls):
        cls.set_base_data()
        if cls.manager:
            grep_xargs_command = (
                list(pm.PIPE_GREP_COMMAND_D) + ["'%s'" % cls.packages["pattern"]] + list(pm.PIPE_XARGS_COMMAND_D)
            )
            remove_pattern_cmd = join_cmds(
                cls.managers[cls.manager].list_command_d, grep_xargs_command, cls.managers[cls.manager].remove_command_d
            )
            sudo_remove_pattern_cmd = sudo_join_cmds(
                cls.managers[cls.manager].list_command_d, grep_xargs_command, cls.managers[cls.manager].remove_command_d
            )
            cls.data.update({
                remove_pattern_cmd: cls.rc0,
                sudo_remove_pattern_cmd: cls.rc0,
                extend_cmd(cls.managers[cls.manager].exist_command_d, cls.packages["installed_1"]): cls.rc0,
                extend_cmd(cls.managers[cls.manager].exist_command_d, cls.packages["installed_2"]): cls.rc0,
                extend_cmd(cls.managers[cls.manager].exist_command_d, cls.packages["installed_3"]): cls.rc0,
                extend_cmd(cls.managers[cls.manager].exist_command_d, cls.packages["not_installed"]): cls.rc1,
                extend_cmd(cls.managers[cls.manager].install_command_d, cls.packages["not_installed"]): cls.rc0,
                # for negative install test
                extend_cmd(cls.managers[cls.manager].exist_command_d, cls.packages["non_existing"]): cls.rc1,
                extend_cmd(cls.managers[cls.manager].install_command_d, cls.packages["non_existing"]): cls.rc1,
                extend_cmd(cls.managers[cls.manager].remove_command_d, cls.packages["installed_1"]): cls.rc0,
                extend_cmd(cls.managers[cls.manager].remove_command_d, cls.packages["installed_2"]): cls.rc0,
                extend_cmd(cls.managers[cls.manager].update_command_d, cls.packages["installed_1"]): cls.rc0,
                extend_cmd(
                    cls.managers[cls.manager].update_command_d,
                ): cls.rc0,
                extend_cmd(
                    cls.managers[cls.manager].list_command_d,
                ): (0, cls.packages["list"], ""),
                # For sudo tests.
                sudo_extend_cmd(cls.managers[cls.manager].exist_command_d, cls.packages["installed_1"]): cls.rc0,
                sudo_extend_cmd(cls.managers[cls.manager].exist_command_d, cls.packages["installed_2"]): cls.rc0,
                sudo_extend_cmd(cls.managers[cls.manager].exist_command_d, cls.packages["installed_3"]): cls.rc0,
                sudo_extend_cmd(cls.managers[cls.manager].exist_command_d, cls.packages["not_installed"]): cls.rc1,
                sudo_extend_cmd(cls.managers[cls.manager].install_command_d, cls.packages["not_installed"]): cls.rc0,
                # for negative install test
                sudo_extend_cmd(cls.managers[cls.manager].exist_command_d, cls.packages["non_existing"]): cls.rc1,
                sudo_extend_cmd(cls.managers[cls.manager].install_command_d, cls.packages["non_existing"]): cls.rc1,
                sudo_extend_cmd(cls.managers[cls.manager].remove_command_d, cls.packages["installed_1"]): cls.rc0,
                sudo_extend_cmd(cls.managers[cls.manager].remove_command_d, cls.packages["installed_2"]): cls.rc0,
                sudo_extend_cmd(cls.managers[cls.manager].update_command_d, cls.packages["installed_1"]): cls.rc0,
                sudo_extend_cmd(
                    cls.managers[cls.manager].update_command_d,
                ): cls.rc0,
                sudo_extend_cmd(
                    cls.managers[cls.manager].list_command_d,
                ): (0, cls.packages["list"], ""),
            })
        fake_cmd_data(cls.data)

    @classmethod
    def set_base_data(cls):
        for manager_ in cls.managers:
            rc = cls.rc1
            if manager_ == cls.manager:
                rc = cls.rc0

            for val in (["which"], ["sudo", "which"]):
                cls.data.update({
                    list2cmdline(val + [manager_]): rc,
                })

    @pytest.fixture(scope="class")
    def pm(sudo):
        h = Host("1.1.1.1")
        h.add_user(User("root", "11111"))
        h.executor(sudo=sudo)
        return h.package_manager

    def test_info_negative(self, pm, sudo):
        assert not pm.info(self.packages["not_installed"])

    def test_exist(self, pm, sudo):
        assert pm.exist(self.packages["installed_1"])

    def test_exist_negative(self, pm, sudo):
        assert not pm.exist(self.packages["not_installed"])

    def test_install_installed(self, pm, sudo):
        assert pm.install(self.packages["installed_1"])

    def test_install_new(self, pm, sudo):
        assert pm.install(self.packages["not_installed"])

    def test_install_negative(self, pm, sudo):
        assert not pm.install(self.packages["non_existing"])

    def test_remove(self, pm, sudo):
        assert pm.remove(self.packages["installed_1"])

    def test_remove_pattern(self, pm, sudo):
        assert pm.remove(self.packages["pattern"], pattern=True)

    def test_update(self, pm, sudo):
        assert pm.update([self.packages["installed_1"]])

    def test_update_all(self, pm, sudo):
        assert pm.update()

    def test_list(self, pm, sudo):
        assert pm.list_() == self.packages["list"].split("\n")


class TestYumPM(BasePackageManager):
    __test__ = True
    manager = "yum"


class TestRpmPM(BasePackageManager):
    __test__ = True
    manager = "rpm"


class TestDnfPM(BasePackageManager):
    __test__ = True
    manager = "dnf"


class TestAptPM(BasePackageManager):
    __test__ = True
    manager = "apt"
