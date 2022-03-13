from ProgrammingBitcoin.block import Block
from ProgrammingBitcoin.ecc import PrivateKey
from ProgrammingBitcoin.helper import hash256, little_endian_to_int, encode_varint, read_varint, decode_base58, SIGHASH_ALL
from ProgrammingBitcoin.network import (
    GetDataMessage,
    GetHeadersMessage,
    HeadersMessage,
    NetworkEnvelope,
    SimpleNode,
    TX_DATA_TYPE,
    FILTERED_BLOCK_DATA_TYPE,
)
from ProgrammingBitcoin.script import p2pkh_script, Script
from ProgrammingBitcoin.tx import Tx, TxIn, TxOut
from ProgrammingBitcoin.bloomfilter import BloomFilter
from ProgrammingBitcoin.merkleblock import MerkleBlock

import csv
import logging
import signal
from os.path import exists

try:
    from network_settings import HOST
except (ModuleNotFoundError, ImportError):
    with open("network_settings.py", "w") as net_file:
        net_file.write('HOST = "testnet.programmingbitcoin.com"')
        HOST = 'testnet.programmingbitcoin.com'

logging.basicConfig(filename='block.log', format='%(levelname)s:%(message)s', level=logging.DEBUG)

def start_log():
    start_block = "000000000000012ad603ddcc526791f6b2046a887999a284d60c44599536fced"
    start_height =  2164464 
    with open("block_log.csv", "w", newline="") as block_log:
        w = csv.writer(block_log)
        w.writerow((start_block, start_height))
    return start_block

def read_log(block_number):
    start_block = "0000000062043fb2e5091e43476e485ddc5d726339fd12bb010d5aeaf2be8206"
    try:
        with open('block_log.csv', 'r') as log_file:
            r = csv.reader(log_file)
            lines = list(r)
            return lines[block_number][0]
    except FileNotFoundError:
        return start_log()

def get_latest_block_hash():
    node = SimpleNode(HOST, testnet=True, logging=False)
    node.handshake()
    try:
        start_block = bytes.fromhex(read_log(-2))
    except FileNotFoundError:
        start_block = start_log()

    getheaders = GetHeadersMessage(start_block=start_block)
    node.send(getheaders)

    headers = node.wait_for(HeadersMessage)
    last_block = None 
    getdata = GetDataMessage()

    for block in headers.blocks:
        if not block.check_pow():
            raise RuntimeError('pow is invalid')
        if last_block is not None and block.prev_block != last_block:
            raise RuntimeError('chain broken')
        getdata.add_data(FILTERED_BLOCK_DATA_TYPE, block.hash())
        last_block = block.hash()
    return last_block.hex()

def get_known_height():
    with open("block_log.csv", "r") as block_log:
        r = csv.reader(block_log)
        blocks = list(r)
    return blocks[-1][1]

def get_known_hash():
    with open('block_log.csv', 'r') as block_log:
        r = csv.reader(block_log)
        blocks = list(r)
    return blocks[-1][0]

def get_hash_from_height(height):
    with open("block_log.csv", "r") as blocks:
        r = csv.reader(blocks)
        blocks = list(r)
        for block in blocks:
            if int(block[1]) == height:
                return block[0]

def is_synched():
    now_hash = get_latest_block_hash()
    then_hash = read_log(-1)
    if now_hash == then_hash:
        return True
    return False

def gap_exceeded(username):
    with open(f"{username}.csv", "r") as address_file:
        r = csv.reader(address_file)
        addresses = []
        for address in list(r):
            addresses.append(address[1])
    with open(f"{username}_utxos.csv", "r") as utxo_file:
        r = csv.reader(utxo_file)
        used = []
        for utxo in list(r):
            used.append(utxo[3])
        if used == []:
            return True, []
    total = len(addresses)
    latest = addresses.index(used[-1])
    if (total - latest < 20):
        return True, []
    for addr in used:
        addresses.remove(addr)
    oldest_unused_addr = addresses[0]
    return False, oldest_unused_addr 

def get_height(file, block_hash):
    with open(file, "r") as block_file:
        r = csv.reader(block_file)
        blocks = list(r)
    for block in blocks:
        if block[0] == block_hash:
            return int(block[1])
    return None

def read_fork_log(file, n):
    with open(file, "r") as block_file:
        r = csv.reader(block_file)
        blocks = list(r)
        return blocks[n][0]

