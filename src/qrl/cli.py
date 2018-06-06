#!/usr/bin/env python3
import os
from collections import namedtuple
from decimal import Decimal
from typing import List

import click
import grpc
import simplejson as json
from google.protobuf.json_format import MessageToJson
from pyqrllib.pyqrllib import mnemonic2bin, hstr2bin, bin2hstr

from qrl.core import config
from qrl.core.Transaction import Transaction, TokenTransaction, TransferTokenTransaction, LatticePublicKey, \
    TransferTransaction, MessageTransaction, SlaveTransaction
from qrl.core.Wallet import Wallet
from qrl.core.misc.helper import parse_hexblob, parse_qaddress
from qrl.crypto.xmss import XMSS, hash_functions
from qrl.generated import qrl_pb2_grpc, qrl_pb2

ENV_QRL_WALLET_DIR = 'ENV_QRL_WALLET_DIR'

OutputMessage = namedtuple('OutputMessage',
                           'error address_items balance_items')

BalanceItem = namedtuple('BalanceItem',
                         'address balance')

CONNECTION_TIMEOUT = 5


class CLIContext(object):

    def __init__(self, remote, verbose, host, port_public, port_admin, wallet_dir, json):
        self.remote = remote
        self.verbose = verbose
        self.host = host
        self.port_public = port_public
        self.port_admin = port_admin

        self.wallet_dir = os.path.abspath(wallet_dir)
        self.wallet_path = os.path.join(self.wallet_dir, 'wallet.json')
        self.json = json

    @property
    def node_public_address(self):
        return '{}:{}'.format(self.host, self.port_public)

    @property
    def node_admin_address(self):
        return '{}:{}'.format(self.host, self.port_admin)

    @property
    def channel_public(self):
        return grpc.insecure_channel(self.node_public_address)

    @property
    def channel_admin(self):
        return grpc.insecure_channel(self.node_admin_address)

    def get_stub_admin_api(self):
        return qrl_pb2_grpc.AdminAPIStub(self.channel_admin)

    def get_stub_public_api(self):
        return qrl_pb2_grpc.PublicAPIStub(self.channel_public)


def _admin_get_local_addresses(ctx):
    try:
        stub = ctx.obj.get_stub_admin()
        getAddressStateResp = stub.GetLocalAddresses(qrl_pb2.GetLocalAddressesReq(), timeout=CONNECTION_TIMEOUT)
        return getAddressStateResp.addresses
    except Exception as e:
        click.echo('Error connecting to node', color='red')
        return []


def _print_error(ctx, error_descr, wallets=None):
    if ctx.obj.json:
        if wallets is None:
            wallets = []
        msg = {'error': error_descr, 'wallets': wallets}
        click.echo(json.dumps(msg))
    else:
        print("ERROR: {}".format(error_descr))


def _serialize_output(ctx, addresses: List[OutputMessage], source_description) -> dict:
    if len(addresses) == 0:
        msg = {'error': 'No wallet found at {}'.format(source_description), 'wallets': []}
        return msg

    msg = {'error': None, 'wallets': []}

    for pos, item in enumerate(addresses):
        try:
            balance_unshored = Decimal(_public_get_address_balance(ctx, item.qaddress)) / config.dev.shor_per_quanta
            balance = '{:5.8f}'.format(balance_unshored)
        except Exception as e:
            msg['error'] = str(e)
            balance = '?'

        msg['wallets'].append({
            'number': pos,
            'address': item.qaddress,
            'balance': balance,
            'hash_function': item.hashFunction
        })
    return msg


def _print_addresses(ctx, addresses: List[OutputMessage], source_description):
    def _normal(wallet):
        return "{:<8}{:<83}{:<13}".format(wallet['number'], wallet['address'], wallet['balance'])

    def _verbose(wallet):
        return "{:<8}{:<83}{:<13}{}".format(
            wallet['number'], wallet['address'], wallet['balance'], wallet['hash_function']
        )

    output = _serialize_output(ctx, addresses, source_description)
    if ctx.obj.json:
        output["location"] = source_description
        click.echo(json.dumps(output))
    else:
        if output['error'] and output['wallets'] == []:
            click.echo(output['error'])
        else:
            click.echo("Wallet at          : {}".format(source_description))
            if ctx.obj.verbose:
                header = "{:<8}{:<83}{:<13}{:<8}".format('Number', 'Address', 'Balance', 'Hash')
                divider = ('-' * 112)
            else:
                header = "{:<8}{:<83}{:<13}".format('Number', 'Address', 'Balance')
                divider = ('-' * 101)
            click.echo(header)
            click.echo(divider)

            for wallet in output['wallets']:
                if ctx.obj.verbose:
                    click.echo(_verbose(wallet))
                else:
                    click.echo(_normal(wallet))


