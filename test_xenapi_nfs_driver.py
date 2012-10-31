import contextlib
import XenAPI
import unittest
import xenapi_nfs_driver
import os
import params
import XenAPI


class Session(object):
    'Similar to the one we have in openstack'
    def __init__(self):
        self.url = params.xapi_url
        self.user = params.xapi_user
        self.password = params.xapi_pass

        self.XenAPI = XenAPI
        self.session = self._create_sess()
        self.host_uuid = self._get_host_uuid()

    def _create_sess(self):
        session = XenAPI.Session(self.url)
        session.login_with_password(self.user, self.password)
        return session

    @contextlib.contextmanager
    def _get_session(self):
        yield self.session

    def _get_host_uuid(self):
        with self._get_session() as session:
            host_ref = session.xenapi.session.get_this_host(session.handle)
            return session.xenapi.host.get_uuid(host_ref)

    def call_xenapi(self, method, *args):
        with self._get_session() as session:
            return session.xenapi_request(method, args)

    def get_xenapi_host(self):
        with self._get_session() as session:
            return session.xenapi.host.get_by_uuid(self.host_uuid)


class TestVolumeCreation(unittest.TestCase):
    def setUp(self):
        self.driver = xenapi_nfs_driver.XenAPINFSDriver(Session())
        self.disconnect_all_nfs_srs()
        self.host_ref = self.driver.session.get_xenapi_host()
        self.host_uuid = self.driver.session.host_uuid

    def disconnect_all_nfs_srs(self):
        for sr_ref in self.driver.get_srs():
            if self.driver.is_nfs_sr(sr_ref):
                self.driver.unplug_pbds_and_forget_sr(sr_ref)

    def test_new_sr_on_nfs_connects_an_sr_and_disconnects(self):
        driver = self.driver
        number_of_srs_before = len(driver.get_srs())

        with driver.new_sr_on_nfs(self.host_ref, params.nfs_server,
                                  params.nfs_serverpath):
            self.assertEquals(
                number_of_srs_before + 1,
                len(driver.get_srs()))

        self.assertEquals(
            number_of_srs_before,
            len(driver.get_srs()))

    def filenames_on_export(self):
        return set(os.listdir(params.exported_catalog))

    def test_sr_directory_is_not_removed(self):
        driver = self.driver

        filenames_before = self.filenames_on_export()

        with driver.new_sr_on_nfs(self.host_ref, params.nfs_server,
                                  params.nfs_serverpath) as sr_ref:
            uuid = driver.get_sr_uuid(sr_ref)

        filenames_after = self.filenames_on_export()

        self.assertEquals([uuid], list(filenames_after - filenames_before))

    def test_vdi_create_does_not_introduce_vdi(self):
        driver = self.driver

        vdi_list = driver.get_vdis()

        with driver.new_sr_on_nfs(self.host_ref, params.nfs_server,
                                  params.nfs_serverpath) as sr_ref:
            vdi_ref = driver.create_new_vdi(sr_ref, 1)
            self.assertEquals(
                set(vdi_list + [vdi_ref]), set(driver.get_vdis()))

        self.assertEquals(vdi_list, driver.get_vdis())

    def test_re_attach_an_sr(self):
        driver = self.driver

        with driver.new_sr_on_nfs(self.host_ref, params.nfs_server,
                                  params.nfs_serverpath) as sr_ref:
            sr_uuid = driver.get_sr_uuid(sr_ref)
            sr_count = len(driver.get_srs())
            pbd_count = len(driver.get_pbds())

        driver.plug_nfs_sr(
            self.host_ref, params.nfs_server, params.nfs_serverpath, sr_uuid)

        self.assertEquals(sr_count, len(driver.get_srs()))
        self.assertEquals(pbd_count, len(driver.get_pbds()))

    def test_create_a_new_nfs_backed_volume_returns_sr_uuid(self):
        driver = self.driver

        connection_data = driver.create_volume(
            self.host_uuid, params.nfs_server, params.nfs_serverpath, 1)

        self.assertIn(
            connection_data['sr_uuid'],
            os.listdir(params.exported_catalog)
        )

    def test_create_a_new_nfs_backed_volume_returns_vdi_uuid(self):
        driver = self.driver

        connection_data = driver.create_volume(
            self.host_uuid, params.nfs_server, params.nfs_serverpath, 1)

        self.assertIn(
            connection_data['vdi_uuid'] + ".vhd",
            os.listdir(
                os.path.join(
                    params.exported_catalog,
                    connection_data['sr_uuid']))
        )

    def test_re_attach_an_nfs_backed_volume_increases_number_of_vdis_srs(self):
        driver = self.driver

        original_number_of_srs = len(driver.get_srs())
        original_number_of_vdis = len(driver.get_vdis())

        connection_data = driver.create_volume(
            self.host_uuid, params.nfs_server, params.nfs_serverpath, 1)

        driver.connect_volume(self.host_uuid, connection_data)

        self.assertEquals(
            original_number_of_srs + 1,
            len(driver.get_srs()))

        self.assertEquals(
            original_number_of_vdis + 1,
            len(driver.get_vdis()))
