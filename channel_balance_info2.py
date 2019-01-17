import codecs
import json
import os
import sys
import pprint

import grpc
from google.protobuf.json_format import MessageToJson
from tabulate import tabulate

import rpc_pb2 as ln
import rpc_pb2_grpc as lnrpc

#-------------------------
# Generate RPC credentials
#-------------------------

# tell gRPC which cypher suite to use
os.environ["GRPC_SSL_CIPHER_SUITES"] = 'HIGH+ECDSA'

# grab tls cert
cert = open(os.path.expanduser('~/.lnd/tls.cert'), 'rb').read()

# grab the macaroon file for authentication
# change path if running on testnet or other network
with open(os.path.expanduser('~/.lnd/data/chain/bitcoin/mainnet/admin.macaroon'), 'rb') as f:
    macaroon_bytes = f.read()
    macaroon = codecs.encode(macaroon_bytes, 'hex')

# helper function to return the macaroon when requested
def metadata_callback(context, callback):
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

# ----------------
# Channel Balances
# ----------------

# get channel data and format to dict
channel_data = stub.ListChannels(ln.ListChannelsRequest())
channel_json = MessageToJson(channel_data)
channel_dict = json.loads(channel_json)

# initialize variables
r_active = 0
l_active = 0
r_inactive = 0
l_inactive = 0

# calculate channel balances
for dict in channel_dict["channels"]:
    # for active channels:
    if "active" in dict:
        try:
            remote = int(dict["remote_balance"])
            r_active += remote
            local = int(dict["local_balance"])
            l_active += local
        except:
            pass

    # for inactive channels
    else:
        try:
            remote = int(dict["remote_balance"])
            r_inactive += remote
            local = int(dict["local_balance"])
            l_inactive += local
        except:
            pass

# calculate totals
total_l = l_active + l_inactive
total_r = r_active + r_inactive
total_all_chan = total_r + total_l

# --------------
# Wallet Balance
# --------------

# grab (on-chain) wallet data to dict
wallet_data = stub.WalletBalance(ln.WalletBalanceRequest())
wallet_json = MessageToJson(wallet_data)
wallet_dict = json.loads(wallet_json)

wallet_conf = int(wallet_dict["confirmed_balance"])
wallet_total = int(wallet_dict["total_balance"])
wallet_conf_p = round((wallet_conf / wallet_total) * 100, 2)

node_total = wallet_total + total_all_chan


# ---------------------
# calculate percentages
# ---------------------

def p2dp(x, y):
    return round((x / y) * 100, 2)

# local active
l_active_p = p2dp(l_active, total_l)
l_active_total = p2dp(l_active, total_all_chan)
l_active_node_p = p2dp(l_active, node_total)

# local inactive
l_inactive_node_p = p2dp(l_inactive, node_total)
l_inactive_p = p2dp(l_inactive, total_l)
l_inactive_total = p2dp(l_inactive, total_all_chan)

# remote active
r_active_node_p = p2dp(r_active, node_total)
r_active_p = p2dp(r_active, total_r)
r_active_total = p2dp(r_active, total_all_chan)

# remote inactive
r_inactive_node_p = p2dp(r_inactive, node_total)
r_inactive_p = p2dp(r_inactive, total_r)
r_inactive_total = p2dp(r_inactive, total_all_chan)

# on-chain wallet
wallet_conf_node_p = p2dp(wallet_conf, node_total)
wallet_total_node_p = p2dp(wallet_total, node_total)


# --------------
# create outputs
# --------------

def create_table():
    balance_table = [["\nBalance\nLocation", "\nChannel\nState", "\n\nsatoshis",
                      "\n(%)\nLocation", "(%)\nChannel\ntotal", "(%)\nNode\ntotal"],
                     ['Local channel', 'active', "{:,}".format(l_active),
                      l_active_p, l_active_total, l_active_node_p],
                     ['Local channel', 'inactive', "{:,}".format(l_inactive),
                      l_inactive_p, l_inactive_total, l_inactive_node_p],
                     ['Remote channel', 'active', "{:,}".format(r_active),
                      r_active_p, r_active_total, r_active_node_p],
                     ['Remote channel', 'inactive', "{:,}".format(r_inactive),
                      r_inactive_p, r_inactive_total, r_inactive_node_p],
                     ['Local Wallet', 'confirmed', "{:,}".format(wallet_conf),
                      wallet_conf_p, 0, 0],
                     ['Local Wallet', 'total', "{:,}".format(wallet_total), 100, 0,
                      wallet_total_node_p]]

def create_dict():
    balance_dict = {'Local active':  {'satoshis': "{:,}".format(l_active),
                                      '(%) Location': l_active_p,
                                      '(%) Channel total': l_active_total,
                                      '(%) Node total': l_active_node_p},
                    'Local inactive': {'satoshis': "{:,}".format(l_inactive),
                                       '(%) Location': l_inactive_p,
                                       '(%) Channel total': l_inactive_total,
                                       '(%) Node total': l_inactive_node_p},
                    'Remote active':  {'satoshis': "{:,}".format(r_active),
                                       '(%) Location': r_active_p,
                                       '(%) Channel total': r_active_total,
                                       '(%) Node total': r_active_node_p},
                    'Remote inactive': {'satoshis': "{:,}".format(r_inactive),
                                        '(%) Location': r_inactive_p,
                                        '(%) Channel total': r_inactive_total,
                                        '(%) Node total': r_inactive_node_p},
                    'Wallet confirmed': {'satoshis': "{:,}".format(wallet_conf),
                                         '(%) Location': wallet_conf_p,
                                         '(%) Channel total': 0,
                                         '(%) Node total': 0},
                    'Wallet total': {'satoshis': "{:,}".format(wallet_total),
                                         '(%) Location': wallet_total_node_p,
                                         '(%) Channel total': 100,
                                         '(%) Node total': 0},
    }

def create_json():
    # Double quotes and other JSON-specific formatting
    json_balance_dict = json.dumps(balance_dict)


def main():
    try:
        if sys.argv[1] == "table":
            create_table()
            print(tabulate(balance_table, headers="firstrow", tablefmt="grid"))
        if sys.argv[1] == "dict":
            create_dict()
            print(balance_dict)
        if sys.argv[1] == "json":
            create_json()
            print(json_balance_dict)
    except:
        #print('Please provide an argument')
        #return


if __name__ == "__main__":
    # execute only if run as a script
    main()

