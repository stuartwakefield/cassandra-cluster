import logging
import boto3
import hashlib
import uuid
import os
from botocore.exceptions import ClientError

NETWORK_STACK = 'cassandra-network'
DEPLOYMENT_STACK = 'cassandra-deployment'

CREATE_FAILED = 'CREATE_FAILED'
DELETE_FAILED = 'DELETE_FAILED'
ROLLBACK_FAILED = 'ROLLBACK_FAILED'
UPDATE_ROLLBACK_FAILED = 'UPDATE_ROLLBACK_FAILED'

FAILED_STATUSES = {CREATE_FAILED, DELETE_FAILED, ROLLBACK_FAILED, UPDATE_ROLLBACK_FAILED}

k = 'ParameterKey'
v = 'ParameterValue'

logger = logging.getLogger(__name__)

def template(path):
    with open(path) as f:
        return f.read()

def cloudformationstackexists(client, name):
    logger.info('{} - Checking if stack exists.'.format(name))
    try:
        client.describe_stacks(StackName=name)
        logger.info('{} - Stack exists.'.format(name))
        return True
    except:
        logger.info('{} - Stack does not exist.'.format(name))
        return False

def cloudformationstackcreate(client, name, template, **args):
    logger.info('{} - Creating stack.'.format(name))
    client.create_stack(
        StackName=name,
        TemplateBody=template,
        **args
    )
    logger.info('{} - Waiting for stack creation...'.format(name))
    waiter = client.get_waiter('stack_create_complete')
    waiter.wait(StackName=name)
    logger.info('{} - Stack created.'.format(name))

def cloudformationstackupdate(client, name, template, **args):
    logger.info('{} - Updating stack.'.format(name))
    client.update_stack(
        StackName=name,
        TemplateBody=template,
        **args
    )
    logger.info('{} - Waiting for stack updated...'.format(name))
    waiter = client.get_waiter('stack_update_complete')
    waiter.wait(StackName=name)
    logger.info('{} - Stack updated.'.format(name))

def cloudformationstackreplace(client, name, template, **args):
    logger.info('{} - Replacing stack.'.format(name))
    cloudformationstackdelete(client, name)
    cloudformationstackcreate(client, name, template, **args)
    logger.info('{} - Stack replaced.'.format(name))

def cloudformationstackdelete(client, name):
    logger.info('{} - Deleting stack.'.format(name))
    client.delete_stack(StackName=name)
    logger.info('{} - Waiting for stack deleted...'.format(name))
    waiter = client.get_waiter('stack_delete_complete')
    waiter.wait(StackName=name)
    logger.info('{} - Stack deleted.'.format(name))

def cloudformationstackisupdatable(client, name):
    logger.info('{} - Checking stack status.'.format(name))
    response = client.describe_stacks(StackName=name)
    if response['Stacks'][0]['StackStatus'] not in FAILED_STATUSES:
        logger.info('{} - Stack can be updated.'.format(name))
        return True
    else:
        logger.info('{} - Stack requires replacement.'.format(name))
        return False

def cloudformationstackgettemplate(client, name):
    logger.info('{} - Getting template for stack.'.format(name))
    response = client.get_template(StackName=name)
    template = response['TemplateBody']
    logger.info('{} - Template for stack retrieved.'.format(name))
    return template

def cloudformationstackisdirty(client, name, template):
    logger.info('{} - Checking if template is dirty.'.format(name))
    remote = hashlib.md5(cloudformationstackgettemplate(client, name).encode('utf-8')).hexdigest()
    logger.info('{} - Remote template MD5 {}.'.format(name, remote))
    local = hashlib.md5(template.encode('utf-8')).hexdigest()
    logger.info('{} - Local template MD5 {}.'.format(name, local))
    if remote != local:
        logger.info('{} - Stack template is dirty.'.format(name))
        return True
    else:
        logger.info('{} - Stack template is up to date.'.format(name))
        return False

class Stack:

    def __init__(self, name, template, **args):
        self.name = name
        self.template = template
        self.args = args

class UpdateInPlaceStack(Stack):

    def __stackexists(self, client):
        return cloudformationstackexists(client, self.name)

    def __createstack(self, client):
        return cloudformationstackcreate(client, self.name, self.template, **self.args)

    def __stackisupdatable(self, client):
        return cloudformationstackisupdatable(client, self.name)

    def __replacestack(self, client):
        return cloudformationstackreplace(client, self.name, self.template, **self.args)

    def __stackisdirty(self, client):
        return cloudformationstackisdirty(client, self.name, self.template)

    def __updatestack(self, client):
        return cloudformationstackupdate(client, self.name, self.template, **self.args)

    def apply(self, client):
        if not self.__stackexists(client):
            self.__createstack(client)
        elif not self.__stackisupdatable(client):
            self.__replacestack(client)
        elif self.__stackisdirty(client):
            self.__updatestack(client)