def _public_get_address_balance(ctx, address):
    stub = ctx.obj.get_stub_public_api()
    getAddressStateReq = qrl_pb2.GetAddressStateReq(address=parse_qaddress(address))
    getAddressStateResp = stub.GetAddressState(getAddressStateReq, timeout=CONNECTION_TIMEOUT)
    return getAddressStateResp.state.balance


def _select_wallet(ctx, src):
    try:
        wallet = Wallet(wallet_path=ctx.obj.wallet_path)
        if not wallet.addresses:
            click.echo('This command requires a local wallet')
            return

        if wallet.encrypted:
            secret = click.prompt('The wallet is encrypted. Enter password', hide_input=True)
            wallet.decrypt(secret)

        if src.isdigit():
            src = int(src)
            try:
                # FIXME: This should only return pk and index
                xmss = wallet.get_xmss_by_index(src)
                return wallet.addresses[src], xmss
            except IndexError:
                click.echo('Wallet index not found', color='yellow')
                quit(1)

        elif src.startswith('Q'):
            for i, addr_item in enumerate(wallet.address_items):
                if src == addr_item.qaddress:
                    xmss = wallet.get_xmss_by_address(wallet.addresses[i])
                    return wallet.addresses[i], xmss
            click.echo('Source address not found in your wallet', color='yellow')
            quit(1)

        return parse_qaddress(src), None
    except Exception as e:
        click.echo("Error selecting wallet")
        quit(1)


def _shorize(x: Decimal) -> int:
    return int(x * int(config.dev.shor_per_quanta))


def _parse_dsts_amounts(addresses: str, amounts: str):
    """
    'Qaddr1 Qaddr2...' -> [\\xcx3\\xc2, \\xc2d\\xc3]
    '10 10' -> [10e9, 10e9] (in shor)
    :param addresses:
    :param amounts:
    :return:
    """
    addresses_split = []
    for addr in addresses.split(' '):
        addresses_split.append(parse_qaddress(addr))

    shor_amounts = []
    for amount in amounts.split(' '):
        shor_amounts.append(_shorize(float(amount)))

    if len(addresses_split) != len(shor_amounts):
        raise Exception("dsts and amounts should be the same length")
    return addresses_split, shor_amounts


########################
########################
########################
########################

@click.version_option(version=config.dev.version, prog_name='QRL Command Line Interface')
@click.group()
@click.option('--remote', '-r', default=False, is_flag=True, help='connect to remote node')
@click.option('--verbose', '-v', default=False, is_flag=True, help='verbose output whenever possible')
@click.option('--host', default='127.0.0.1', help='remote host address             [127.0.0.1]')
@click.option('--port_pub', default=9009, help='remote port number (public api) [9009]')
@click.option('--port_adm', default=9008, help='remote port number (admin api)  [9009]* will change')
@click.option('--wallet_dir', default='.', help='local wallet dir', envvar=ENV_QRL_WALLET_DIR)
@click.option('--json', default=False, is_flag=True, help='output in json')
@click.pass_context
def qrl(ctx, remote, verbose, host, port_pub, port_adm, wallet_dir, json):
    """
    QRL Command Line Interface
    """
    ctx.obj = CLIContext(remote=remote,
                         verbose=verbose,
                         host=host,
                         port_public=port_pub,
                         port_admin=port_adm,
                         wallet_dir=wallet_dir,
                         json=json)


@qrl.command()
@click.pass_context
def wallet_ls(ctx):
    """
    Lists available wallets
    """

    wallet = Wallet(wallet_path=ctx.obj.wallet_path)
    _print_addresses(ctx, wallet.address_items, ctx.obj.wallet_dir)


@qrl.command()
@click.pass_context
@click.option('--height', default=config.dev.xmss_tree_height,
              help='XMSS tree height. The resulting tree will be good for 2^height signatures')
@click.option('--hash_function', type=click.Choice(list(hash_functions.keys())), default='shake128',
              help='Hash function used to build the XMSS tree [default=shake128]')
