#!/bin/bash
mkdir -p build
cp sources/cassandra.yaml build/cassandra.yaml
cp build/cassandra.yaml build/cassandra.yaml.tmp
addr='10.100.10.7'
cat build/cassandra.yaml.tmp | \
  sed 's/^.*\(cluster_name:\).*$/\1 main/' | \
  sed 's/^.*\(listen_address:.*\)$/# \1/' | \
  sed 's/^.*\(listen_interface:\).*$/\1 eth0/' | \
  sed 's/^.*\(listen_interface_prefer_ipv6:\).*$/\1 false/' | \
  sed 's/^.*\(start_rpc:\).*$/\1 true/' | \
  sed 's/^.*\(rpc_address: .*\)$/# \1/' | \
  sed 's/^.*\(rpc_interface:\).*$/\1 eth0/' | \
  sed 's/^.*\(rpc_interface_prefer_ipv6:\).*/\1 false/' | \
  sed "s/^\(\s*- seeds:\).*$/\1 $addr/" | \
  sed 's/^.*\(authenticator:\).*$/\1 PasswordAuthenticator/' | \
  sed 's/^.*\(authorizer:\).*$/\1 CassandraAuthorizer/' >build/cassandra.yaml
rm build/cassandra.yaml.tmp
