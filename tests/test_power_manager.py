import pytest

from rrmngmnt import Host, User, power_manager

from .common import FakeExecutorFactory

PM_TYPE = "lanplus"
PM_ADDRESS = "test-mgmt.test"
PM_USER = "test-user"
PM_PASSWORD = "test-password"
IPMI_COMMAND = ("ipmitool -I {pm_type} -H {pm_address} -U {pm_user} -P {pm_password} power").format(
    pm_type=PM_TYPE, pm_address=PM_ADDRESS, pm_user=PM_USER, pm_password=PM_PASSWORD
)

host_executor_factory = Host.executor_factory


def teardown_module():
    Host.executor_factory = host_executor_factory


def fake_cmd_data(cmd_to_data, files=None):
    Host.executor_factory = FakeExecutorFactory(cmd_to_data, files)


class TestPowerManager(object):
    data = {
        "reboot": (0, "", ""),
        "poweroff": (0, "", ""),
        "true": (0, "", ""),
        "{0} status".format(IPMI_COMMAND): (0, "", ""),
        "{0} reset".format(IPMI_COMMAND): (0, "", ""),
        "{0} on".format(IPMI_COMMAND): (0, "", ""),
        "{0} off".format(IPMI_COMMAND): (0, "", ""),
    }

    @classmethod
    def setup_class(cls):
        fake_cmd_data(cls.data)

    @classmethod
    def get_host(cls):
        h = Host("1.1.1.1")
        h.add_user(User("root", "123456"))
        return h


class TestSSHPowerManager(TestPowerManager):
    @pytest.fixture(scope="class")
    def ssh_power_manager(cls):
        host = cls.get_host()
        host.add_power_manager(pm_type=power_manager.SSH_TYPE)
        return host.get_power_manager(pm_type=power_manager.SSH_TYPE)

    def test_reboot_positive(self, ssh_power_manager):
        ssh_power_manager.restart()

    def test_poweroff_positive(self, ssh_power_manager):
        ssh_power_manager.poweroff()

    def test_status_positive(self, ssh_power_manager):
        ssh_power_manager.status()

    def test_poweron_negative(self, ssh_power_manager):
        with pytest.raises(NotImplementedError):
            ssh_power_manager.poweron()


class TestIPMIPowerManager(TestPowerManager):
    @staticmethod
    def fake_exec_pm_command():
        def exec_pm_command(self, command, *args):
            t_command = list(command)
            t_command = self.binary + t_command
            t_command += args
            self.host.executor().run_cmd(t_command)

        power_manager.IPMIPowerManager._exec_pm_command = exec_pm_command

    @classmethod
    def setup_class(cls):
        super(TestIPMIPowerManager, cls).setup_class()
        cls.fake_exec_pm_command()

    @pytest.fixture(scope="class")
    def ipmi_power_manager(cls):
        pm_user = User(name=PM_USER, password=PM_PASSWORD)
        ipmi_init_params = {"pm_if_type": PM_TYPE, "pm_address": PM_ADDRESS, "user": pm_user}
        host = cls.get_host()
        host.add_power_manager(pm_type=power_manager.IPMI_TYPE, **ipmi_init_params)
        return host.get_power_manager(pm_type=power_manager.IPMI_TYPE)

    def test_reboot_positive(self, ipmi_power_manager):
        ipmi_power_manager.restart()

    def test_poweroff_positive(self, ipmi_power_manager):
        ipmi_power_manager.poweroff()

    def test_status_positive(self, ipmi_power_manager):
        ipmi_power_manager.status()

    def test_poweron_positive(self, ipmi_power_manager):
        ipmi_power_manager.poweron()
