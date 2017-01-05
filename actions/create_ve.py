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
from ipaddress import ip_interface
from execute_cli import CliCMD
import re


class CreateVe(NosDeviceAction):
    """
       Implements the logic to create interface VE and associate IP on VDX Switches .
       This action acheives the below functionality
           1. Validate if the IPaddress is already associated to the VE
           2. Create a VE
           3. Associate the IP address to the VE
           4. Admin up on the interface VE
    """

    def run(self, mgmt_ip, username, password, rbridge_id, vlan_id, ip_address, vrf_name,
            ipv6_use_link_local_only):
        """Run helper methods to implement the desired state.
        """
        self.setup_connection(host=mgmt_ip, user=username, passwd=password)
        changes = {}
        if ip_address is None:
            tmp_list = rbridge_id
        else:
            if len(ip_address) == 1 and len(rbridge_id) >= 2:
                ip_address = ip_address * len(rbridge_id)
            elif len(rbridge_id) != len(ip_address):
                raise ValueError('rbridge_id and ip_address lists are not matching',
                                 rbridge_id, ip_address)
            tmp_list = zip(rbridge_id, ip_address)

        with self.mgr(conn=self.conn, auth=self.auth) as device:
            self.logger.info('successfully connected to %s to create Ve', self.host)
            for each_rb in tmp_list:
                if ip_address is None:
                    rbridge_id = each_rb
                else:
                    rbridge_id = each_rb[0]
                    temp_address = each_rb[1]
                if vrf_name is not None and vrf_name != '' and\
                        ip_address is not None and ip_address != '':
                    ip_address = temp_address
                    ve_exists = self._check_requirements_ve(device, rbridge_id=rbridge_id,
                                                            ve_name=vlan_id)
                    changes['pre_validation_vrf'] = self._check_requirements_vrf(device,
                                                                             rbridge_id=rbridge_id,
                                                                             ve_name=vlan_id,
                                                                             vrf_name=vrf_name,
                                                                             ip_address=ip_address)
                    changes['pre_validation_ip'] = self._check_requirements_ip(device,
                                                                           rbridge_id=rbridge_id,
                                                                           ve_name=vlan_id,
                                                                           vrf_name=vrf_name,
                                                                           ip_address=ip_address)
                    if changes['pre_validation_vrf']:
                        if ve_exists:
                            changes['create_ve'] = self._create_ve(device, rbridge_id=rbridge_id,
                                                                   ve_name=vlan_id)
                        changes['vrf_configs'] = self._create_vrf_forwarding(device,
                                                                         vrf_name=vrf_name,
                                                                         rbridge_id=rbridge_id,
                                                                         ve_name=str(vlan_id))
                    if changes['pre_validation_ip']:
                        changes['assign_ip'] = self._assign_ip_to_ve(device, rbridge_id=rbridge_id,
                                                                ve_name=vlan_id,
                                                                ip_address=ip_address)
                elif vrf_name is not None and vrf_name != '':
                    ve_exists = self._check_requirements_ve(device, rbridge_id=rbridge_id,
                                                            ve_name=vlan_id)
                    changes['pre_validation_vrf'] = self._check_requirements_vrf(device,
                                                                             rbridge_id=rbridge_id,
                                                                             ve_name=vlan_id,
                                                                             vrf_name=vrf_name,
                                                                             ip_address='')
                    if changes['pre_validation_vrf']:
                        if ve_exists:
                            changes['create_ve'] = self._create_ve(device, rbridge_id=rbridge_id,
                                                                   ve_name=vlan_id)
                        changes['vrf_configs'] = self._create_vrf_forwarding(device,
                                                                             vrf_name=vrf_name,
                                                                             rbridge_id=rbridge_id,
                                                                             ve_name=str(vlan_id))
                elif ip_address is not None and ip_address != '':
                    ip_address = temp_address
                    ve_exists = self._check_requirements_ve(device, rbridge_id=rbridge_id,
                                                            ve_name=vlan_id)
                    changes['pre_validation_ip'] = self._check_requirements_ip(device,
                                                                           rbridge_id=rbridge_id,
                                                                           ve_name=vlan_id,
                                                                           vrf_name='',
                                                                           ip_address=ip_address)
                    if changes['pre_validation_ip']:
                        if ve_exists:
                            changes['create_ve'] = self._create_ve(device, rbridge_id=rbridge_id,
                                                                   ve_name=vlan_id)
                        changes['assign_ip'] = self._assign_ip_to_ve(device, rbridge_id=rbridge_id,
                                                                ve_name=vlan_id,
                                                                ip_address=ip_address)
                elif ip_address is None and vrf_name is None:
                    ve_exists = self._check_requirements_ve(device, rbridge_id=rbridge_id,
                                                            ve_name=vlan_id)
                    if ve_exists:
                        changes['create_ve'] = self._create_ve(device, rbridge_id=rbridge_id,
                                                               ve_name=vlan_id)
                self._admin_state(device, ve_name=vlan_id, rbridge_id=rbridge_id)
                if ipv6_use_link_local_only:
                    ve_exists = self._check_requirements_ve(device, rbridge_id=rbridge_id,
                                                            ve_name=vlan_id)
                    if ve_exists:
                        changes['create_ve'] = self._create_ve(device, rbridge_id=rbridge_id,
                                                               ve_name=vlan_id)
                    self._ipv6_link_local(device, name=vlan_id, rbridge_id=rbridge_id)
            self.logger.info('closing connection to %s after creating Ve -- all done!', self.host)
        return changes

    def _check_requirements_ve(self, device, ve_name, rbridge_id):
        """ Verify if the VE is pre-existing """

        ves = device.interface.ve_interfaces(rbridge_id=rbridge_id)
        for each_ve in ves:
            tmp_ve_name = 'Ve ' + ve_name
            if each_ve['if-name'] == tmp_ve_name:
                self.logger.info('VE %s is pre-existing on rbridge_id %s', ve_name, rbridge_id)
                return False

        return True

    def _check_requirements_ip(self, device, ve_name, ip_address, rbridge_id, vrf_name):
        """ Verify if the ip address is already associated to the VE """

        exec_cli = CliCMD()
        host_ip = self.host
        host_username = self.auth[0]
        host_password = self.auth[1]

        try:
            ip_tmp = ip_interface(unicode(ip_address))
            ip_address = ip_tmp.with_prefixlen
        except ValueError:
            self.logger.info('Invalid IP address %s', ip_address)

        if len(unicode(ip_address).split("/")) != 2:
            raise ValueError('Pass IP address along with netmask.(ip-address/netmask)', ip_address)

        ves = device.interface.ve_interfaces(rbridge_id=rbridge_id)
        for each_ve in ves:
            tmp_ve_name = 'Ve ' + ve_name
            if each_ve['ip-address'] != 'unassigned':
                if each_ve['if-name'] == tmp_ve_name and each_ve['ip-address'] == ip_address:
                    self.logger.info('Ip address %s on the VE %s is pre-existing on rbridge_id %s',
                                     ip_address, ve_name, rbridge_id)
                    return False
                elif each_ve['if-name'] != tmp_ve_name and each_ve['ip-address'] == ip_address:
                    self.logger.info('Ip address %s is pre-assigned to a '
                                     'different %s on rbridge_id %s',
                                     ip_address, each_ve['if-name'], rbridge_id)
                    return False
                elif each_ve['if-name'] == tmp_ve_name and each_ve['ip-address'] != ip_address:
                    self.logger.info('Ve %s is pre-assigned with a different IP %s '
                                     'on rbridge_id %s',
                                     ve_name, each_ve['ip-address'], rbridge_id)
                    return False
                elif ip_interface(unicode(ip_address)).network == \
                        ip_interface(unicode(each_ve['ip-address'])).network:
                    self.logger.info('IP address %s overlaps with a previously '
                                     'configured IP subnet. Check %s on rbridge_id %s',
                                     ip_address, each_ve['if-name'], rbridge_id)
                    return False

        if vrf_name == '':
            vrf_fwd = device.interface.add_int_vrf(get=True, rbridge_id=rbridge_id,
                                                   name=ve_name, int_type='ve',
                                                   vrf_name=vrf_name)
            if vrf_fwd is not None:
                tmp1 = vrf_fwd.data.find('.//{*}forwarding')
                if tmp1 is not None:
                    config_tmp = vrf_fwd.data.find('.//{*}forwarding').text
                    self.logger.info('There is a VRF %s configured on the VE %s on rbridge_id %s'
                                     ',Remove the VRF to configure the IP Address %s',
                                     config_tmp, ve_name, rbridge_id, ip_address)
                    return False

        if vrf_name is not None and vrf_name != '':
            cli_arr = []
            cli_cmd = 'show run rb ' + rbridge_id + ' vrf ' + vrf_name
            cli_arr.append(cli_cmd)
            v4_pattern = 'address-family ipv4 unicast'
            v6_pattern = 'address-family ipv6 unicast'

            raw_cli_output = exec_cli.execute_cli_command(host=host_ip, user=host_username,
                                                          cli_cmd=cli_arr,
                                                          passwd=host_password)
            cli_output = raw_cli_output[cli_cmd]

            if ip_interface(unicode(ip_address)).version == 4:
                tmp_match = re.search(v4_pattern, cli_output)
                if not tmp_match:
                    self.logger.info('To configure the IP address on the Ve on rbridge_id %s, '
                                     'VRF Address Family-ipv4 has to be configured on VRF %s',
                                     vrf_name, rbridge_id)
                    return False
            else:
                tmp_match = re.search(v6_pattern, cli_output)
                if not tmp_match:
                    self.logger.info('To configure the ipv6 address on the Ve on rbridge_id %s, '
                                     'VRF Address Family-ipv6 has to be configured on VRF %s',
                                     vrf_name, rbridge_id)
                    return False

        return True

    def _check_requirements_vrf(self, device, ve_name, vrf_name, rbridge_id, ip_address):
        """ Verify if the vrf forwarding is enabled on the VE """

        ves = device.interface.ve_interfaces(rbridge_id=rbridge_id)
        vrf_output = device.interface.vrf(get=True, rbridge_id=rbridge_id)
        vrf_list = []
        for each_vrf in vrf_output:
            vrf_list.append(each_vrf['vrf_name'])

        for each_ve in ves:
            tmp_ve = 'Ve ' + ve_name
            if each_ve['ip-address'] != 'unassigned' and vrf_name in vrf_list:
                if each_ve['if-name'] == tmp_ve and each_ve['ip-address'] == ip_address:
                    self.logger.info('Ve %s is pre-assigned to this IP address %s, '
                                     'and VRF %s on rbridge-id %s',
                                     ve_name, each_ve['ip-address'], vrf_name, rbridge_id)
                    return False
                elif each_ve['if-name'] == tmp_ve and each_ve['ip-address'] != ''\
                        and ip_address == '':
                    self.logger.info('There is an IP address %s pre-existing on the Ve %s, '
                                     'Remove the IP address before assigning the VRF %s on '
                                     'rbridge-id %s',
                                     each_ve['ip-address'], ve_name, vrf_name, rbridge_id)
                    return False
                elif each_ve['if-name'] == tmp_ve and each_ve['ip-address'] != ip_address:
                    self.logger.info('Ve %s is pre-assigned to a different IP address %s, '
                                     'Remove the IP address before assigning the VRF %s'
                                     'on rbridge-id %s',
                                     ve_name, each_ve['ip-address'], vrf_name, rbridge_id)
                    return False

        if vrf_name not in vrf_list:
            self.logger.info('Create VRF %s on rbridge-id %s before assigning it to Ve',
                             vrf_name, rbridge_id)
            return False

        vrf_fwd = device.interface.add_int_vrf(get=True, rbridge_id=rbridge_id,
                                               name=ve_name, int_type='ve',
                                               vrf_name=vrf_name)
        if vrf_fwd is not None:
            tmp1 = vrf_fwd.data.find('.//{*}forwarding')
            if tmp1 is not None:
                config_tmp = vrf_fwd.data.find('.//{*}forwarding').text
                if config_tmp == vrf_name:
                    self.logger.info('VRF %s forwarding is pre-existing on Ve %s on rbridge-id %s',
                                     vrf_name, ve_name, rbridge_id)
                    return False
                elif config_tmp != vrf_name:
                    self.logger.info('VRF forwarding is enabled on Ve %s but with a different'
                                     ' VRF %s on rbride-id %s',
                                     ve_name, config_tmp, rbridge_id)
                    return False
        return True

    def _create_ve(self, device, rbridge_id, ve_name):
        """ Configuring the VE"""

        try:
            self.logger.info('Creating VE %s on rbridge-id %s', ve_name, rbridge_id)
            device.interface.add_vlan_int(ve_name)
            device.interface.create_ve(enable=True, ve_name=ve_name, rbridge_id=rbridge_id)
        except (ValueError, KeyError):
            self.logger.info('Invalid Input values while creating to Ve')

    def _assign_ip_to_ve(self, device, rbridge_id, ve_name, ip_address):
        """ Associate the IP address to the VE"""

        try:
            self.logger.info('Assiging IP address %s to VE %s on rbridge-id %s',
                             ip_address, ve_name, rbridge_id)
            ip_address = ip_interface(unicode(ip_address))
            device.interface.ip_address(name=ve_name, int_type='ve', ip_addr=ip_address,
                                        rbridge_id=rbridge_id)
        except (ValueError, KeyError):
            self.logger.info('Invalid Input values while assigning IP address to Ve')

    def _create_vrf_forwarding(self, device, rbridge_id, ve_name, vrf_name):
        """ Configure VRF is any"""

        try:
            self.logger.info('Configuring VRF %s on Ve %s on rbridge-id %s',
                             vrf_name, ve_name, rbridge_id)
            device.interface.add_int_vrf(int_type='ve', name=ve_name, rbridge_id=rbridge_id,
                                         vrf_name=vrf_name)
        except (ValueError, KeyError):
            self.logger.info('Invalid Input values while configuring VRF %s on'
                             'Ve %s on rbridge-id %s', vrf_name, ve_name, rbridge_id)

    def _admin_state(self, device, ve_name, rbridge_id):
        """ Admin settings on interface """

        # no-shut on the ve
        conf_port_chan = device.interface.admin_state(get=True,
                                                      int_type='ve',
                                                      name=ve_name, rbridge_id=rbridge_id)
        conf_port_1 = conf_port_chan.data.find('.//{*}interface')
        conf_port_2 = conf_port_chan.data.find('.//{*}shutdown')
        if conf_port_1 is not None and conf_port_2 is not None:
            device.interface.admin_state(enabled=True, name=ve_name,
                                         int_type='ve', rbridge_id=rbridge_id)
            self.logger.info('Admin state setting on Ve %s is successfull',
                             ve_name)

    def _ipv6_link_local(self, device, name, rbridge_id):
        """ Enable ipv6 link local only on VE """

        try:
            link_check = device.interface.ipv6_link_local(get=True, name=name,
                                                          rbridge_id=rbridge_id, int_type='ve')
            if not link_check:
                device.interface.ipv6_link_local(name=name, rbridge_id=rbridge_id, int_type='ve')
                self.logger.info('Configuring IPV6 link local on Ve %s on rbridge_id %s is '
                                 'successfull', name, rbridge_id)
            else:
                self.logger.info('IPV6 link local on Ve %s on rbridge_id %s is pre-existing',
                                 name, rbridge_id)
        except (ValueError, KeyError):
            self.logger.info('Invalid Input values while configuring IPV6 link local')