# Copyright 2016 Brocade Communications Systems, Inc.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import itertools

from ne_base import NosDeviceAction
from ne_base import log_exceptions


class CreateVlan(NosDeviceAction):
    """
       Implements the logic to create vlans on VDX and SLX devices.
       This action achieves the below functionality
           1.Create a Vlan Id and description
    """

    def run(self, mgmt_ip, username, password, vlan_id, vlan_desc):
        """Run helper methods to implement the desired state.
        """

        self.setup_connection(host=mgmt_ip, user=username, passwd=password)
        changes = self.switch_operation(vlan_desc, vlan_id)

        return changes

    @log_exceptions
    def switch_operation(self, intf_desc, vlan_id):
        changes = {}
        with self.pmgr(conn=self.conn, auth=self.auth) as device:
            self.logger.info(
                'Successfully connected to %s to create interface vlans',
                self.host)
            # Check is the user input for VLANS is correct
            vlan_list = []
            vlanlist = vlan_id.split(',')
            for val in vlanlist:
                temp = self.expand_vlan_range(vlan_id=val)
                if temp is None:
                    raise ValueError('Reserved/Control Vlans or Invalid Vlan Ids passed'
                                     ' in args `vlan_id` %s' % (vlan_id))
                vlan_list.append(temp)

            vlan_list = list(itertools.chain.from_iterable(vlan_list))

            valid_desc = True
            if intf_desc:
                valid_desc = self.check_int_description(intf_description=intf_desc)
            if not valid_desc:
                raise ValueError('Unsupported `vlan_desc` value passed', intf_desc)

            changes['vlan'] = self._create_vlan(device, vlan_id=vlan_list)
            self._update_vlan(device, vlan_id=vlan_list, intf_desc=intf_desc)

            self.logger.info('Closing connection to %s after '
                             'creating vlan -- all done!',
                             self.host)
        return changes

    def _create_vlan(self, device, vlan_id):

        try:
            self.logger.info('Creating Vlans %s', vlan_id)
            for vlan in vlan_id:
                device.interface.add_vlan_int(vlan)
        except KeyError, ValueError:
            self.logger.info('VLAN %s creation failed', vlan)
            raise ValueError('VLAN creation failed')

        return True

    def _update_vlan(self, device, vlan_id, intf_desc):

        try:
            self.logger.info('Configuring Vlan description as %s', intf_desc)
            for vlan in vlan_id:
                device.interface.description(int_type='vlan', name=vlan, desc=intf_desc)
        except (KeyError, ValueError, AttributeError) as e:
            self.logger.info('Configuring Vlan description failed for %s' % vlan)
            raise ValueError('Configuring Vlan description failed', e.message)

        return True
