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

from ne_base import NosDeviceAction


class CreateVlan(NosDeviceAction):
    """
       Implements the logic to create vlans on VDX and SLX devices.
       This action achieves the below functionality
           1.Vlan Id and description validation
           2.Check for the vlan on the Device,if not present create it
           3.No errors reported when the VLAN already exists (idempotent)
    """

    def run(self, mgmt_ip, username, password, vlan_id, intf_desc):
        """Run helper methods to implement the desired state.
        """

        self.setup_connection(host=mgmt_ip, user=username, passwd=password)
        changes = {}

        with self.pmgr(conn=self.conn, auth=self.auth) as device:
            self.logger.info(
                'successfully connected to %s to validate interface vlan',
                self.host)
            # Check is the user input for VLANS is correct

            vlan_list = self.expand_vlan_range(vlan_id=vlan_id)

            valid_desc = True
            if intf_desc:
                # if description is passed we validate that the length is good.
                valid_desc = self.check_int_description(
                    intf_description=intf_desc)

            if vlan_list and valid_desc:
                changes['vlan'] = self._create_vlan(
                    device, vlan_id=vlan_list, intf_desc=intf_desc)
            else:
                raise ValueError('Input is not a valid vlan or description')

            self.logger.info('Closing connection to %s after configuring '
                             'create vlan -- all done!',
                             self.host)

        return changes

    def _create_vlan(self, device, vlan_id, intf_desc):
        output = []

        for vlan in vlan_id:
            check_vlan = device.interface.get_vlan_int(vlan)
            result = {}
            if check_vlan is False:
                cr_vlan = device.interface.add_vlan_int(vlan)
                self.logger.info('Successfully created a VLAN %s', vlan)
                result['result'] = cr_vlan
                result['output'] = 'Successfully created a VLAN %s' % vlan
            else:
                result['result'] = 'False'
                result['output'] = 'VLAN  %s already exists on' \
                                   ' the device' % vlan
                self.logger.info('VLAN %s already exists, not created', vlan)

            if intf_desc:
                self.logger.info(
                    'Configuring VLAN description as %s', intf_desc)
                try:
                    device.interface.description(
                        int_type='vlan', name=vlan, desc=intf_desc)
                    result[
                        'description'] = 'Successfully updated VLAN ' \
                                         'description for %s' % vlan
                    self.logger.info(
                        'Successfully updated VLAN description for %s' %
                        vlan)
                except (KeyError, ValueError, AttributeError) as e:
                    self.logger.info(
                        'Configuring VLAN interface failed for %s' %
                        vlan)
                    raise ValueError(
                        'Configuring VLAN interface failed', e.message)
            else:
                self.logger.debug('Skipping to update Interface description,'
                                  ' as no info provided')
            output.append(result)
        return output
