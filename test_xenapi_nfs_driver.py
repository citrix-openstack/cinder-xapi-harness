from cinder.volume.drivers.xenapi import lib as xenapi_nfs_driver
from cinder.volume.drivers.xenapi import tools
import unittest
import os
import params
import subprocess
import contextlib
import time


@contextlib.contextmanager
def temporary_vdi(session):
    pool_ref = session.pool.get_all()[0]
    sr_ref = session.pool.get_default_SR(pool_ref)
    vdi_ref = session.VDI.create(sr_ref, 1, 'User')
    try:
        yield vdi_ref
    finally:
        session.VDI.destroy(vdi_ref)


@contextlib.contextmanager
def temporary_vbd(session):
    vm_uuid = tools.get_this_vm_uuid()
    vm_ref = session.VM.get_by_uuid(vm_uuid)
    with temporary_vdi(session) as vdi_ref:
        vbd_ref = session.VBD.create(vm_ref, vdi_ref,
            userdevice='autodetect', bootable=False, mode='RO',
            type='disk', empty=False, other_config=dict())
        try:
            yield vbd_ref
        finally:
            try:
                session.VBD.unplug(vbd_ref)
            except:
                pass
            session.VBD.destroy(vbd_ref)


class TestSessionFactory(unittest.TestCase):
    def test_exception_raised_if_session_is_used_after_closed(self):
        sessionFactory = xenapi_nfs_driver.SessionFactory(
            params.xapi_url,
            params.xapi_user,
            params.xapi_pass
        )
        session = sessionFactory.get_session()

        session.SR.get_all()

        session.close()

        with self.assertRaises(xenapi_nfs_driver.XenAPIException):
            session.SR.get_all()


class XenAPISessionBased(unittest.TestCase):
    def setUp(self):
        self.sessionFactory = xenapi_nfs_driver.SessionFactory(
            params.xapi_url,
            params.xapi_user,
            params.xapi_pass
        )
        self.session = self.sessionFactory.get_session()
        self.disconnect_all_nfs_srs()
        self.host_ref = self.session.get_this_host()
        self.host_uuid = self.session.host.get_uuid(self.host_ref)
        self.assertFalse(self.session.get_pool())

    def tearDown(self):
        self.session.close()

    def disconnect_all_nfs_srs(self):
        for sr_ref in self.session.SR.get_all():
            if self.session.is_nfs_sr(sr_ref):
                self.session.unplug_pbds_and_forget_sr(sr_ref)

    def filenames_on_export(self):
        return set(os.listdir(params.exported_catalog))


class DiskOperationsTest(XenAPISessionBased):
    def tearDown(self):
        self.detach_destroy_extra_disks()
        super(DiskOperationsTest, self).tearDown()

    def detach_destroy_extra_disks(self):
        session = self.session
        vm_uuid = tools.get_this_vm_uuid()
        vm_ref = session.VM.get_by_uuid(vm_uuid)
        for vbd_ref in session.VM.get_vbds(vm_ref):
            if session.VBD.get_device(vbd_ref) == "xvda":
                continue
            vdi_ref = session.VBD.get_vdi(vbd_ref)
            session.VBD.unplug(vbd_ref)
            session.VBD.destroy(vbd_ref)
            session.VDI.destroy(vdi_ref)

    def test_get_default_sr(self):
        session = self.session
        pool_ref = session.pool.get_all()[0]
        sr_ref = session.pool.get_default_SR(pool_ref)
        self.assertTrue(bool(sr_ref))

    def test_create_vdi(self):
        session = self.session
        pool_ref = session.pool.get_all()[0]
        sr_ref = session.pool.get_default_SR(pool_ref)
        vdi_ref = session.VDI.create(sr_ref, 1, 'User')
        self.assertTrue(bool(vdi_ref))
        session.VDI.destroy(vdi_ref)

    def test_get_uuid(self):
        machine_uuid = tools.get_this_vm_uuid()
        self.assertTrue(bool(machine_uuid))

    def test_create_vbd(self):
        session = self.session
        vm_uuid = tools.get_this_vm_uuid()
        vm_ref = session.VM.get_by_uuid(vm_uuid)
        with temporary_vdi(session) as vdi_ref:
            vbd_ref = session.VBD.create(vm_ref, vdi_ref,
                userdevice='autodetect', bootable=False, mode='RW',
                type='disk', empty=False, other_config=dict())
            session.VBD.destroy(vbd_ref)

    def test_get_device(self):
        session = self.session
        with temporary_vbd(session) as vbd_ref:
            device = session.VBD.get_device(vbd_ref)
            self.assertFalse(bool(device))
            session.VBD.plug(vbd_ref)
            device = session.VBD.get_device(vbd_ref)
            self.assertEquals('xvdb', device)

    def test_get_vdi(self):
        session = self.session
        vm_uuid = tools.get_this_vm_uuid()
        vm_ref = session.VM.get_by_uuid(vm_uuid)
        with temporary_vdi(session) as vdi_ref:
            vbd_ref = session.VBD.create(vm_ref, vdi_ref,
                userdevice='autodetect', bootable=False, mode='RW',
                type='disk', empty=False, other_config=dict())

            self.assertEquals(vdi_ref, session.VBD.get_vdi(vbd_ref))


