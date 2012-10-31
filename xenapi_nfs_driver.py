import contextlib


class XenAPINFSDriver(object):
    def __init__(self, session):
        self.session = session

    def get_pbds(self):
        return self.session.call_xenapi('PBD.get_all')

    def get_srs(self):
        return self.session.call_xenapi('SR.get_all')

    def get_vdis(self):
        return self.session.call_xenapi('VDI.get_all')

    def get_sr_record(self, sr_ref):
        return self.session.call_xenapi('SR.get_record', sr_ref)

    def get_vdi_record(self, vdi_ref):
        return self.session.call_xenapi('VDI.get_record', vdi_ref)

    def forget_sr(self, sr_ref):
        self.session.call_xenapi('SR.forget', sr_ref)

    def unplug_pbd(self, pbd_ref):
        self.session.call_xenapi('PBD.unplug', pbd_ref)

    def scan_sr(self, sr_ref):
        self.session.call_xenapi('SR.scan', sr_ref)

    def get_vdi_by_uuid(self, vdi_uuid):
        return self.session.call_xenapi('VDI.get_by_uuid', vdi_uuid)

    # Record based operations
    def get_sr_uuid(self, sr_ref):
        return self.get_sr_record(sr_ref)['uuid']

    def get_vdi_uuid(self, vdi_ref):
        return self.get_vdi_record(vdi_ref)['uuid']

    def is_nfs_sr(self, sr_ref):
        return self.get_sr_record(sr_ref).get('type') == 'nfs'

    # Compound operations
    def unplug_pbds_and_forget_sr(self, sr_ref):
        sr_rec = self.get_sr_record(sr_ref)
        for pbd_ref in sr_rec.get('PBDs', []):
            self.unplug_pbd(pbd_ref)
        self.forget_sr(sr_ref)

    @contextlib.contextmanager
    def new_sr_on_nfs(self, server, serverpath):
        host_ref = self.session.get_xenapi_host()
        device_config = dict(
            server=server,
            serverpath=serverpath
        )
        physical_size = '0'
        name_label = 'name-label'
        name_description = 'name-description'
        sr_type = 'nfs'
        content_type = ''
        shared = False
        sm_config = dict()

        sr_ref = self.session.call_xenapi(
            'SR.create',
            host_ref,
            device_config,
            physical_size,
            name_label,
            name_description,
            sr_type,
            content_type,
            shared,
            sm_config
        )
        yield sr_ref

        self.unplug_pbds_and_forget_sr(sr_ref)

    def create_new_vdi(self, sr_ref, size):
        return self.session.call_xenapi('VDI.create',
            dict(
                SR=sr_ref,
                virtual_size=str(size),
                type='User',
                sharable=False,
                read_only=False,
                other_config=dict()
            )
        )

    def create_volume(self, server, serverpath, size):
        with self.new_sr_on_nfs(server, serverpath) as sr_ref:
            sr_uuid = self.get_sr_uuid(sr_ref)
            vdi_ref = self.create_new_vdi(sr_ref, size)
            vdi_uuid = self.get_vdi_uuid(vdi_ref)

        return dict(
            sr_uuid=sr_uuid,
            vdi_uuid=vdi_uuid,
            server=server,
            serverpath=serverpath)

    def plug_nfs_sr(self, server, serverpath, sr_uuid):
        name_label = 'name-label'
        name_description = 'name-description'
        sr_type = 'nfs'
        content_type = ''
        shared = False
        sm_config = dict()

        sr_ref = self.session.call_xenapi(
            'SR.introduce',
            sr_uuid,
            name_label,
            name_description,
            sr_type,
            content_type,
            shared,
            sm_config
        )

        device_config = dict(
            server=server,
            serverpath=serverpath
        )

        pbd_ref = self.session.call_xenapi(
            'PBD.create',
            dict(
                host=self.session.get_xenapi_host(),
                SR=sr_ref,
                device_config=device_config)
        )

        self.session.call_xenapi(
            'PBD.plug',
            pbd_ref)

        return sr_ref

    def connect_volume(self, connection_data):
        sr_ref = self.plug_nfs_sr(
            connection_data['server'],
            connection_data['serverpath'],
            connection_data['sr_uuid']
        )
        self.scan_sr(sr_ref)
        return self.get_vdi_by_uuid(connection_data['vdi_uuid'])
