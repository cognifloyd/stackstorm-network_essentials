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
from ne_base import log_exceptions
import re


class ConfigureBridgeDomain(NosDeviceAction):
    """
       Implements the logic to Create a BD and its parameters on SLX devices.
       This action achieves the below functionality
           1.Configure bridge domain
           2.Configure the peer ips
           3.Bind the logical interfaces to the bridge domain
           4.Associate the router interface to the bridge domain
    """

    def run(self, mgmt_ip, username, password, logical_interface_number, bridge_domain_id,
            bridge_domain_service_type, vc_id, statistics, bpdu_drop_enable, local_switching,
            peer_ip, intf_type, pw_profile_name, vlan_id):
        """Run helper methods to implement the desired state.
        """

        self.setup_connection(host=mgmt_ip, user=username, passwd=password)
        changes = self.switch_operation(logical_interface_number, bridge_domain_id,
                                        bridge_domain_service_type, vc_id, statistics,
                                        bpdu_drop_enable, local_switching, peer_ip,
                                        intf_type, pw_profile_name, vlan_id)

        return changes

    @log_exceptions
    def switch_operation(self, logical_interface_number, bridge_domain_id,
                         bridge_domain_service_type, vc_id, statistics, bpdu_drop_enable,
                         local_switching, peer_ip, intf_type, pw_profile_name, vlan_id):
        changes = {}
        with self.pmgr(conn=self.conn, auth=self.auth) as device:
            self.logger.info(
                'successfully connected to %s to configure bridge domain',
                self.host)

            if device.os_type == 'nos':
                self.logger.error('Operation is not supported on this device')
                return
            if logical_interface_number is not None:
                if intf_type is None:
                    self.logger.exception('Missing args `intf_type` while configuring '
                                          'logical_interface_number')
                    raise ValueError('Missing args `intf_type` while configuring '
                                     'logical_interface_number')
                elif len(logical_interface_number) > 1 and len(intf_type) == 1:
                    intf_type = intf_type * len(logical_interface_number)

            re_pat1 = '\d+r'
            if vlan_id is not None and re.match(re_pat1, device.firmware_version):
                self.logger.error('Bridge Domain association with router interface'
                                  ' is not supported on this device')
                return

            changes['pre_check_bd'] = self._check_bd_presence(device, intf_type,
                                                              bridge_domain_id,
                                                              bridge_domain_service_type, vc_id,
                                                              pw_profile_name, peer_ip)
            if changes['pre_check_bd']:
                changes['bd_config'] = self._configure_bridge_domain(device, bridge_domain_id,
                                                                     bridge_domain_service_type,
                                                                     vc_id, statistics,
                                                                     bpdu_drop_enable,
                                                                     local_switching,
                                                                     pw_profile_name)
                if logical_interface_number is not None:
                    changes['bd_lif_config'] = self._configure_lif(device, bridge_domain_id,
                                                                   bridge_domain_service_type,
                                                                   logical_interface_number,
                                                                   intf_type)
                if peer_ip is not None:
                    changes['bd_peer_config'] = self._configure_peer_ip(device,
                                                                        bridge_domain_id,
                                                                        bridge_domain_service_type,
                                                                        peers=peer_ip)
                if vlan_id is not None:
                    changes['bd_ve_config'] = self._configure_router_interface(device,
                                                                        bridge_domain_id,
                                                                        bridge_domain_service_type,
                                                                        vlan_id)

            self.logger.info('Closing connection to %s after configuring '
                             'bridge domain -- all done!',
                             self.host)
        return changes

    def _check_bd_presence(self, device, intf_type, bridge_domain_id,
                           bridge_domain_service_type, vc_id, pw_profile_name, peer_ip):

        if peer_ip is not None:
            for peerip in peer_ip:
                if peerip is not None and not self.is_valid_ip(peerip):
                    raise ValueError('Invalid IP address %s', peerip)

        if intf_type is not None:
            for each_intf in intf_type:
                if each_intf not in device.interface.valid_int_types:
                    self.logger.error('Interface type %s is not valid. '
                                      'Interface type must be one of %s',
                                      each_intf, device.interface.valid_int_types)
                    raise ValueError('Interface type is not valid. '
                                     'Interface type must be one of %s'
                                     % device.interface.valid_int_types)

        bd_check = device.interface.bridge_domain(bridge_domain=bridge_domain_id,
                                     bridge_domain_service_type=bridge_domain_service_type,
                                     get=True)

        if bd_check is not None:
            if bd_check['bridge_domain_type'] == str(bridge_domain_service_type):
                if vc_id is not None:
                    if bd_check['vc_id'] == str(vc_id):
                        if bd_check['pw_profile'] == str(pw_profile_name):
                            self.logger.info('bridge_domain_id %s configs are pre-existing',
                                             bridge_domain_id)
                            return False
                        else:
                            self.logger.info('bridge_domain_id %s configs are pre-existing with'
                                             ' different pw_profile %s', bridge_domain_id,
                                             bd_check['pw_profile'])
                            return False
                    elif bd_check['vc_id'] != str(vc_id) and bd_check['vc_id'] is not None:
                        self.logger.info('bridge_domain_id %s configs are pre-existing with'
                                         ' different vc_id %s',
                                         bridge_domain_id, bd_check['vc_id'])
                        return False
                else:
                    self.logger.info('bridge_domain_id %s configs are pre-existing',
                                     bridge_domain_id)
                    return False
            else:
                self.logger.info('bridge_domain_id %s configs are pre-existing with'
                                 ' different bridge_domain_type %s', bridge_domain_id,
                                 bd_check['bridge_domain_type'])
                return False
        return True

    def _configure_bridge_domain(self, device, bridge_domain_id, bridge_domain_service_type, vc_id,
                                 statistics, bpdu_drop_enable, local_switching, pw_profile_name):
        """ Configuring the bridge-domain, service, vc-id """

        try:
            self.logger.info('Configuring bridge-domain %s', bridge_domain_id)
            device.interface.bridge_domain(bridge_domain=bridge_domain_id,
                                           bridge_domain_service_type=bridge_domain_service_type,
                                           vc_id_num=vc_id, statistics=statistics,
                                           bpdu_drop_enable=bpdu_drop_enable,
                                           local_switching=local_switching,
                                           pw_profile_name=pw_profile_name,
                                           firmware_version=device.firmware_version)
        except ValueError as e:
            self.logger.exception("Configuring bridge-domain failed due to %s"
                                  % (e.message))
            raise ValueError("Configuring bridge-domain failed")
        return True

    def _configure_peer_ip(self, device, bridge_domain_id, bridge_domain_service_type, peers):
        """ Configure the peer ip on the bridge domain"""

        try:
            for peerip in peers:
                self.logger.info('Configuring peer_ip %s on bridge-domain %s', peerip,
                                 bridge_domain_id)
                device.interface.bridge_domain_peer(bridge_domain=bridge_domain_id,
                                   bridge_domain_service_type=bridge_domain_service_type,
                                   peer_ip=peerip)
        except ValueError as e:
            self.logger.exception("Configuring peer-ip on bridge-domain failed due to %s"
                                  % (e.message))
            raise ValueError("Configuring peer-ip on bridge-domain failed")
        return True

    def _configure_lif(self, device, bridge_domain_id, bridge_domain_service_type, lif, intf_type):
        """ Configure the lif on the bridge domain"""

        try:
            for lif_name, each_intf in zip(lif, intf_type):
                self.logger.info('Configuring lif_name %s %s on bridge-domain %s', each_intf,
                                 lif_name, bridge_domain_id)
                device.interface.bridge_domain_logical_interface(bridge_domain=bridge_domain_id,
                        bridge_domain_service_type=bridge_domain_service_type,
                        lif_name=lif_name,
                        intf_type=each_intf)
        except ValueError as e:
            self.logger.exception("Configuring lif on bridge-domain failed due to %s"
                                  % (e.message))
            raise ValueError("Configuring lif on bridge-domain failed")
        return True

    def _configure_router_interface(self, device, bridge_domain_id, bridge_domain_service_type,
                                    vlan_id):
        """ Configure router interface on the bridge domain"""

        try:
            self.logger.info('Associating router interface ve %s to bridge-domain %s', vlan_id,
                             bridge_domain_id)
            device.interface.bridge_domain_router_interface(bridge_domain=bridge_domain_id,
                        bridge_domain_service_type=bridge_domain_service_type,
                        vlan_id=vlan_id)
        except ValueError as e:
            self.logger.exception("Associating router interface to bridge-domain failed due to %s"
                                  % (e.message))
            raise ValueError("Associating router interface to bridge-domain failed")
        return True
