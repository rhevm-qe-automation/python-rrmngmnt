# -*- coding: utf8 -*-
from rrmngmnt import Host
from .common import FakeExecutor


def fake_cmd_data(cmd_to_data):
    def executor(self, user=None):
        e = FakeExecutor(user)
        e.cmd_to_data = cmd_to_data.copy()
        return e
    Host.executor = executor


class TestStorage(object):
    data = {
        '/mount/positive': '/tmp/mnt_point',
        '/mount/negative': None,
        '/umount/positive': True,
        '/umount/negative': False,
        ('vg_name_pos', 'lv_name_pos'): True,
        ('vg_name_neg', 'lv_name_neg'): False,
    }

    @classmethod
    def setup_class(cls):
        fake_cmd_data(cls.data)

    def get_host(self, ip='1.1.1.1'):
        return Host(ip)

    def test_mount_positive(self):
        assert self.get_host().nfs.mount('/full/path/source')

    def test_mount_negative(self):
        assert not self.get_host().nfs.mount('/mount/negative')

    def test_umount_positive(self):
        assert self.get_host().nfs.umount('/umount/positive')

    def test_umount_negative(self):
        assert not self.get_host().nfs.umount('/umount/negative')

    def test_lvchange_positive(self):
        assert self.get_host().lvm.lvchange('vg_name_pos', 'lv_name_pos')

    def test_lvchange_negative(self):
        assert not self.get_host().lvm.lvchange('vg_name_neg', 'lv_name_neg')

    def test_pvscan_positive(self):
        assert self.get_host().lvm.pvscan()