@click.option('--encrypt', default=False, is_flag=True, help='Encrypts important fields with AES')
def wallet_gen(ctx, height, hash_function, encrypt):
    """
    Generates a new wallet with one address
    """
    if ctx.obj.remote:
        click.echo('This command is unsupported for remote wallets')
        return

    wallet = Wallet(wallet_path=ctx.obj.wallet_path)
    if len(wallet.address_items) > 0:
        click.echo("Wallet already exists")
        return

    wallet.add_new_address(height, hash_function)

    _print_addresses(ctx, wallet.address_items, config.user.wallet_dir)

    if encrypt:
        secret = click.prompt('Enter password to encrypt wallet with', hide_input=True, confirmation_prompt=True)
        wallet.encrypt(secret)

    wallet.save()


@qrl.command()
@click.option('--height', type=int, default=config.dev.xmss_tree_height, prompt=False)
@click.option('--hash_function', type=click.Choice(list(hash_functions.keys())), default='shake128',
              help='Hash function used to build the XMSS tree [default=shake128]')
@click.pass_context
def wallet_add(ctx, height, hash_function):
    """
    Adds an address or generates a new wallet (working directory)
    """
    if ctx.obj.remote:
        click.echo('This command is unsupported for remote wallets')
        return

    wallet = Wallet(wallet_path=ctx.obj.wallet_path)
    wallet_was_encrypted = wallet.encrypted
    if wallet.encrypted:
        secret = click.prompt('The wallet is encrypted. Enter password', hide_input=True)
        wallet.decrypt(secret)

    wallet.add_new_address(height, hash_function)

    _print_addresses(ctx, wallet.address_items, config.user.wallet_dir)

    if wallet_was_encrypted:
        wallet.encrypt(secret)

    wallet.save()


@qrl.command()
@click.option('--seed-type', type=click.Choice(['hexseed', 'mnemonic']), default='hexseed')
@click.pass_context
def wallet_recover(ctx, seed_type):
    """
    Recovers a wallet from a hexseed or mnemonic (32 words)
    """
    if ctx.obj.remote:
        click.echo('This command is unsupported for remote wallets')
        return

    seed = click.prompt('Please enter your %s' % (seed_type,))
    seed = seed.lower().strip()

    if seed_type == 'mnemonic':
        words = seed.split()
        if len(words) != 34:
            print('You have entered %s words' % (len(words),))
            print('Mnemonic seed must contain only 34 words')
            return
        bin_seed = mnemonic2bin(seed)
    else:
        if len(seed) != 102:
            print('You have entered hexseed of %s characters' % (len(seed),))
            print('Hexseed must be of only 102 characters.')
            return
        bin_seed = hstr2bin(seed)

    walletObj = Wallet(wallet_path=ctx.obj.wallet_path)

    recovered_xmss = XMSS.from_extended_seed(bin_seed)
    print('Recovered Wallet Address : %s' % (Wallet._get_Qaddress(recovered_xmss.address),))
    for addr in walletObj.address_items:
        if recovered_xmss.qaddress == addr.qaddress:
            print('Wallet Address is already in the wallet list')
            return

    if click.confirm('Do you want to save the recovered wallet?'):
        click.echo('Saving...')
        walletObj.append_xmss(recovered_xmss)
        walletObj.save()
        click.echo('Done')
        _print_addresses(ctx, walletObj.address_items, config.user.wallet_dir)


@qrl.command()
@click.option('--wallet-idx', default=0, prompt=True)
@click.pass_context
def wallet_secret(ctx, wallet_idx):
    """
    Provides the mnemonic/hexseed of the given address index
    """
    if ctx.obj.remote:
        click.echo('This command is unsupported for remote wallets')
        return

    wallet = Wallet(wallet_path=ctx.obj.wallet_path)
    if wallet.encrypted:
        secret = click.prompt('The wallet is encrypted. Enter password', hide_input=True)
        wallet.decrypt(secret)

    if 0 <= wallet_idx < len(wallet.address_items):
        address_item = wallet.address_items[wallet_idx]
        click.echo('Wallet Address  : %s' % (address_item.qaddress))
        click.echo('Mnemonic        : %s' % (address_item.mnemonic))
        click.echo('Hexseed         : %s' % (address_item.hexseed))
    else:
        click.echo('Wallet index not found', color='yellow')