def find_user(addr):
    with open('users.csv', 'r') as users_file:
        r = csv.reader(users_file)
        lines = list(r)
        for line in lines:
            user = line[0]
            with open(f'{user}.csv', 'r') as addr_file:
                r = csv.reader(addr_file)
                addrs = list(r)
                for a in addrs:
                    address = a[1]
                    if address == addr:
                        return user

def get_all_users():
    users = []
    try:
        with open('users.csv', 'r') as user_file:
            r = csv.reader(user_file)
            lines = list(r)
            for line in lines:
                users.append(line[0])
    except FileNotFoundError:
        pass
    return users

def get_all_addr():
    users = get_all_users()

    addresses = []
    for user in users:
        if user != "username":
            with open(f'{user}.csv', 'r') as users_file:
                r = csv.reader(users_file)
                lines = list(r)
                for line in lines:
                    addresses.append(line[1])
    return addresses

def handler(signum, frame):
    raise RuntimeError("timed out")

def get_block_hex(m):
    block = Block(m.version, m.prev_block, m.merkle_root, m.timestamp, m.bits, m.nonce)
    return block.hash().hex()

def prev_fork_hash(file):
    with open(file, "r") as fork:
        r = csv.reader(fork)
        hashes = list(r)
        return hashes[-1][0]

def get_forks():
    forks = []
    counter = 0
    not_found = True
    while not_found:
        if exists(f"fork_{counter}.csv"):
           forks.append(f"fork_{counter}.csv")
           counter += 1
        else:
            return forks

def make_fork_file(prev_block, fork_blocks):
    forks = get_forks()
    num = len(forks) 
    height = get_height("block_log.csv", prev_block)
    lines = []
    lines.append([prev_block, height])
    
    for block in fork_blocks:
        height += 1
        lines.append([block, height])

    with open(f"fork_{num}.csv", "w", newline="") as fork_file:
        w = csv.writer(fork_file)
        w.writerows(lines)

    return f"fork_{num}.csv"

def write_block(prev_block, block_hash):
    if read_log(-1) == prev_block:
        height = get_height('block_log.csv', prev_block) + 1
        with open("block_log.csv", "a", newline="") as block_file:
            w = csv.writer(block_file)
            w.writerow((block_hash, height))
        return None
    else:
        forks = get_forks()
        for fork in forks:
            if read_fork_log(fork, -1) == prev_block:
                height = get_height(fork, prev_block) + 1
                with open(fork, "a", newline="") as block_file:
                    w = csv.writer(block_file)
                    w.writerow((block_hash, height))
                return None
    # if new fork
    make_fork_file(prev_block, [block_hash])

def all_hashes():
    with open("block_log.csv", "r") as block_file:
        r = csv.reader(block_file)
        lines = list(r)
        blocks = []
        for line in lines:
            blocks.append(line[0])
    forks = get_forks()
    for fork in forks:
        with open(fork, "r") as block_file:
            r = csv.reader(block_file)
            lines = list(r)
            for line in lines:
                blocks.append(line[0])
    return blocks

def all_main_blocks():
    with open('block_log.csv', 'r') as block_file:
        r = csv.reader(block_file)
        blocks = list(r)
    return blocks

def need_reorg():
    main_height = get_height("block_log.csv", read_log(-1)) 
    old_forks = get_forks()
    highest = main_height
    forks = {}
    for fork in old_forks:
        block = read_fork_log(fork, -1)
        h = get_height(fork, block)
        forks[h] = fork 
        if h > highest:
            highest = h
    if forks != {}:
        if highest > main_height:
            return forks[highest]
    return None

def get_all_ids():
    users = get_all_users()
    ids = []
    for user in users:
        with open(f"{user}_utxos.csv", "r") as utxo_file:
            r = csv.reader(utxo_file)
            utxos = list(r)
            for utxo in utxos:
                ids.append([utxo[0], utxo[1], user])
    return ids

# set flag 0
def tx_set_new(user, tx_id, index, amount, address, scriptPubKey, block_hash):
    with open(f"{user}_utxos.csv", 'a', newline="") as utxo_file:
        w = csv.writer(utxo_file)
        w.writerow([tx_id, index, amount, address, scriptPubKey, block_hash, 0])

# set flag 1
def tx_set_confirmed(user, tx_id, index, amount, address, scriptPubKey, block_hash):
    with open(f"{user}_utxos.csv", 'r') as utxo_file:
        r = csv.reader(utxo_file)
        utxos = list(r)
        existing_index= None
        for i, utxo in enumerate(utxos):
            if utxo[0] == tx_id:
                existing_index = i
    if existing_index != None:
        utxos[existing_index][6] = 1
        utxos[existing_index][5] = block_hash
    else:
        utxos.append([tx_id, index, amount, address, scriptPubKey, block_hash, 1])
    with open(f"{user}_utxos.csv", 'w', newline="") as utxo_file:
        w = csv.writer(utxo_file)
        w.writerows(utxos)

