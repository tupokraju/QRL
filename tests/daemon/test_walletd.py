# coding=utf-8
# Distributed under the MIT software license, see the accompanying
# file LICENSE or http://www.opensource.org/licenses/mit-license.php.
from unittest import TestCase

from mock import Mock
from pyqrllib.pyqrllib import bin2hstr

from qrl.daemon.walletd import WalletD
from qrl.generated import qrl_pb2
from qrl.core.txs.TransferTransaction import TransferTransaction
from qrl.core.Wallet import WalletDecryptionError
from qrl.core.misc import logger
from tests.misc.helper import set_qrl_dir, get_alice_xmss, get_bob_xmss

logger.initialize_default()


class TestWalletD(TestCase):
    def __init__(self, *args, **kwargs):
        self.passphrase = '你好'
        self.qaddress = "Q010400ff39df1ba4d1d5b8753e6d04c51c34b95b01fc3650c10ca7b296a18bdc105412c59d0b3b"
        self.hex_seed = "0104008441d43524996f76236141d16b7b324323abf796e77ad" \
                        "7c874622a82f5744bb803f9b404d25733d0db82be7ac6f3c4cf"
        self.mnemonic = "absorb drank lute brick cure evil inept group grey " \
                        "breed hood reefy eager depict weed image law legacy " \
                        "jockey calm lover freeze fact lively wide dread spiral " \
                        "jaguar span rinse salty pulsar violet fare"
        super(TestWalletD, self).__init__(*args, **kwargs)

    def test_init(self):
        with set_qrl_dir("wallet_ver1"):
            walletd = WalletD()
            self.assertIsNotNone(walletd)

    def test_qaddress_to_address(self):
        with set_qrl_dir("wallet_ver1"):
            walletd = WalletD()
            qaddress = "Q010600968c3408cba5192d75c11cec909e803fc590e82463216b5a04ce8e447f76b4e02c0d3d81"
            address = walletd.qaddress_to_address(qaddress)
            self.assertEqual(qaddress[1:], bin2hstr(address))

    def test_authenticate(self):
        with set_qrl_dir("wallet_ver1"):
            walletd = WalletD()
            walletd.authenticate()

            walletd._wallet = Mock()
            walletd._wallet.encrypted = Mock(return_value=True)
            with self.assertRaises(ValueError):
                walletd.authenticate()

    def test_encrypt_last_item(self):
        with set_qrl_dir("wallet_ver1"):
            walletd = WalletD()
            walletd.authenticate()

            walletd.add_new_address(height=4)
            self.assertFalse(walletd.get_wallet_info()[2])
            walletd._passphrase = self.passphrase
            walletd._encrypt_last_item()
            self.assertTrue(walletd.get_wallet_info()[2])

    def test_get_wallet_index_xmss(self):
        with set_qrl_dir("wallet_ver1"):
            walletd = WalletD()
            qaddress = walletd.add_new_address(height=4)
            index, xmss = walletd._get_wallet_index_xmss(qaddress, 0)
            self.assertEqual(index, 0)
            self.assertEqual(xmss.qaddress, qaddress)

    def test_add_new_address(self):
        with set_qrl_dir("wallet_ver1"):
            walletd = WalletD()
            qaddress = walletd.add_new_address(height=4)
            self.assertEqual(qaddress[0], 'Q')

            self.assertEqual(len(walletd.list_address()), 1)

    def test_add_new_address2(self):
        with set_qrl_dir("wallet_ver1"):
            walletd = WalletD()
            qaddress = walletd.add_new_address(height=4)
            self.assertEqual(qaddress[0], 'Q')

            self.assertEqual(len(walletd.list_address()), 1)

            qaddress = walletd.add_new_address(height=4)
            self.assertEqual(qaddress[0], 'Q')

            self.assertEqual(len(walletd.list_address()), 2)

    def test_add_address_from_seed(self):
        with set_qrl_dir("wallet_ver1"):
            walletd = WalletD()

            qaddress1 = walletd.add_address_from_seed(seed=self.hex_seed)  # Using hexseed
            self.assertEqual(self.qaddress, qaddress1)

            self.assertEqual(len(walletd.list_address()), 1)

    def test_add_address_from_seed2(self):
        with set_qrl_dir("wallet_ver1"):
            walletd = WalletD()

            qaddress1 = walletd.add_address_from_seed(seed=self.hex_seed)  # Using hexseed
            self.assertEqual(self.qaddress, qaddress1)

            self.assertEqual(len(walletd.list_address()), 1)

            walletd.remove_address(self.qaddress)
            self.assertEqual(len(walletd.list_address()), 0)

            qaddress2 = walletd.add_address_from_seed(seed=self.mnemonic)  # Using mnemonic
            self.assertEqual(self.qaddress, qaddress2)

            self.assertEqual(len(walletd.list_address()), 1)

    def test_list_address(self):
        with set_qrl_dir("wallet_ver1"):
            walletd = WalletD()
            qaddress = walletd.add_new_address(height=4)
            self.assertEqual(qaddress[0], 'Q')

            self.assertEqual(len(walletd.list_address()), 1)
            list_address = walletd.list_address()
            self.assertEqual(list_address[0], qaddress)

    def test_remove_address(self):
        with set_qrl_dir("wallet_ver1"):
            walletd = WalletD()
            qaddress = walletd.add_new_address(height=4)
            self.assertEqual(qaddress[0], 'Q')

            self.assertEqual(len(walletd.list_address()), 1)

            result = walletd.remove_address(qaddress)
            self.assertTrue(result)

            self.assertEqual(len(walletd.list_address()), 0)

    def test_remove_address2(self):
        with set_qrl_dir("wallet_ver1"):
            walletd = WalletD()
            qaddress = walletd.add_new_address(height=4)
            self.assertEqual(qaddress[0], 'Q')

            self.assertEqual(len(walletd.list_address()), 1)

            result = walletd.remove_address(qaddress)
            self.assertTrue(result)

            self.assertEqual(len(walletd.list_address()), 0)

            result = walletd.remove_address("Q123")
            self.assertFalse(result)

            self.assertEqual(len(walletd.list_address()), 0)

    def test_get_recovery_seeds(self):
        with set_qrl_dir("wallet_ver1"):
            walletd = WalletD()
            qaddress = walletd.add_new_address(height=4)
            self.assertEqual(qaddress[0], 'Q')

            seeds = walletd.get_recovery_seeds(qaddress)
            self.assertIsInstance(seeds, tuple)
            walletd.remove_address(qaddress)
            self.assertEqual(len(walletd.list_address()), 0)

            qaddress2 = walletd.add_address_from_seed(seeds[0])  # Using Hex Seed
            self.assertEqual(qaddress, qaddress2)
            walletd.remove_address(qaddress2)
            self.assertEqual(len(walletd.list_address()), 0)

            qaddress2 = walletd.add_address_from_seed(seeds[1])  # Using Mnemonic
            self.assertEqual(qaddress, qaddress2)
            walletd.remove_address(qaddress2)
            self.assertEqual(len(walletd.list_address()), 0)

    def test_get_wallet_info(self):
        with set_qrl_dir("wallet_ver1"):
            walletd = WalletD()
            version, len_address_items, encrypted = walletd.get_wallet_info()
            self.assertEqual(version, 1)
            self.assertEqual(len_address_items, 0)
            self.assertFalse(encrypted)

    def test_push_transaction(self):
        with set_qrl_dir("wallet_ver1"):
            walletd = WalletD()
            alice_xmss = get_alice_xmss()
            bob_xmss = get_bob_xmss()
            tx = TransferTransaction.create(addrs_to=[bob_xmss.address],
                                            amounts=[1],
                                            fee=1,
                                            xmss_pk=alice_xmss.pk)

            walletd._public_stub.PushTransaction = Mock(
                return_value=qrl_pb2.PushTransactionResp(error_code=qrl_pb2.PushTransactionResp.SUBMITTED))

            walletd._push_transaction(tx, alice_xmss)

            walletd._public_stub.PushTransaction = Mock(
                return_value=qrl_pb2.PushTransactionResp(error_code=qrl_pb2.PushTransactionResp.UNKNOWN))

            with self.assertRaises(Exception):
                walletd._push_transaction(tx, alice_xmss)

    def test_relay_transfer_txn(self):
        with set_qrl_dir("wallet_ver1"):
            walletd = WalletD()
            qaddress = walletd.add_new_address(height=4)
            alice_xmss = get_alice_xmss(4)
            bob_xmss = get_bob_xmss(4)
            qaddresses_to = [alice_xmss.qaddress, bob_xmss.qaddress]
            amounts = [1000000000, 1000000000]
            walletd._public_stub.PushTransaction = Mock(
                return_value=qrl_pb2.PushTransactionResp(error_code=qrl_pb2.PushTransactionResp.SUBMITTED))
            tx = walletd.relay_transfer_txn(qaddresses_to=qaddresses_to,
                                            amounts=amounts,
                                            fee=100000000,
                                            master_qaddress=None,
                                            signer_address=qaddress,
                                            ots_index=0)
            self.assertIsNotNone(tx)

    def test_relay_transfer_txn2(self):
        with set_qrl_dir("wallet_ver1"):
            walletd = WalletD()
            qaddress = walletd.add_new_address(height=4)
            walletd.encrypt_wallet(self.passphrase)
            walletd.unlock_wallet(self.passphrase)
            alice_xmss = get_alice_xmss(4)
            bob_xmss = get_bob_xmss(4)
            qaddresses_to = [alice_xmss.qaddress, bob_xmss.qaddress]
            amounts = [1000000000, 1000000000]
            walletd._public_stub.PushTransaction = Mock(
                return_value=qrl_pb2.PushTransactionResp(error_code=qrl_pb2.PushTransactionResp.SUBMITTED))
            tx = walletd.relay_transfer_txn(qaddresses_to=qaddresses_to,
                                            amounts=amounts,
                                            fee=100000000,
                                            master_qaddress=None,
                                            signer_address=qaddress,
                                            ots_index=0)
            self.assertIsNotNone(tx)

            walletd.lock_wallet()
            with self.assertRaises(ValueError):
                walletd.relay_transfer_txn(qaddresses_to=qaddresses_to,
                                           amounts=amounts,
                                           fee=100000000,
                                           master_qaddress=None,
                                           signer_address=qaddress,
                                           ots_index=0)

    def test_relay_message_txn(self):
        with set_qrl_dir("wallet_ver1"):
            walletd = WalletD()
            qaddress = walletd.add_new_address(height=4)
            walletd._public_stub.PushTransaction = Mock(
                return_value=qrl_pb2.PushTransactionResp(error_code=qrl_pb2.PushTransactionResp.SUBMITTED))
            tx = walletd.relay_message_txn(message=b'Hello QRL!',
                                           fee=100000000,
                                           master_qaddress=None,
                                           signer_address=qaddress,
                                           ots_index=0)
            self.assertIsNotNone(tx)

    def test_relay_message_txn2(self):
        with set_qrl_dir("wallet_ver1"):
            walletd = WalletD()
            qaddress = walletd.add_new_address(height=4)
            walletd.encrypt_wallet(self.passphrase)
            walletd.unlock_wallet(self.passphrase)
            walletd._public_stub.PushTransaction = Mock(
                return_value=qrl_pb2.PushTransactionResp(error_code=qrl_pb2.PushTransactionResp.SUBMITTED))
            tx = walletd.relay_message_txn(message=b'Hello QRL!',
                                           fee=100000000,
                                           master_qaddress=None,
                                           signer_address=qaddress,
                                           ots_index=0)
            self.assertIsNotNone(tx)

            walletd.lock_wallet()
            with self.assertRaises(ValueError):
                walletd.relay_message_txn(message=b'Hello QRL!',
                                          fee=100000000,
                                          master_qaddress=None,
                                          signer_address=qaddress,
                                          ots_index=0)

    def test_relay_token_txn(self):
        with set_qrl_dir("wallet_ver1"):
            walletd = WalletD()
            qaddress = walletd.add_new_address(height=4)
            alice_xmss = get_alice_xmss(4)
            bob_xmss = get_bob_xmss(4)
            qaddresses = [alice_xmss.qaddress, bob_xmss.qaddress]
            amounts = [1000000000, 1000000000]
            walletd._public_stub.PushTransaction = Mock(
                return_value=qrl_pb2.PushTransactionResp(error_code=qrl_pb2.PushTransactionResp.SUBMITTED))
            tx = walletd.relay_token_txn(symbol=b'QRL',
                                         name=b'Quantum Resistant Ledger',
                                         owner_qaddress=alice_xmss.qaddress,
                                         decimals=5,
                                         qaddresses=qaddresses,
                                         amounts=amounts,
                                         fee=100000000,
                                         master_qaddress=None,
                                         signer_address=qaddress,
                                         ots_index=0)
            self.assertIsNotNone(tx)

    def test_relay_token_txn2(self):
        with set_qrl_dir("wallet_ver1"):
            walletd = WalletD()
            qaddress = walletd.add_new_address(height=4)
            walletd.encrypt_wallet(self.passphrase)
            walletd.unlock_wallet(self.passphrase)

            alice_xmss = get_alice_xmss(4)
            bob_xmss = get_bob_xmss(4)
            qaddresses = [alice_xmss.qaddress, bob_xmss.qaddress]
            amounts = [1000000000, 1000000000]
            walletd._public_stub.PushTransaction = Mock(
                return_value=qrl_pb2.PushTransactionResp(error_code=qrl_pb2.PushTransactionResp.SUBMITTED))
            tx = walletd.relay_token_txn(symbol=b'QRL',
                                         name=b'Quantum Resistant Ledger',
                                         owner_qaddress=alice_xmss.qaddress,
                                         decimals=5,
                                         qaddresses=qaddresses,
                                         amounts=amounts,
                                         fee=100000000,
                                         master_qaddress=None,
                                         signer_address=qaddress,
                                         ots_index=0)
            self.assertIsNotNone(tx)

            walletd.lock_wallet()
            with self.assertRaises(ValueError):
                walletd.relay_token_txn(symbol=b'QRL',
                                        name=b'Quantum Resistant Ledger',
                                        owner_qaddress=alice_xmss.qaddress,
                                        decimals=5,
                                        qaddresses=qaddresses,
                                        amounts=amounts,
                                        fee=100000000,
                                        master_qaddress=None,
                                        signer_address=qaddress,
                                        ots_index=0)

    def test_relay_transfer_token_txn(self):
        with set_qrl_dir("wallet_ver1"):
            walletd = WalletD()
            qaddress = walletd.add_new_address(height=4)
            walletd.encrypt_wallet(self.passphrase)
            walletd.unlock_wallet(self.passphrase)

            alice_xmss = get_alice_xmss(4)
            bob_xmss = get_bob_xmss(4)
            qaddresses_to = [alice_xmss.qaddress, bob_xmss.qaddress]
            amounts = [1000000000, 1000000000]
            walletd._public_stub.PushTransaction = Mock(
                return_value=qrl_pb2.PushTransactionResp(error_code=qrl_pb2.PushTransactionResp.SUBMITTED))
            tx = walletd.relay_transfer_token_txn(qaddresses_to=qaddresses_to,
                                                  amounts=amounts,
                                                  token_txhash='',
                                                  fee=100000000,
                                                  master_qaddress=None,
                                                  signer_address=qaddress,
                                                  ots_index=0)
            self.assertIsNotNone(tx)

            walletd.lock_wallet()
            with self.assertRaises(ValueError):
                walletd.relay_transfer_token_txn(qaddresses_to=qaddresses_to,
                                                 amounts=amounts,
                                                 token_txhash='',
                                                 fee=100000000,
                                                 master_qaddress=None,
                                                 signer_address=qaddress,
                                                 ots_index=0)

    def test_relay_slave_txn(self):
        with set_qrl_dir("wallet_ver1"):
            walletd = WalletD()
            qaddress = walletd.add_new_address(height=4)
            walletd.encrypt_wallet(self.passphrase)
            walletd.unlock_wallet(self.passphrase)

            alice_xmss = get_alice_xmss(4)
            slave_pks = [alice_xmss.pk]
            access_types = [0]
            walletd._public_stub.PushTransaction = Mock(
                return_value=qrl_pb2.PushTransactionResp(error_code=qrl_pb2.PushTransactionResp.SUBMITTED))
            tx = walletd.relay_slave_txn(slave_pks=slave_pks,
                                         access_types=access_types,
                                         fee=100000000,
                                         master_qaddress=None,
                                         signer_address=qaddress,
                                         ots_index=0)
            self.assertIsNotNone(tx)

            walletd.lock_wallet()
            with self.assertRaises(ValueError):
                walletd.relay_slave_txn(slave_pks=slave_pks,
                                        access_types=access_types,
                                        fee=100000000,
                                        master_qaddress=None,
                                        signer_address=qaddress,
                                        ots_index=0)

    def test_encrypt_wallet(self):
        with set_qrl_dir("wallet_ver1"):
            walletd = WalletD()
            with self.assertRaises(ValueError):
                walletd.encrypt_wallet(passphrase=self.passphrase)

            walletd.add_new_address()
            walletd.encrypt_wallet(passphrase=self.passphrase)

            with self.assertRaises(Exception):
                walletd.encrypt_wallet(passphrase=self.passphrase)

    def test_lock_wallet(self):
        with set_qrl_dir("wallet_ver1"):
            walletd = WalletD()
            walletd.add_new_address()
            walletd.encrypt_wallet(passphrase=self.passphrase)
            walletd.lock_wallet()
            with self.assertRaises(ValueError):
                walletd.add_new_address()

    def test_unlock_wallet(self):
        with set_qrl_dir("wallet_ver1"):
            walletd = WalletD()
            walletd.add_new_address()
            walletd.encrypt_wallet(passphrase=self.passphrase)
            walletd.lock_wallet()
            with self.assertRaises(ValueError):
                walletd.add_new_address()
            with self.assertRaises(WalletDecryptionError):
                walletd.unlock_wallet(passphrase='pass123')
            walletd.unlock_wallet(passphrase=self.passphrase)
            walletd.add_new_address()
            self.assertEqual(len(walletd.list_address()), 2)

    def test_change_passphrase(self):
        with set_qrl_dir("wallet_ver1"):
            walletd = WalletD()
            qaddress = walletd.add_new_address()
            walletd.encrypt_wallet(passphrase=self.passphrase)
            walletd.lock_wallet()

            passphrase2 = 'pass000'

            with self.assertRaises(ValueError):
                walletd.change_passphrase(old_passphrase='pass123', new_passphrase='pass234')
            walletd.change_passphrase(old_passphrase=self.passphrase, new_passphrase=passphrase2)

            with self.assertRaises(WalletDecryptionError):
                walletd.unlock_wallet(passphrase=self.passphrase)

            walletd.unlock_wallet(passphrase=passphrase2)
            qaddresses = walletd.list_address()
            self.assertEqual(len(qaddresses), 1)
            self.assertEqual(qaddresses[0], qaddress)