@qrl.command()
@click.option('--wallet-idx', type=int, prompt=True, help='index of address in wallet')
@click.option('--skip-confirmation', default=False, is_flag=True, prompt=False, help='skip the confirmation prompt')
@click.pass_context
def wallet_rm(ctx, wallet_idx, skip_confirmation):
    """
    Removes an address from the wallet using the given address index.

    Warning! Use with caution. Removing an address from the wallet
    will result in loss of access to the address and is not
    reversible unless you have address recovery information.
    Use the wallet_secret command for obtaining the recovery Mnemonic/Hexseed and
    the wallet_recover command for restoring an address.
    """
    if ctx.obj.remote:
        click.echo('This command is unsupported for remote wallets')
        return

    wallet = Wallet(wallet_path=ctx.obj.wallet_path)

    if 0 <= wallet_idx < len(wallet.address_items):
        addr_item = wallet.address_items[wallet_idx]
        if not skip_confirmation:
            click.echo(
                'You are about to remove address [{0}]: {1} from the wallet.'.format(wallet_idx, addr_item.qaddress))
            click.echo(
                'Warning! By continuing, you risk complete loss of access to this address if you do not have a '
                'recovery Mnemonic/Hexseed.')
            click.confirm('Do you want to continue?', abort=True)
        wallet.remove(addr_item.qaddress)

        _print_addresses(ctx, wallet.address_items, config.user.wallet_dir)
    else:
        click.echo('Wallet index not found', color='yellow')


@qrl.command()
@click.pass_context
def wallet_encrypt(ctx):
    wallet = Wallet(wallet_path=ctx.obj.wallet_path)
    click.echo('Encrypting wallet at {}'.format(wallet.wallet_path))

    secret = click.prompt('Enter password', hide_input=True, confirmation_prompt=True)
    wallet.encrypt(secret)
    wallet.save()


@qrl.command()
@click.pass_context
def wallet_decrypt(ctx):
    wallet = Wallet(wallet_path=ctx.obj.wallet_path)
    click.echo('Decrypting wallet at {}'.format(wallet.wallet_path))

    secret = click.prompt('Enter password', hide_input=True)
    wallet.decrypt(secret)
    wallet.save()


@qrl.command()
@click.option('--src', type=str, default='', prompt=True, help='source address or index')
@click.option('--master', type=str, default='', prompt=True, help='master QRL address')
@click.option('--dst', type=str, prompt=True, help='List of destination addresses')
@click.option('--amounts', type=str, prompt=True, help='List of amounts to transfer (Quanta)')
@click.option('--fee', type=Decimal, default=0.0, prompt=True, help='fee in Quanta')
@click.option('--pk', default=0, prompt=False, help='public key (when local wallet is missing)')
@click.pass_context
def tx_prepare(ctx, src, master, dst, amounts, fee, pk):
    """
    Request a tx blob (unsigned) to transfer from src to dst (uses local wallet)
    """
    try:
        _, src_xmss = _select_wallet(ctx, src)
        if src_xmss:
            address_src_pk = src_xmss.pk
        else:
            address_src_pk = pk.encode()

        addresses_dst, shor_amounts = _parse_dsts_amounts(dst, amounts)
        master_addr = None
        if master:
            master_addr = parse_qaddress(master)

        fee_shor = _shorize(fee)
    except Exception as e:
        click.echo("Error validating arguments: {}".format(e))
        quit(1)

    try:
        tx = TransferTransaction.create(addrs_to=addresses_dst,
                                        amounts=shor_amounts,
                                        fee=fee_shor,
                                        xmss_pk=address_src_pk,
                                        master_addr=master_addr)
    except Exception as e:
        click.echo("Unhandled error: {}".format(str(e)))
        quit(1)

    txblob = bin2hstr(tx.pbdata.SerializeToString())
    print(txblob)