# set other flags(2, 3, sometimes 0) 
def tx_set_flag(user, tx_id, flag, index=None):
    with open(f"{user}_utxos.csv", 'r') as utxo_file:
        r = csv.reader(utxo_file)
        utxos = list(r)
        for i, utxo in enumerate(utxos):
            if utxo[0] == tx_id and index != None and utxo[1] == index:
                existing_index = i
            elif utxo[0] == tx_id and index == None:
                existing_index = i
    utxos[existing_index][-1] = flag 
    with open(f"{user}_utxos.csv", 'w') as utxo_file:
        w = csv.writer(utxo_file)
        w.writerows(utxos)


def input_parser(current_addr, node):
    while True:
        try:
            message = node.wait_for(MerkleBlock, Tx)
            if message.command == b'merkleblock':
                merkle_block = message
                if not message.is_valid():
                    raise RuntimeError('invalid merkle proof')
            else:
                message.testnet = True
                ids = get_all_ids()
                for i, tx_out in enumerate(message.tx_outs):
                    for addr in current_addr:
                        if tx_out.script_pubkey.address(testnet=True) == addr:
                            prev_tx = message.hash().hex()
                            r_user = find_user(addr)
                            if prev_tx in old_utxos:
                                tx_set_flag(r_user,prev_tx, '1')
                                old_utxos.remove(prev_tx)
                            else:
                                prev_index = i
                                prev_amount = tx_out.amount
                                locking_script = tx_out.script_pubkey
                                block = get_block_hex(merkle_block)
                                tx_set_confirmed(r_user, prev_tx, index, prev_amount, addr, locking_script, block)
                    for i, tx_in in enumerate(message.tx_ins):
                        for tx_id in ids:
                            if tx_id[0] == tx_in.prev_tx.hex() and int(tx_id[1]) == tx_in.prev_index:
                                tx_set_flag(tx_id[2], tx_id[0], '3', tx_id[1])
        except SyntaxError:
            logging.info("recieved an invalid script")

def reorg(fork):
    node = SimpleNode(HOST, testnet=True, logging=False)
    with open(fork, "r") as fork_file:
        r = csv.reader(fork_file)
        fork_file= list(r)
        forking_point = fork_file[0]
    
    with open("block_log.csv", "r") as main_file:
        r = csv.reader(main_file)
        main_file = list(r)
    
    new_blocks = fork_file[1:]
    fork_file = [fork_file[0]]
    fork_len = len(new_blocks)
    main_len = len(main_file) - main_file.index(forking_point) - 1
    old_blocks = main_file[-main_len:]
    main_file= main_file[:-main_len]
    main_file = main_file + new_blocks 
    fork_file = fork_file + old_blocks

    # replace blocks in block file and fork file
    with open(fork, "w", newline="") as file:
        w = csv.writer(file)
        w.writerows(fork_file)
    with open("block_log.csv", "w", newline="") as file:
        w = csv.writer(file)
        w.writerows(main_file)
    old = [block[0] for block in old_blocks]
    # unconfirm utxos mined in blocks that were reorged out
    for user in get_all_users():
        old_utxos = []
        with open(f"{user}_utxos.csv", 'r') as utxo_file:
            r = csv.reader(utxo_file)
            utxos = list(r)
            for utxo in utxos:
                if utxo[5] in old:
                    old_utxos.append(utxo[0])
                    tx_set_flag(user, utxo[0], '0')
    # get utxos mined in the new blocks and figure out if any userss have been double-spent 
    current_addr = get_all_addr()
    bf = BloomFilter(size=30, function_count=5, tweak=1729)
    for addr in current_addr:
        bf.add(decode_base58(addr))
    node.send(bf.filterload())
    getdata = GetDataMessage()

    for block in new_blocks:
        getdata.add_data(FILTERED_BLOCK_DATA_TYPE, bytes.fromhex(block[0]))
    node.send(getdata)
    signal.signal(signal.SIGALRM, handler)
    signal.alarm(10)
    try:
        input_parser(current_addr, node)
    except RuntimeError:
        logging.info(f"a reorg of {main_len} blocks has occured")
        if old_utxos != []:
            logging.info(f"You may have been double spent with the following transactions: {old_utxos}")
