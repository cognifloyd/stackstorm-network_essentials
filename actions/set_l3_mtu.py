import re
import sys

from ne_base import NosDeviceAction
from ne_base import log_exceptions


class set_l3_mtu(NosDeviceAction):
    def run(self, mgmt_ip, username, password, intf_type, intf_name, mtu_size,
            afi):
        """Run helper methods to set L3 MTU on desired interface.
        """
        try:
            self.setup_connection(host=mgmt_ip, user=username, passwd=password)
        except Exception as e:
            self.logger.error(e.message)
            sys.exit(-1)
        output = self.switch_operation(afi, intf_type, mtu_size, intf_name)
        return output

    @log_exceptions
    def switch_operation(self, afi, intf_type, mtu_size, intf_name):
        output = {}
        changes = []
        ip_version = int(re.search(r'ipv([\d.]+)', afi).group(1))
        intf_type = intf_type.lower()
        with self.pmgr(conn=self.conn, auth_snmp=self.auth_snmp) as device:
            self.logger.info('successfully connected to %s to set mtu',
                             self.host)

            interface_list = self.extract_port_list(device, intf_type, intf_name)

            changes = self._set_l3_mtu(device, intf_type=intf_type,
                                       intf_name=interface_list,
                                       mtu_size=mtu_size,
                                       ip_version=ip_version)
            output['result'] = changes
            self.logger.info(
                'closing connection to %s after configuring L3 mtu on '
                'interface--'
                ' all done!', self.host)
        return output

    def _set_l3_mtu(self, device, intf_type, intf_name, mtu_size, ip_version):
        result = True
        for intf in intf_name:
            self.logger.info(
                'configuring mtu_size %i on int-type - %s int-name- %s',
                mtu_size, intf_type, intf)
            try:

                device.interface.ip_mtu(mtu=mtu_size,
                                        name=intf,
                                        int_type=intf_type,
                                        version=ip_version)

                self.logger.info(
                    'Successfully  set  mtu_size %i on int %s %s',
                    mtu_size, intf_type, intf)
            except (TypeError, AttributeError, ValueError) as e:
                self.logger.error(
                    'Cannot set L3 mtu on interface %s %s due to %s',
                    intf_type, intf, e.message)
                result = False
                raise ValueError(e.message)
        return result