@qrl.command()
@click.option('--src', type=str, default='', prompt=True, help='source address or index')
@click.option('--master', type=str, default='', prompt=True, help='master QRL address')
@click.option('--number_of_slaves', default=0, type=int, prompt=True, help='Number of slaves addresses')
@click.option('--access_type', default=0, type=int, prompt=True, help='0 - All Permission, 1 - Only Mining Permission')
@click.option('--fee', type=Decimal, default=0.0, prompt=True, help='fee (Quanta)')
@click.option('--pk', default=0, prompt=False, help='public key (when local wallet is missing)')
@click.option('--otsidx', default=0, prompt=False, help='OTS index (when local wallet is missing)')
@click.pass_context
def slave_tx_generate(ctx, src, master, number_of_slaves, access_type, fee, pk, otsidx):
    """
    Generates Slave Transaction for the wallet
    """
    try:
        _, src_xmss = _select_wallet(ctx, src)
        src_xmss.set_ots_index(otsidx)
        if src_xmss:
            address_src_pk = src_xmss.pk
        else:
            address_src_pk = pk.encode()

        master_addr = parse_qaddress(master)
        fee_shor = _shorize(fee)
    except Exception as e:
        click.echo("Error validating arguments: {}".format(e))
        quit(1)

    slave_xmss = []
    slave_pks = []
    access_types = []
    slave_xmss_seed = []
    if number_of_slaves > 100:
        click.echo("Error: Max Limit for the number of slaves is 100")
        quit(1)

    for i in range(number_of_slaves):
        print("Generating Slave #" + str(i + 1))
        xmss = XMSS.from_height(config.dev.xmss_tree_height)
        slave_xmss.append(xmss)
        slave_xmss_seed.append(xmss.extended_seed)
        slave_pks.append(xmss.pk)
        access_types.append(access_type)
        print("Successfully Generated Slave %s/%s" % (str(i + 1), number_of_slaves))

    try:
        tx = SlaveTransaction.create(slave_pks=slave_pks,
                                     access_types=access_types,
                                     fee=fee_shor,
                                     xmss_pk=address_src_pk,
                                     master_addr=master_addr)
        tx.sign(src_xmss)
        with open('slaves.json', 'w') as f:
            json.dump([bin2hstr(src_xmss.address), slave_xmss_seed, tx.to_json()], f)
        click.echo('Successfully created slaves.json')
        click.echo('Move slaves.json file from current directory to the mining node inside ~/.qrl/')
    except Exception as e:
        click.echo("Unhandled error: {}".format(str(e)))
        quit(1)


@qrl.command()
@click.option('--src', type=str, default='', prompt=True, help='signing address index')
@click.option('--txblob', type=str, default='', prompt=True, help='transaction blob (unsigned)')
@click.pass_context
def tx_sign(ctx, src, txblob):
    """
    Sign a tx blob
    """
    txbin = parse_hexblob(txblob)
    pbdata = qrl_pb2.Transaction()
    pbdata.ParseFromString(txbin)
    tx = Transaction.from_pbdata(pbdata)

    address_src, address_xmss = _select_wallet(ctx, src)
    tx.sign(address_xmss)

    txblob = bin2hstr(tx.pbdata.SerializeToString())
    print(txblob)


@qrl.command()
@click.option('--txblob', type=str, default='', prompt=True, help='transaction blob (unsigned)')
@click.pass_context
def tx_inspect(ctx, txblob):
    """
    Inspected a transaction blob
    """
    tx = None
    try:
        txbin = parse_hexblob(txblob)
        pbdata = qrl_pb2.Transaction()
        pbdata.ParseFromString(txbin)
        tx = Transaction.from_pbdata(pbdata)
    except Exception as e:
        click.echo("tx blob is not valid")
        quit(1)

    tmp_json = tx.to_json()
    # FIXME: binary fields are represented in base64. Improve output
    print(tmp_json)


@qrl.command()
@click.option('--txblob', type=str, default='', prompt=True, help='transaction blob (unsigned)')
@click.pass_context
def tx_push(ctx, txblob):
    tx = None
    try:
        txbin = parse_hexblob(txblob)
        pbdata = qrl_pb2.Transaction()
        pbdata.ParseFromString(txbin)
        tx = Transaction.from_pbdata(pbdata)
    except Exception as e:
        click.echo("tx blob is not valid")
        quit(1)

    tmp_json = tx.to_json()
    # FIXME: binary fields are represented in base64. Improve output
    print(tmp_json)
    if len(tx.signature) == 0:
        click.echo('Signature missing')
        quit(1)

    stub = ctx.obj.get_stub_public_api()
    pushTransactionReq = qrl_pb2.PushTransactionReq(transaction_signed=tx.pbdata)
    pushTransactionResp = stub.PushTransaction(pushTransactionReq, timeout=CONNECTION_TIMEOUT)
    print(pushTransactionResp.error_code)


