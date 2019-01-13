import rpc_pb2 as ln
import rpc_pb2_grpc as lnrpc
import grpc
import os
import json
import pprint
import json

from google.protobuf.json_format import MessageToJson
from tabulate import tabulate

# Due to updated ECDSA generated tls.cert we need to let gprc know that
# we need to use that cipher suite otherwise there will be a handhsake
# error when we communicate with the lnd rpc server.
os.environ["GRPC_SSL_CIPHER_SUITES"] = 'HIGH+ECDSA'

# Lnd cert is at ~/.lnd/tls.cert on Linux and
# ~/Library/Application Support/Lnd/tls.cert on Mac
cert = open(os.path.expanduser('~/.lnd/tls.cert'), 'rb').read()
creds = grpc.ssl_channel_credentials(cert)
channel = grpc.secure_channel('localhost:10009', creds)
stub = lnrpc.LightningStub(channel)

#####################
# To use macaroons: #
#####################

import codecs

# Lnd admin macaroon is at ~/.lnd/data/chain/bitcoin/simnet/admin.macaroon on Linux and
# ~/Library/Application Support/Lnd/data/chain/bitcoin/simnet/admin.macaroon on Mac
with open(os.path.expanduser('~/.lnd/data/chain/bitcoin/mainnet/admin.macaroon'), 'rb') as f:
    macaroon_bytes = f.read()
    macaroon = codecs.encode(macaroon_bytes, 'hex')

def metadata_callback(context, callback):
    # for more info see grpc docs
    callback([('macaroon', macaroon)], None)

# build ssl credentials using the cert the same as before
cert_creds = grpc.ssl_channel_credentials(cert)

# now build meta data credentials
auth_creds = grpc.metadata_call_credentials(metadata_callback)

# combine the cert credentials and the macaroon auth credentials
# such that every call is properly encrypted and authenticated
combined_creds = grpc.composite_channel_credentials(cert_creds, auth_creds)

# finally pass in the combined credentials when creating a channel
channel = grpc.secure_channel('localhost:10009', combined_creds)
stub = lnrpc.LightningStub(channel)


# -----------------
# Let's make an RPC
# -----------------

all_channel_info = stub.ListChannels(ln.ListChannelsRequest())
# print(all_channel_info)
# print(type(all_channel_info))

channel_json = MessageToJson(all_channel_info)
channel_dict = json.loads(channel_json)

active_remote = 0
active_local = 0
inactive_remote = 0
inactive_local = 0


# Calculate balances
for dict in channel_dict["channels"]:
    # for active channels:
    if "active" in dict:
        try:
            remote = int(dict["remote_balance"])
            active_remote += remote
            local = int(dict["local_balance"])
            active_local += local
        except:
            pass
    
    # for inactive channels
    else:
        try:
            remote = int(dict["remote_balance"])
            inactive_remote += remote
            local = int(dict["local_balance"])
            inactive_local += local
        except:
            pass

total_local = active_local + inactive_local
total_remote = active_remote + inactive_remote
total = total_remote + total_local

local_active_per = round((active_local / total_local) * 100, 2)
local_active_total = round((active_local / total) * 100, 2)
local_inactive_per = round((inactive_local / total_local) * 100, 2)
local_inactive_total = round((inactive_local / total) * 100, 2)

remote_active_per = round((active_remote / total_remote) * 100, 2)
remote_active_total = round((active_remote / total) * 100, 2)
remote_inactive_per = round((inactive_remote / total_remote) * 100, 2)
remote_inactive_total = round((inactive_remote / total) * 100, 2)

table = [["Balance\nLocation", "Channel\nState", "\nsatoshis", "% of\nLocation", "% of total\nbalance"],
         ['Local', 'active', "{:,}".format(active_local), local_active_per, local_active_total],
         ['Local', 'inactive', "{:,}".format(inactive_local), local_inactive_per, local_inactive_total],
         ['Remote', 'active', "{:,}".format(active_remote), remote_active_per, remote_active_total],
         ['Remote', 'inactive', "{:,}".format(inactive_remote), remote_inactive_per, remote_inactive_total]]
         

print(tabulate(table, headers="firstrow", tablefmt="grid"))


