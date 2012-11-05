import contextlib
from cinder.volume.xenapi.lib import *


class XenAPINFSDriver(object):
    def __init__(self, session_factory):
        self._session_factory = session_factory

    # TODO: eliminate host_uuid
    def create_volume(self, host_uuid, server, serverpath, size):
        'Returns connection_data, which could be used to connect to the vol'
        with self._session_factory.get_session() as session:
            host_ref = session.get_host_by_uuid(host_uuid)
            with session.new_sr_on_nfs(host_ref, server, serverpath) as sr_ref:
                sr_uuid = session.get_sr_uuid(sr_ref)
                vdi_ref = session.create_new_vdi(sr_ref, size)
                vdi_uuid = session.get_vdi_uuid(vdi_ref)

            return dict(
                sr_uuid=sr_uuid,
                vdi_uuid=vdi_uuid,
                server=server,
                serverpath=serverpath)

    # TODO: eliminate host_uuid
    def connect_volume(self, host_uuid, connection_data):
        with self._session_factory.get_session() as session:
            host_ref = session.get_host_by_uuid(host_uuid)
            sr_ref = session.plug_nfs_sr(
                host_ref,
                connection_data['server'],
                connection_data['serverpath'],
                connection_data['sr_uuid']
            )
            session.scan_sr(sr_ref)
            return session.get_vdi_by_uuid(connection_data['vdi_uuid'])

    def disconnect_volume(self, vdi_ref):
        with self._session_factory.get_session() as session:
            vdi_rec = session.get_vdi_record(vdi_ref)
            sr_ref = vdi_rec['SR']
            session.unplug_pbds_and_forget_sr(sr_ref)
