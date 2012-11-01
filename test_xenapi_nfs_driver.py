import unittest
import xenapi_nfs_driver
import os
import params


class TestSessionFactory(unittest.TestCase):
    def test_exception_raised_if_session_is_used_after_closed(self):
        sessionFactory = xenapi_nfs_driver.SessionFactory(
            params.xapi_url,
            params.xapi_user,
            params.xapi_pass
        )
        session = sessionFactory.get_session()

        session.get_srs()

        session.close()

        with self.assertRaises(xenapi_nfs_driver.XenAPIException):
            session.get_srs()


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
        self.host_uuid = self.session.get_host_uuid(self.host_ref)
        self.assertFalse(self.session.get_pool())

    def tearDown(self):
        self.session.close()

    def disconnect_all_nfs_srs(self):
        for sr_ref in self.session.get_srs():
            if self.session.is_nfs_sr(sr_ref):
                self.session.unplug_pbds_and_forget_sr(sr_ref)



class XenAPISessionTest(XenAPISessionBased):
    def test_new_sr_on_nfs_connects_an_sr_and_disconnects(self):
        session = self.session
        number_of_srs_before = len(session.get_srs())

        with session.new_sr_on_nfs(self.host_ref, params.nfs_server,
                                  params.nfs_serverpath):
            self.assertEquals(
                number_of_srs_before + 1,
                len(session.get_srs()))

        self.assertEquals(
            number_of_srs_before,
            len(session.get_srs()))

    def filenames_on_export(self):
        return set(os.listdir(params.exported_catalog))

    def test_sr_directory_is_not_removed(self):
        session = self.session

        filenames_before = self.filenames_on_export()

        with session.new_sr_on_nfs(self.host_ref, params.nfs_server,
                                  params.nfs_serverpath) as sr_ref:
            uuid = session.get_sr_uuid(sr_ref)

        filenames_after = self.filenames_on_export()

        self.assertEquals([uuid], list(filenames_after - filenames_before))

    def test_vdi_create_does_not_introduce_vdi(self):
        session = self.session

        vdi_list = session.get_vdis()

        with session.new_sr_on_nfs(self.host_ref, params.nfs_server,
                                  params.nfs_serverpath) as sr_ref:
            vdi_ref = session.create_new_vdi(sr_ref, 1)
            self.assertEquals(
                set(vdi_list + [vdi_ref]), set(session.get_vdis()))

        self.assertEquals(vdi_list, session.get_vdis())

    def test_re_attach_an_sr(self):
        session = self.session

        with session.new_sr_on_nfs(self.host_ref, params.nfs_server,
                                  params.nfs_serverpath) as sr_ref:
            sr_uuid = session.get_sr_uuid(sr_ref)
            sr_count = len(session.get_srs())
            pbd_count = len(session.get_pbds())

        session.plug_nfs_sr(
            self.host_ref, params.nfs_server, params.nfs_serverpath, sr_uuid)

        self.assertEquals(sr_count, len(session.get_srs()))
        self.assertEquals(pbd_count, len(session.get_pbds()))


class XenAPINFSDriverTest(XenAPISessionBased):
    def setUp(self):
        super(XenAPINFSDriverTest, self).setUp()
        self.driver = xenapi_nfs_driver.XenAPINFSDriver(self.sessionFactory)

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

        original_number_of_srs = len(self.session.get_srs())
        original_number_of_vdis = len(self.session.get_vdis())

        connection_data = driver.create_volume(
            self.host_uuid, params.nfs_server, params.nfs_serverpath, 1)

        driver.connect_volume(self.host_uuid, connection_data)

        self.assertEquals(
            original_number_of_srs + 1,
            len(self.session.get_srs()))

        self.assertEquals(
            original_number_of_vdis + 1,
            len(self.session.get_vdis()))

    def test_disconnect_a_volume(self):
        driver = self.driver

        original_number_of_srs = len(self.session.get_srs())
        original_number_of_vdis = len(self.session.get_vdis())

        connection_data = driver.create_volume(
            self.host_uuid, params.nfs_server, params.nfs_serverpath, 1)

        vdi_ref = driver.connect_volume(self.host_uuid, connection_data)

        driver.disconnect_volume(vdi_ref)

        self.assertEquals(
            original_number_of_srs,
            len(self.session.get_srs()))

        self.assertEquals(
            original_number_of_vdis,
            len(self.session.get_vdis()))
