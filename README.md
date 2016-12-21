# Cassandra AWS Cluster

This project contains Cloudformation templates that can be used
to start up a five node Cassandra Cluster on AWS.

We are using 5 x i2.xlarge instances, each instance has a 100 GB GP2
EBS volume and an Elastic IP. See the `infrastructure/instance.yaml`
to change the instance settings and `infrastructure/network.yaml` to
change the volume sizing.

**NOTE:** The sitting cost of running this cluster continuously, without
overlapping charges (this happens during redeployment) or bandwidth and
IO costs is roughly £ 3,000 (about £ 5 an hour). The sitting cost of
the storage alone is roughly £ 50. You can delete the instance stacks
and the volumes will still be kept with your data as part of the
network stack. The cluster should also work with t2.small instances
(without EBS optimization) for a toy cluster which costs roughly £ 90
a month or (about 12p per hour).

## IP whitelist

The cluster is automatically locked down with security groups and you
must pass a whitelist of IPs to connect to the cluster when you run
the deployment. You can use `dig` to find your WAN IP required for the
whitelist:

```sh
dig +short myip.opendns.com @resolver1.opendns.com
```

## Deployment

To deploy you must install the required Python libraries, we recommend
using Virtualenv to avoid dependency versioning issues on your system.

You will also need to create a SSH keypair called `cassandra`.

```sh
# Create a virtual environment for Python
virtualenv .venv

# Active the virtual environment
source .venv/bin/activate

# Install the required libraries
pip install -r requirements.txt

# Deploy, whitelisting your IP for connection to the cluster
ALLOW_IP="$MY_IP" python deploy.py
```

## Connecting

Pick one of the public IPs to connect to:

```sh
cqlsh -u cassandra -p cassandra x.x.x.x
```

**NOTE**: It is recommended to replace the default user with a new
role in Cassandra 2.2 and later.

```sql
-- Create new role based access.
CREATE ROLE bob
WITH PASSWORD 'FTPdv^AAvfFrWP#QtN$AvT8y'
LOGIN = true
SUPERUSER = true;

-- Drop default user
DROP USER cassandra;
```

## Private IP / Public IP mapping

Your cluster will return other nodes addresses using their private
IP addresses, it is recommended to implement a mapping in your
driver to map the private IPs to the public IPs:

```scala
val hostMappings = Map[InetSocketAddress, InetSocketAddress] = Map(
  new InetSocketAddress("10.x.x.x", 9042) -> new InetSocketAddress("5x.x.x.x", 9042),
  ...
)
val hosts = hostMappings.values.map(_.getHostName).toSeq

val cluster = Cluster.builder()
  .addContactPoints(hosts: _*)
  .withPort(9042)
  .withCredentials(user, password)
  .withAddressTranslator(new AddressTranslator {

    override def init(cluster: Cluster): Unit = {}

    override def close(): Unit = {}

    override def translate(address: InetSocketAddress): InetSocketAddress =
      hostMappings(address)

  })
  .build()
```

## Troubleshooting

### CQL version not supported

> cql_version '3.4.2' is not supported by remote (w/ native protocol). Supported versions: [u'3.4.0']

To resolve this problem you will need to specify the CQL version
for the CLI / driver you are using. To do this using the CLI use
the `cqlversion` argument.

```
cqlsh --cqlversion=3.4.0 ...
```