class XenAPISessionTest(XenAPISessionBased):
    def test_new_sr_on_nfs_connects_an_sr_and_disconnects(self):
        session = self.session
        number_of_srs_before = len(session.SR.get_all())

        with session.new_sr_on_nfs(self.host_ref, params.nfs_server,
                                  params.nfs_serverpath):
            self.assertEquals(
                number_of_srs_before + 1,
                len(session.SR.get_all()))

        self.assertEquals(
            number_of_srs_before,
            len(session.SR.get_all()))

    def test_sr_name_and_desc(self):
        session = self.session

        with session.new_sr_on_nfs(self.host_ref, params.nfs_server,
                                  params.nfs_serverpath,
                                  'name', 'desc') as sr_ref:
            name = session.SR.get_name_label(sr_ref)
            desc = session.SR.get_name_description(sr_ref)

        self.assertEquals('name', name)
        self.assertEquals('desc', desc)


    def test_sr_directory_is_not_removed(self):
        session = self.session

        filenames_before = self.filenames_on_export()

        with session.new_sr_on_nfs(self.host_ref, params.nfs_server,
                                  params.nfs_serverpath) as sr_ref:
            uuid = session.SR.get_uuid(sr_ref)

        filenames_after = self.filenames_on_export()

        self.assertEquals([uuid], list(filenames_after - filenames_before))

    def test_vdi_create_does_not_introduce_vdi(self):
        session = self.session

        vdi_list = session.VDI.get_all()

        with session.new_sr_on_nfs(self.host_ref, params.nfs_server,
                                  params.nfs_serverpath) as sr_ref:
            vdi_ref = session.create_new_vdi(sr_ref, 1)
            self.assertEquals(
                set(vdi_list + [vdi_ref]), set(session.VDI.get_all()))

        self.assertEquals(vdi_list, session.VDI.get_all())

    def test_re_attach_an_sr(self):
        session = self.session

        with session.new_sr_on_nfs(self.host_ref, params.nfs_server,
                                  params.nfs_serverpath) as sr_ref:
            sr_uuid = session.SR.get_uuid(sr_ref)
            sr_count = len(session.SR.get_all())
            pbd_count = len(session.PBD.get_all())

        sr_ref = session.plug_nfs_sr(
            self.host_ref, params.nfs_server, params.nfs_serverpath, sr_uuid,
            'name', 'desc')

        self.assertEquals(sr_count, len(session.SR.get_all()))
        self.assertEquals(pbd_count, len(session.PBD.get_all()))
        self.assertEquals('name', session.SR.get_name_label(sr_ref))
        self.assertEquals('desc', session.SR.get_name_description(sr_ref))


class NFSBasedVolumeOperationsTest(XenAPISessionBased):
    def setUp(self):
        super(NFSBasedVolumeOperationsTest, self).setUp()
        self.driver = xenapi_nfs_driver.NFSBasedVolumeOperations(self.sessionFactory)

    def test_create_a_new_nfs_backed_volume_returns_sr_uuid(self):
        driver = self.driver

        volume_details = driver.create_volume(
            params.nfs_server, params.nfs_serverpath, 1)

        self.assertIn(
            volume_details['sr_uuid'],
            os.listdir(params.exported_catalog)
        )

    def test_create_a_new_nfs_backed_volume_returns_vdi_uuid(self):
        driver = self.driver

        volume_details = driver.create_volume(
            params.nfs_server, params.nfs_serverpath, 1)

        self.assertIn(
            volume_details['vdi_uuid'] + ".vhd",
            os.listdir(
                os.path.join(
                    params.exported_catalog,
                    volume_details['sr_uuid']))
        )

    def test_re_attach_an_nfs_backed_volume_increases_number_of_vdis_srs(self):
        driver = self.driver

        original_number_of_srs = len(self.session.SR.get_all())
        original_number_of_vdis = len(self.session.VDI.get_all())

        volume_details = driver.create_volume(
            params.nfs_server, params.nfs_serverpath, 1)

        driver.connect_volume(params.nfs_server,
                              params.nfs_serverpath, **volume_details)

        self.assertEquals(
            original_number_of_srs + 1,
            len(self.session.SR.get_all()))

        self.assertEquals(
            original_number_of_vdis + 1,
            len(self.session.VDI.get_all()))

    def test_disconnect_a_volume(self):
        driver = self.driver

        original_number_of_srs = len(self.session.SR.get_all())
        original_number_of_vdis = len(self.session.VDI.get_all())

        volume_details = driver.create_volume(
            params.nfs_server, params.nfs_serverpath, 1)

        vdi_uuid = driver.connect_volume(params.nfs_server,
                                        params.nfs_serverpath, **volume_details)

        driver.disconnect_volume(vdi_uuid)

        self.assertEquals(
            original_number_of_srs,
            len(self.session.SR.get_all()))

        self.assertEquals(
            original_number_of_vdis,
            len(self.session.VDI.get_all()))