@qrl.command()
@click.option('--src', type=str, default='', prompt=True, help='signer QRL address')
@click.option('--master', type=str, default='', prompt=True, help='master QRL address')
@click.option('--message', type=str, prompt=True, help='Message (max 80 bytes)')
@click.option('--fee', type=Decimal, default=0.0, prompt=True, help='fee in Quanta')
@click.option('--ots_key_index', default=0, prompt=True, help='OTS key Index')
@click.pass_context
def tx_message(ctx, src, master, message, fee, ots_key_index):
    """
    Message Transaction
    """
    if not ctx.obj.remote:
        click.echo('This command is unsupported for local wallets')
        return

    try:
        _, src_xmss = _select_wallet(ctx, src)
        if not src_xmss:
            click.echo("A local wallet is required to sign the transaction")
            quit(1)

        address_src_pk = src_xmss.pk
        src_xmss.set_ots_index(ots_key_index)

        message = message.encode()

        master_addr = parse_qaddress(master)
        fee_shor = _shorize(fee)
    except Exception as e:
        click.echo("Error validating arguments: {}".format(e))
        quit(1)

    try:
        stub = ctx.obj.get_stub_public_api()
        tx = MessageTransaction.create(message_hash=message,
                                       fee=fee_shor,
                                       xmss_pk=address_src_pk,
                                       master_addr=master_addr)
        tx.sign(src_xmss)

        push_transaction_req = qrl_pb2.PushTransactionReq(transaction_signed=tx.pbdata)
        push_transaction_resp = stub.PushTransaction(push_transaction_req, timeout=CONNECTION_TIMEOUT)

        print(push_transaction_resp)
    except Exception as e:
        print("Error {}".format(str(e)))


@qrl.command()
@click.option('--src', type=str, default='', prompt=True, help='signer QRL address')
@click.option('--master', type=str, default='', prompt=True, help='master QRL address')
@click.option('--dst', type=str, prompt=True, help='List of destination addresses')
@click.option('--amounts', type=str, prompt=True, help='List of amounts to transfer (Quanta)')
@click.option('--fee', type=Decimal, default=0.0, prompt=True, help='fee in Quanta')
@click.option('--ots_key_index', default=0, prompt=True, help='OTS key Index')
@click.pass_context
def tx_transfer(ctx, src, master, dst, amounts, fee, ots_key_index):
    """
    Transfer coins from src to dst
    """
    if not ctx.obj.remote:
        click.echo('This command is unsupported for local wallets')
        return

    try:
        _, src_xmss = _select_wallet(ctx, src)
        if not src_xmss:
            click.echo("A local wallet is required to sign the transaction")
            quit(1)

        address_src_pk = src_xmss.pk
        src_xmss.set_ots_index(ots_key_index)

        addresses_dst, shor_amounts = _parse_dsts_amounts(dst, amounts)
        master_addr = None
        if master:
            master_addr = parse_qaddress(master)
        fee_shor = _shorize(fee)
    except Exception as e:
        click.echo("Error validating arguments: {}".format(e))
        quit(1)

    try:
        stub = ctx.obj.get_stub_public_api()

        tx = TransferTransaction.create(addrs_to=addresses_dst,
                                        amounts=shor_amounts,
                                        fee=fee_shor,
                                        xmss_pk=address_src_pk,
                                        master_addr=master_addr)
        tx.sign(src_xmss)

        push_transaction_req = qrl_pb2.PushTransactionReq(transaction_signed=tx.pbdata)
        push_transaction_resp = stub.PushTransaction(push_transaction_req, timeout=CONNECTION_TIMEOUT)

        print(push_transaction_resp)
    except Exception as e:
        print("Error {}".format(str(e)))