class CreateAndSwapUpdateStack(Stack):

    def apply(self, client):
        print('Create and swap')

class ImmutableStack(Stack):

    def __createstack(self, client):
        return cloudformationstackcreate(client, self.name, self.template, **self.args)

    def apply(self, client):
        self.__createstack(client)

class UpdateReplacementStack(Stack):

    def __stackexists(self, client):
        return cloudformationstackexists(client, self.name)

    def __createstack(self, client):
        return cloudformationstackcreate(client, self.name, self.template, **self.args)

    def __replacestack(self, client):
        return cloudformationstackreplace(client, self.name, self.template, **self.args)

    def apply(self, client):
        if not self.__stackexists(client):
            self.__createstack(client)
        else:
            self.__replacestack(client)

class SetupTeardownStack(Stack):

    def setup(self, client):
        if not cloudformationstackexists(client, self.instance.name):
            return cloudformationstackcreate(client, self.name, self.template, **self.args)

    def teardown(self, client):
        if cloudformationstackexists(client, self.instance.name):
            return cloudformationstackdelete(client, self.name)

class NetworkStack(UpdateInPlaceStack):

    def __init__(self, allow_ip):
        super().__init__(NETWORK_STACK, template('infrastructure/network.yaml'),
        Parameters=[
            { k: 'AllowedIPAddress', v: allow_ip }
        ])

PRIVATE_IPS = {
    'a1': 'PrivateIPA1',
    'a2': 'PrivateIPA2',
    'b1': 'PrivateIPB1',
    'b2': 'PrivateIPB2',
    'c1': 'PrivateIPC1'
}
PUBLIC_IP_ALLOCATION = {
    'a': 'PublicIPAllocationA',
    'b': 'PublicIPAllocationB',
    'c': 'PublicIPAllocationC',
    'd': 'PublicIPAllocationD',
    'e': 'PublicIPAllocationE'
}
VOLUMES = {
    'a1': 'VolumeA1',
    'a2': 'VolumeA2',
    'b1': 'VolumeB1',
    'b2': 'VolumeB2',
    'c1': 'VolumeC1'
}

class DeploymentInstance(UpdateReplacementStack):

    def __init__(self, instance_name, subnet_name, instance_suffix, public_ip_allocation):
        super().__init__(
            '{}-{}-{}'.format(DEPLOYMENT_STACK, 'instance', instance_suffix),
            template('infrastructure/instance.yaml'),
            Parameters=[
                { k: 'NetworkStack', v: NETWORK_STACK },
                { k: 'SubnetName', v: subnet_name },
                { k: 'Name', v: instance_name },
                { k: 'IPAllocationName', v: PUBLIC_IP_ALLOCATION[public_ip_allocation] },
                { k: 'VolumeName', v: VOLUMES[instance_suffix] },
                { k: 'PrivateIPName', v: PRIVATE_IPS[instance_suffix] }
            ]
        )

class Deployment:

    def __init__(self):
        self.instances = [
            DeploymentInstance(instance_name, subnet_name, instance_suffix, public_ip_allocation)
            for instance_name, subnet_name, instance_suffix, public_ip_allocation in [
                ('cassandra-a1', 'SubnetPublicA', 'a1', 'a'),
                ('cassandra-a2', 'SubnetPublicA', 'a2', 'b'),
                ('cassandra-b1', 'SubnetPublicB', 'b1', 'c'),
                ('cassandra-b2', 'SubnetPublicB', 'b2', 'd'),
                ('cassandra-c1', 'SubnetPublicC', 'c1', 'e')
            ]
        ]

    def apply(self, client):
        for instance in self.instances:
            instance.apply(client)

def main():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    client = boto3.client('cloudformation')

    if 'ALLOW_IP' not in os.environ:
        raise Exception("Missing ALLOW_IP environment variable")

    allow_ip = os.environ['ALLOW_IP']

    network_stack = NetworkStack(allow_ip)
    deployment = Deployment()

    network_stack.apply(client)
    deployment.apply(client)

if __name__ == '__main__':
    main()