class DeleteVolumeTest(XenAPISessionBased):
    def setUp(self):
        super(DeleteVolumeTest, self).setUp()
        self.driver = xenapi_nfs_driver.NFSBasedVolumeOperations(self.sessionFactory)

    def count_filenames_on_export(self):
        return len(self.filenames_on_export())

    def test_delete_volume_removes_sr_directory(self):
        volume_details = self.driver.create_volume(
            params.nfs_server, params.nfs_serverpath, 1)

        filecount = self.count_filenames_on_export()

        self.driver.delete_volume(
            params.nfs_server, params.nfs_serverpath, **volume_details)

        self.assertEquals(filecount - 1, self.count_filenames_on_export())


class CopyVolumeTest(XenAPISessionBased):
    def setUp(self):
        super(CopyVolumeTest, self).setUp()
        self.driver = xenapi_nfs_driver.NFSBasedVolumeOperations(self.sessionFactory)

    def count_filenames_on_export(self):
        return len(self.filenames_on_export())

    def test_copy_creates_new_file(self):
        src_vol = self.driver.create_volume(
            params.nfs_server, params.nfs_serverpath, 1)

        file_count = self.count_filenames_on_export()

        dst_vol = self.driver.copy_volume(
            params.nfs_server, params.nfs_serverpath, **src_vol)

        new_file_count = self.count_filenames_on_export()

        self.assertTrue(new_file_count == file_count + 1)
        self.assertTrue(src_vol['sr_uuid'] != dst_vol['sr_uuid'])
        self.assertTrue(src_vol['vdi_uuid'] != dst_vol['vdi_uuid'])


class CallPluginTest(XenAPISessionBased):
    def test_call_echo_plugin(self):
        args = dict(foo="bar")

        host_ref = self.session.get_this_host()
        result = self.session.call_plugin(host_ref, 'echo', 'main', args)

        self.assertEquals("args were: %s" % repr(args), result)

    def test_bad_plugin_call(self):
        args = dict(foo="bar")

        host_ref = self.session.get_this_host()
        with self.assertRaises(xenapi_nfs_driver.XenAPIException):
            self.session.call_plugin(host_ref, 'nonexisting', 'xxx', args)


class ResizeTest(XenAPISessionBased):
    def setUp(self):
        super(ResizeTest, self).setUp()
        self.driver = xenapi_nfs_driver.NFSBasedVolumeOperations(self.sessionFactory)

    def get_size_of_vhd(self, vol):
        path_to_vhd = os.path.join(params.exported_catalog, vol['sr_uuid'], vol['vdi_uuid'] + '.vhd')
        self.assertTrue(os.path.exists(path_to_vhd))

        cmdline = "vhd-util query -n %s -v" % path_to_vhd
        args = cmdline.split()
        proc = subprocess.Popen(args, stdout=subprocess.PIPE)

        out, err = proc.communicate()

        return out.strip()

    def test_resize(self):
        vol = self.driver.create_volume(
            params.nfs_server, params.nfs_serverpath, 1)

        self.assertEquals('1024', self.get_size_of_vhd(vol))

        self.driver.resize_volume(
            params.nfs_server, params.nfs_serverpath, **dict(size_in_gigabytes=2, **vol))

        self.assertEquals('2048', self.get_size_of_vhd(vol))


class VolumeAttachedHereTest(XenAPISessionBased):
    def setUp(self):
        super(VolumeAttachedHereTest, self).setUp()
        self.driver = xenapi_nfs_driver.NFSBasedVolumeOperations(self.sessionFactory)

    def test_attach_a_volume_here(self):
        vol = self.driver.create_volume(
            params.nfs_server, params.nfs_serverpath, 1)
        vm_uuid = tools.get_this_vm_uuid()
        vm_ref = self.session.VM.get_by_uuid(vm_uuid)

        originally_attached_vbds = self.session.VM.get_vbds(vm_ref)

        with self.driver.volume_attached_here(params.nfs_server, params.nfs_serverpath, **vol) as blockdev:
            self.assertTrue(os.path.exists(blockdev))
            attached_vbds = self.session.VM.get_vbds(vm_ref)
            self.assertEquals(len(originally_attached_vbds) + 1, len(attached_vbds))

        attached_vbds_after = self.session.VM.get_vbds(vm_ref)
        self.assertEquals(originally_attached_vbds, attached_vbds_after)
