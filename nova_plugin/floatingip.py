#########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.

from cloudify.decorators import operation
from cloudify.exceptions import NonRecoverableError

from openstack_plugin_common import with_nova_client


@operation
@with_nova_client
def create(ctx, nova_client, **kwargs):

    # Already acquired?
    if ctx.runtime_properties.get('external_id'):
        ctx.logger.debug("Using already allocated Floating IP {0}".format(
            ctx.runtime_properties['floating_ip_address']))
        return

    floatingip = {
        'pool': None
    }

    if 'floatingip' in ctx.properties:
        floatingip.update(ctx.properties['floatingip'])

    # Sugar: ip -> (copy as is) -> floating_ip_address
    if 'ip' in floatingip:
        floatingip['floating_ip_address'] = floatingip['ip']
        del floatingip['ip']

    if 'floating_ip_address' in floatingip:
        fip = _find_existing_floating_ip(
            nova_client, floatingip['floating_ip_address'])

        ctx.runtime_properties['external_id'] = fip.id
        ctx.runtime_properties['floating_ip_address'] = fip.ip
        ctx.runtime_properties['enable_deletion'] = False
        return

    fip = nova_client.floating_ips.create(floatingip['pool'])

    ctx.runtime_properties['external_id'] = fip.id
    ctx.runtime_properties['floating_ip_address'] = fip.ip
    # Acquired here -> OK to delete
    ctx.runtime_properties['enable_deletion'] = True
    ctx.logger.info(
        "Allocated floating IP {0}".format(fip.ip))


def _find_existing_floating_ip(nova_client, address):
    fips = nova_client.floating_ips.list()
    filtered = [fip for fip in fips if fip.ip == address]
    if len(filtered) == 0:
        raise NonRecoverableError('Did not find an allocated floating IP '
                                  'with address {0}'.format(address))

    if len(filtered) > 1:
        raise NonRecoverableError('Found multiple floating IPs with '
                                  'address {0}. This should not be '
                                  'possible'.format(address))

    return fip


@operation
@with_nova_client
def delete(ctx, nova_client, **kwargs):
    do_delete = bool(ctx.runtime_properties.get('enable_deletion'))
    op = ['Not deleting', 'Deleting'][do_delete]
    ctx.logger.debug("{0} floating IP {1}".format(
        op, ctx.runtime_properties['floating_ip_address']))
    if do_delete:
        nova_client.floating_ips.delete(ctx.runtime_properties['external_id'])

    ctx.runtime_properties['external_id'] = None
    ctx.runtime_properties['floating_ip_address'] = None
    ctx.runtime_properties['enable_deletion'] = None
