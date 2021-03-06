import sys
from ne_base import NosDeviceAction
from ne_base import log_exceptions


class Remove_Acl(NosDeviceAction):
    def run(self, mgmt_ip, username, password, intf_type, intf_name,
            rbridge_id, acl_name, acl_direction):
        """Run helper methods to remove ACL on desired interface.
        """
        try:
            self.setup_connection(host=mgmt_ip, user=username, passwd=password)
        except Exception as e:
            self.logger.error(e.message)
            sys.exit(-1)
        return self.switch_operation(intf_type, intf_name,
                                     rbridge_id, acl_name,
                                     acl_direction)

    @log_exceptions
    def switch_operation(self, intf_type, intf_name,
                         rbridge_id, acl_name, acl_direction):
        parameters = locals()
        parameters.pop('self', None)

        interface_list = []
        intf_type = intf_type.lower()

        # Check is the user input for Interface Name is correct
        for intf in intf_name:
            if "-" not in str(intf):
                interface_list.append(intf)
            else:
                ex_intflist = self.extend_interface_range(intf_type=intf_type,
                                                          intf_name=intf)
                for ex_intf in ex_intflist:
                    interface_list.append(ex_intf)

        with self.pmgr(conn=self.conn, auth=self.auth,
                       auth_snmp=self.auth_snmp,
                       connection_type='NETCONF') as device:

            if device.connection_type == 'NETCONF':
                parameters['device'] = device

            self.logger.info('Removing ACL %s on int-type - %s int-name- %s',
                             acl_name, intf_type, str(intf_name))

            output = device.acl.remove_acl(**parameters)  # pylint: disable=no-member
            self.logger.info(output)

            return True

        return False