@qrl.command()
@click.option('--src', type=str, default='', prompt=True, help='source QRL address')
@click.option('--master', type=str, default='', prompt=True, help='master QRL address')
@click.option('--symbol', default='', prompt=True, help='Symbol Name')
@click.option('--name', default='', prompt=True, help='Token Name')
@click.option('--owner', default='', prompt=True, help='Owner QRL address')
@click.option('--decimals', default=0, prompt=True, help='decimals')
@click.option('--fee', type=Decimal, default=0.0, prompt=True, help='fee in Quanta')
@click.option('--ots_key_index', default=0, prompt=True, help='OTS key Index')
@click.pass_context
def tx_token(ctx, src, master, symbol, name, owner, decimals, fee, ots_key_index):
    """
    Create Token Transaction, that results into the formation of new token if accepted.
    """

    if not ctx.obj.remote:
        click.echo('This command is unsupported for local wallets')
        return

    initial_balances = []

    while True:
        address = click.prompt('Address ', default='')
        if address == '':
            break
        amount = int(click.prompt('Amount ')) * (10 ** int(decimals))
        initial_balances.append(qrl_pb2.AddressAmount(address=parse_qaddress(address),
                                                      amount=amount))

    try:
        _, src_xmss = _select_wallet(ctx, src)
        if not src_xmss:
            click.echo("A local wallet is required to sign the transaction")
            quit(1)

        address_src_pk = src_xmss.pk
        src_xmss.set_ots_index(int(ots_key_index))
        address_owner = parse_qaddress(owner)
        master_addr = None
        if master_addr:
            master_addr = parse_qaddress(master)
        # FIXME: This could be problematic. Check
        fee_shor = _shorize(fee)

        if len(name) > config.dev.max_token_name_length:
            raise Exception("Token name must be shorter than {} chars".format(config.dev.max_token_name_length))
        if len(symbol) > config.dev.max_token_name_length:
            raise Exception("Token symbol must be shorter than {} chars".format(config.dev.max_token_name_length))

    except KeyboardInterrupt:
        click.echo("Terminated by user")
        quit(1)
    except Exception as e:
        click.echo("Error validating arguments: {}".format(e))
        quit(1)

    try:
        stub = ctx.obj.get_stub_public_api()
        tx = TokenTransaction.create(symbol=symbol.encode(),
                                     name=name.encode(),
                                     owner=address_owner,
                                     decimals=decimals,
                                     initial_balances=initial_balances,
                                     fee=fee_shor,
                                     xmss_pk=address_src_pk,
                                     master_addr=master_addr)

        tx.sign(src_xmss)

        push_transaction_req = qrl_pb2.PushTransactionReq(transaction_signed=tx.pbdata)
        push_transaction_resp = stub.PushTransaction(push_transaction_req, timeout=CONNECTION_TIMEOUT)

        print(push_transaction_resp.error_code)
    except Exception as e:
        print("Error {}".format(str(e)))


@qrl.command()
@click.option('--src', type=str, default='', prompt=True, help='source QRL address')
@click.option('--master', type=str, default='', prompt=True, help='master QRL address')
@click.option('--token_txhash', default='', prompt=True, help='Token Txhash')
@click.option('--dst', type=str, prompt=True, help='List of destination addresses')
@click.option('--amounts', type=str, prompt=True, help='List of amounts to transfer (Quanta)')
@click.option('--decimals', default=0, prompt=True, help='decimals')
@click.option('--fee', type=Decimal, default=0.0, prompt=True, help='fee in Quanta')
@click.option('--ots_key_index', default=0, prompt=True, help='OTS key Index')
@click.pass_context
def tx_transfertoken(ctx, src, master, token_txhash, dst, amounts, decimals, fee, ots_key_index):
    """
    Create Transfer Token Transaction, which moves tokens from src to dst.
    """

    if not ctx.obj.remote:
        click.echo('This command is unsupported for local wallets')
        return

    try:
        _, src_xmss = _select_wallet(ctx, src)
        if not src_xmss:
            click.echo("A local wallet is required to sign the transaction")
            quit(1)

        address_src_pk = src_xmss.pk
        src_xmss.set_ots_index(int(ots_key_index))
        addresses_dst = []
        for addr in dst.split(' '):
            addresses_dst.append(parse_qaddress(addr))

        shor_amounts = []
        for amount in amounts.split(' '):
            shor_amounts.append(int(float(amount) * (10 ** int(decimals))))

        if len(addresses_dst) != len(shor_amounts):
            raise Exception("{} destination addresses specified but only {} amounts given".format(len(addresses_dst),
                                                                                                  len(shor_amounts)))

        bin_token_txhash = parse_hexblob(token_txhash)
        master_addr = None
        if master:
            master_addr = parse_qaddress(master)
        # FIXME: This could be problematic. Check
        fee_shor = _shorize(fee)
    except KeyboardInterrupt:
        click.echo("Terminated by user")
        quit(1)
    except Exception as e:
        click.echo("Error validating arguments: {}".format(e))
        quit(1)

    try:
        stub = ctx.obj.get_stub_public_api()
        tx = TransferTokenTransaction.create(token_txhash=bin_token_txhash,
                                             addrs_to=addresses_dst,
                                             amounts=shor_amounts,
                                             fee=fee_shor,
                                             xmss_pk=address_src_pk,
                                             master_addr=master_addr)
        tx.sign(src_xmss)

        push_transaction_req = qrl_pb2.PushTransactionReq(transaction_signed=tx.pbdata)
        push_transaction_resp = stub.PushTransaction(push_transaction_req, timeout=CONNECTION_TIMEOUT)

        print(push_transaction_resp.error_code)
    except Exception as e:
        print("Error {}".format(str(e)))


