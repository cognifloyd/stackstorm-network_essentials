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


import re
import ipaddress
import pynos.device
import pynos.utilities
import pyswitchlib.asset
import socket
from st2actions.runners.pythonrunner import Action


class DeviceAction(Action):
    def __init__(self, config=None, action_service=None):
        super(DeviceAction, self).__init__(config=config, action_service=action_service)
        self.result = {'changed': False, 'changes': {}}
        self.mgr = pynos.device.Device
        self.host = None
        self.conn = None
        self.auth = None
        self.asset = pyswitchlib.asset.Asset

    def setup_connection(self, host, user=None, passwd=None):
        self.host = host
        self.conn = (host, '22')
        self.auth = (user, passwd)  # self._get_auth(host=host, user=user, passwd=passwd)

    def _get_auth(self, host, user, passwd):
        if not user:
            lookup_key = self._get_lookup_key(host=self.host, lookup='user')
            user_kv = self.action_service.get_value(name=lookup_key, local=False)
            if not user_kv:
                raise Exception('username for %s not found.' % host)
            user = user_kv
        if not passwd:
            lookup_key = self._get_lookup_key(host=self.host, lookup='passwd')
            passwd_kv = self.action_service.get_value(name=lookup_key, local=False, decrypt=True)
            if not passwd_kv:
                raise Exception('password for %s not found.' % host)
            passwd = passwd_kv
        return (user, passwd)

    def _get_lookup_key(self, host, lookup):
        return 'switch.%s.%s' % (host, lookup)

    def check_int_description(self, intf_description):
        """
        Check for valid interface description
        """
        err_code = len(intf_description)
        if err_code < 1:
            self.logger.info('Pls specify a valid description')
            return False
        elif err_code <= 63:
            return True
        else:
            self.logger.info('Length of the description is more than the allowed size')
            return False

    def expand_vlan_range(self, vlan_id):
        """Fail the task if vlan id is zero or one or above 4096 .
        """

        re_pattern1 = r"^(\d+)$"
        re_pattern2 = r"^(\d+)\-?(\d+)$"

        if re.search(re_pattern1, vlan_id):
            try:
                vlan_id = (int(vlan_id),)
            except ValueError:
                self.logger.info("Could not convert data to an integer.")
                return None
        elif re.search(re_pattern2, vlan_id):
            try:
                vlan_id = re.match(re_pattern2, vlan_id)
            except ValueError:
                self.logger.info("Not in valid range format.")
                return None

            if int(vlan_id.groups()[0]) == int(vlan_id.groups()[1]):
                self.logger.warning("Use range command only for diff vlans")
            vlan_id = range(int(vlan_id.groups()[0]), int(vlan_id.groups()[1]) + 1)

        else:
            self.logger.info("Invalid vlan format")
            return None

        for vid in vlan_id:
            if vid > 4096:
                extended = "true"
            else:
                extended = "false"
            tmp_vlan_id = pynos.utilities.valid_vlan_id(vid, extended=extended)
            reserved_vlan_list = range(4087, 4096)
            reserved_vlan_list.append(1002)

            if not tmp_vlan_id:
                self.logger.info("'Not a valid VLAN %s", vid)
                return None
            if vid == 1:
                self.logger.info("vlan %s is default vlan", vid)
                return None
            elif vid in reserved_vlan_list:
                self.logger.info("Vlan cannot be created, as it is not a user/fcoe vlan %s", vid)
                return None

        return vlan_id

    def validate_interface(self, intf_type, intf_name, rbridge_id):
        msg = None
        # int_list = intf_name
        re_pattern1 = r"^(\d+)$"
        re_pattern2 = r"^(\d+)\/(\d+)\/(\d+)$"
        re_pattern3 = r"^(\d+)\/(\d+)$"
        intTypes = ["port_channel", "gigabitethernet", "tengigabitethernet", "fortygigabitethernet",
                    "hundredgigabitethernet", "ethernet"]
        NosIntTypes = ["gigabitethernet", "tengigabitethernet", "fortygigabitethernet"]
        if rbridge_id is None and 'loopback' in intf_type:
            msg = 'Must specify `rbridge_id` when specifying a `loopback`'
        elif rbridge_id is None and 've' in intf_type:
            msg = 'Must specify `rbridge_id` when specifying a `ve`'
        elif rbridge_id is not None and intf_type in intTypes:
            msg = 'Should not specify `rbridge_id` when specifying a ' + intf_type
        elif re.search(re_pattern1, intf_name):
            intf = intf_name
        elif re.search(re_pattern2, intf_name) and intf_type in NosIntTypes:
            intf = intf_name
        elif re.search(re_pattern3, intf_name) and 'ethernet' in intf_type:
            intf = intf_name
        else:
            msg = 'Invalid interface format'

        if msg is not None:
            self.logger.info(msg)
            return False

        intTypes = ["ve", "loopback", "ethernet"]
        if intf_type not in intTypes:
            tmp_vlan_id = pynos.utilities.valid_interface(intf_type, name=str(intf))

            if not tmp_vlan_id:
                self.logger.info("Not a valid interface type %s or name %s", intf_type, intf)
                return False

        return True

    def expand_interface_range(self, intf_type, intf_name):
        msg = None

        int_list = intf_name
        re_pattern1 = r"^(\d+)\-?(\d+)$"
        re_pattern2 = r"^(\d+)\/(\d+)\-?(\d+)$"
        re_pattern3 = r"^(\d+)\/(\d+)\/(\d+)\-?(\d+)$"

        if re.search(re_pattern1, int_list):
            try:
                int_list = re.match(re_pattern1, int_list)
            except Exception:
                return None

            if int(int_list.groups()[0]) == int(int_list.groups()[1]):
                self.logger.info("Use range command only for unique values")
            int_list = range(int(int_list.groups()[0]), int(int_list.groups()[1]) + 1)

        elif re.search(re_pattern2, int_list):
            try:
                temp_list = re.match(re_pattern2, int_list)
            except Exception:
                return None

            if int(temp_list.groups()[1]) == int(temp_list.groups()[2]):
                self.logger.info("Use range command only for unique values")
            intList = range(int(temp_list.groups()[1]), int(temp_list.groups()[2]) + 1)
            int_list = []
            for intf in intList:
                int_list.append(temp_list.groups()[0] + '/' + str(intf))
            int_list = int_list

        elif re.search(re_pattern3, int_list):
            try:
                temp_list = re.match(re_pattern3, int_list)
            except Exception:
                return None

            if int(temp_list.groups()[2]) == int(temp_list.groups()[3]):
                self.logger.info("Use range command only for unique values")
            intList = range(int(temp_list.groups()[2]), int(temp_list.groups()[3]) + 1)
            int_list = []
            for intf in intList:
                int_list.append(temp_list.groups()[0] + '/' + temp_list.groups()[1] + '/' +
                                str(intf))
            int_list = int_list
        else:
            msg = 'Invalid interface format'

        if msg is not None:
            self.logger.info(msg)
            return None

        return int_list

    @staticmethod
    def is_valid_mac(mac):
        """
        This will only validate the HHHH.HHHH.HHHH MAC format. Will need to be expanded to
        validate other formats of MAC.

        :param mac:
        :return:
        """
        if re.match('[0-9A-Fa-f]{4}[.][0-9A-Fa-f]{4}[.][0-9A-Fa-f]{4}$', mac):
            return True
        else:
            return False

    @staticmethod
    def is_valid_ip(ip):
        try:
            ipaddress.ip_address(ip.decode('utf-8'))
            return True
        except ValueError:
            return False
        except AttributeError:
            return False

    @staticmethod
    def mac_converter(old_mac):
        """
        This method converts MAC from xxxx.xxxx.xxxx to xx:xx:xx:xx:xx:xx. This
        helps provide consistency across persisting MACs in the DB.

        Args:
                old_mac: MAC in a format xxxx.xxxx.xxxx

            Returns:
                dict: updated MAC in the xx:xx:xx:xx:xx:xx format
        """
        new_mac = old_mac.replace('.', '')
        newer_mac = ':'.join([new_mac[i:i + 2] for i in range(0, len(new_mac), 2)])
        return newer_mac

    def _validate_ip_(self, addr):
        try:
            socket.inet_aton(addr)
            return True
        except socket.error:
            return False

    def _get_acl_type_(self, device, acl_name):
        try:
            get = device.ip_access_list_standard_get(acl_name)
            return str(get[1][0][self.host]['response']['json']['output'].keys()[0])
        except:
            pass
        try:
            get = device.ip_access_list_extended_get(acl_name)
            return str(get[1][0][self.host]['response']['json']['output'].keys()[0])
        except:
            ValueError("Cannot get access list %s", acl_name)

    def _get_seq_id_(self, device, acl_name, acl_type):

        get = device.ip_access_list_extended_get if acl_type == 'extended' else \
            device.ip_access_list_standard_get
        try:
            get_output = get(acl_name)
            acl_dict = get_output[1][0][self.host]['response']['json']['output'][acl_type]
            if 'seq' in acl_dict:
                seq_list = acl_dict['seq']
                if type(seq_list) == list:
                    last_seq_id = int(seq_list[len(seq_list) - 1]['seq-id'])
                else:
                    last_seq_id = int(seq_list['seq-id'])
                if last_seq_id % 10 == 0:  # divisible by 10
                    seq_id = last_seq_id + 10
                else:
                    seq_id = (last_seq_id + 9) // 10 * 10  # rounding up to the nearest 10
            else:
                seq_id = 10
            return seq_id
        except:
            return None

    def _get_seq_(self, device, acl_name, acl_type, seq_id):

        get = device.ip_access_list_extended_get if acl_type == 'extended' else \
            device.ip_access_list_standard_get

        try:
            get_output = get(acl_name, resource_depth=3)
            acl_dict = get_output[1][0][self.host]['response']['json']['output'][acl_type]
            if 'seq' in acl_dict:
                seq_list = acl_dict['seq']
                seq_list = seq_list if type(seq_list) == list else [seq_list, ]
                for seq in seq_list:
                    if seq['seq-id'] == str(seq_id):
                        return seq
            else:
                self.logger.info('No seq present in acl %s', acl_name)
                return None

        except:
            self.logger.info('cannot get seq in acl %s', acl_name)
            return None