@qrl.command()
@click.option('--owner', default='', prompt=True, help='source QRL address')
@click.pass_context
def token_list(ctx, owner):
    """
    Fetch the list of tokens owned by an address.
    """

    if not ctx.obj.remote:
        click.echo('This command is unsupported for local wallets')
        return

    try:
        owner_address = parse_qaddress(owner)
    except Exception as e:
        click.echo("Error validating arguments: {}".format(e))
        quit(1)

    try:
        stub = ctx.obj.get_stub_public_api()
        address_state_req = qrl_pb2.GetAddressStateReq(address=owner_address)
        address_state_resp = stub.GetAddressState(address_state_req, timeout=CONNECTION_TIMEOUT)

        for token_hash in address_state_resp.state.tokens:
            click.echo('Hash: %s' % (token_hash,))
            click.echo('Balance: %s' % (address_state_resp.state.tokens[token_hash],))
    except Exception as e:
        print("Error {}".format(str(e)))


@qrl.command()
@click.option('--src', type=str, default='', prompt=True, help='source QRL address')
@click.option('--master', type=str, default='', prompt=True, help='master QRL address')
@click.option('--kyber-pk', default='', prompt=True, help='kyber public key')
@click.option('--dilithium-pk', default='', prompt=True, help='dilithium public key')
@click.option('--fee', type=Decimal, default=0.0, prompt=True, help='fee in Quanta')
@click.option('--ots_key_index', default=0, prompt=True, help='OTS key Index')
@click.pass_context
def tx_latticepk(ctx, src, master, kyber_pk, dilithium_pk, fee, ots_key_index):
    """
    Create Lattice Public Keys Transaction
    """
    if not ctx.obj.remote:
        click.echo('This command is unsupported for local wallets')
        return

    try:
        _, src_xmss = _select_wallet(ctx, src)
        if not src_xmss:
            click.echo("A local wallet is required to sign the transaction")
            quit(1)

        address_src_pk = src_xmss.pk
        src_xmss.set_ots_index(ots_key_index)
        kyber_pk = kyber_pk.encode()
        dilithium_pk = dilithium_pk.encode()
        master_addr = None
        if master:
            master_addr = parse_qaddress(master)
        # FIXME: This could be problematic. Check
        fee_shor = _shorize(fee)
    except Exception as e:
        click.echo("Error validating arguments: {}".format(e))
        quit(1)

    try:
        tx = LatticePublicKey.create(fee=fee_shor,
                                     kyber_pk=kyber_pk,
                                     dilithium_pk=dilithium_pk,
                                     xmss_pk=address_src_pk,
                                     master_addr=master_addr)
        tx.sign(src_xmss)

        stub = ctx.obj.get_stub_public_api()
        push_transaction_req = qrl_pb2.PushTransactionReq(transaction_signed=tx.pbdata)
        push_transaction_resp = stub.PushTransaction(push_transaction_req, timeout=CONNECTION_TIMEOUT)

        print(push_transaction_resp.error_code)
    except Exception as e:
        print("Error {}".format(str(e)))


@qrl.command()
@click.pass_context
def state(ctx):
    """
    Shows Information about a Node's State
    """
    stub = ctx.obj.get_stub_public_api()
    nodeStateResp = stub.GetNodeState(qrl_pb2.GetNodeStateReq())

    if ctx.obj.json:
        click.echo(MessageToJson(nodeStateResp, sort_keys=True))
    else:
        click.echo(nodeStateResp)


def main():
    qrl()


if __name__ == '__main__':
    main()
