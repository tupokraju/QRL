# coding=utf-8
# Distributed under the MIT software license, see the accompanying
# file LICENSE or http://www.opensource.org/licenses/mit-license.php.
from qrl.generated import qrlwallet_pb2
from qrl.generated.qrlwallet_pb2_grpc import WalletAPIServicer
from qrl.services.grpcHelper import GrpcExceptionWrapper


class WalletAPIService(WalletAPIServicer):
    MAX_REQUEST_QUANTITY = 100

    # TODO: Separate the Service from the node model
    def __init__(self, walletd):
        self._walletd = walletd

    @GrpcExceptionWrapper(qrlwallet_pb2.AddNewAddressResp)
    def AddNewAddress(self, request: qrlwallet_pb2.AddNewAddressReq, context) -> qrlwallet_pb2.AddNewAddressResp:
        resp = qrlwallet_pb2.AddNewAddressResp()
        try:
            resp.address = self._walletd.add_new_address(request.height, request.hash_function.lower())
        except Exception as e:
            resp.status = 1
            resp.error_message = str(e)

        return resp

    @GrpcExceptionWrapper(qrlwallet_pb2.AddAddressFromSeedResp)
    def AddAddressFromSeed(self, request: qrlwallet_pb2.AddAddressFromSeedReq, context) -> qrlwallet_pb2.AddAddressFromSeedResp:
        resp = qrlwallet_pb2.AddAddressFromSeedResp()
        try:
            resp.address = self._walletd.add_address_from_seed(seed=request.seed)
        except Exception as e:
            resp.status = 1
            resp.error_message = str(e)

        return resp

    @GrpcExceptionWrapper(qrlwallet_pb2.ListAddressesResp)
    def ListAddresses(self, request: qrlwallet_pb2.ListAddressesReq, context) -> qrlwallet_pb2.ListAddressesResp:
        resp = qrlwallet_pb2.ListAddressesResp()
        try:
            resp.addresses.extend(self._walletd.list_address())
        except Exception as e:
            resp.status = 1
            resp.error_message = str(e)

        return resp

    @GrpcExceptionWrapper(qrlwallet_pb2.RemoveAddressResp)
    def RemoveAddress(self, request: qrlwallet_pb2.RemoveAddressReq, context) -> qrlwallet_pb2.RemoveAddressResp:
        resp = qrlwallet_pb2.RemoveAddressResp()
        try:
            if not self._walletd.remove_address(request.address):
                resp.status = 1
                resp.error_message = "No such address found"
        except Exception as e:
            resp.status = 1
            resp.error_message = str(e)

        return resp

    @GrpcExceptionWrapper(qrlwallet_pb2.GetRecoverySeedsResp)
    def GetRecoverySeeds(self, request: qrlwallet_pb2.GetRecoverySeedsReq, context) -> qrlwallet_pb2.GetRecoverySeedsResp:
        resp = qrlwallet_pb2.GetRecoverySeedsResp()
        try:
            resp.hexseed, resp.mnemonic = self._walletd.get_recovery_seeds(request.address)
        except Exception as e:
            resp.status = 1
            resp.error_message = str(e)

        return resp

    @GrpcExceptionWrapper(qrlwallet_pb2.GetWalletInfoResp)
    def GetWalletInfo(self, request: qrlwallet_pb2.GetWalletInfoReq, context) -> qrlwallet_pb2.GetWalletInfoResp:
        resp = qrlwallet_pb2.GetWalletInfoResp()
        try:
            resp.version, resp.address_count, resp.is_encrypted = self._walletd.get_wallet_info()
        except Exception as e:
            resp.status = 1
            resp.error_message = str(e)

        return resp

    @GrpcExceptionWrapper(qrlwallet_pb2.RelayTxnResp)
    def RelayTransferTxn(self, request: qrlwallet_pb2.RelayTransferTxnReq, context) -> qrlwallet_pb2.RelayTxnResp:
        resp = qrlwallet_pb2.RelayTxnResp()
        try:
            resp.tx.MergeFrom(self._walletd.relay_transfer_txn(request.addresses_to,
                                                               request.amounts,
                                                               request.fee,
                                                               request.master_address,
                                                               request.signer_address,
                                                               request.ots_index))
        except Exception as e:
            resp.status = 1
            resp.error_message = str(e)

        return resp

    @GrpcExceptionWrapper(qrlwallet_pb2.RelayTxnResp)
    def RelayMessageTxn(self, request: qrlwallet_pb2.RelayMessageTxnReq, context) -> qrlwallet_pb2.RelayTxnResp:
        resp = qrlwallet_pb2.RelayTxnResp()
        try:
            resp.tx.MergeFrom(self._walletd.relay_message_txn(request.message,
                                                              request.fee,
                                                              request.master_address,
                                                              request.signer_address,
                                                              request.ots_index))
        except Exception as e:
            resp.status = 1
            resp.error_message = str(e)

        return resp

    @GrpcExceptionWrapper(qrlwallet_pb2.RelayTxnResp)
    def RelayTokenTxn(self, request: qrlwallet_pb2.RelayTokenTxnReq, context) -> qrlwallet_pb2.RelayTxnResp:
        resp = qrlwallet_pb2.RelayTxnResp()
        try:
            resp.tx.MergeFrom(self._walletd.relay_token_txn(request.symbol,
                                                            request.name,
                                                            request.owner,
                                                            request.decimals,
                                                            request.addresses,
                                                            request.amounts,
                                                            request.fee,
                                                            request.master_address,
                                                            request.signer_address,
                                                            request.ots_index))
        except Exception as e:
            resp.status = 1
            resp.error_message = str(e)

        return resp

    @GrpcExceptionWrapper(qrlwallet_pb2.RelayTxnResp)
    def RelayTransferTokenTxn(self, request: qrlwallet_pb2.RelayTransferTokenTxnReq, context) -> qrlwallet_pb2.RelayTxnResp:
        resp = qrlwallet_pb2.RelayTxnResp()
        try:
            resp.tx.MergeFrom(self._walletd.relay_transfer_token_txn(request.addresses_to,
                                                                     request.amounts,
                                                                     request.token_txhash,
                                                                     request.fee,
                                                                     request.master_address,
                                                                     request.signer_address,
                                                                     request.ots_index))
        except Exception as e:
            resp.status = 1
            resp.error_message = str(e)

        return resp

    @GrpcExceptionWrapper(qrlwallet_pb2.RelayTxnResp)
    def RelaySlaveTxn(self, request: qrlwallet_pb2.RelaySlaveTxnReq, context) -> qrlwallet_pb2.RelayTxnResp:
        resp = qrlwallet_pb2.RelayTxnResp()
        try:
            resp.tx.MergeFrom(self._walletd.relay_slave_txn(request.slave_pks,
                                                            request.access_types,
                                                            request.fee,
                                                            request.master_address,
                                                            request.signer_address,
                                                            request.ots_index))
        except Exception as e:
            resp.status = 1
            resp.error_message = str(e)

        return resp

    @GrpcExceptionWrapper(qrlwallet_pb2.EncryptWalletResp)
    def EncryptWallet(self, request: qrlwallet_pb2.EncryptWalletReq, context) -> qrlwallet_pb2.EncryptWalletResp:
        resp = qrlwallet_pb2.EncryptWalletResp()
        try:
            self._walletd.encrypt_wallet(request.passphrase)
        except Exception as e:
            resp.status = 1
            resp.error_message = str(e)

        return resp

    @GrpcExceptionWrapper(qrlwallet_pb2.LockWalletResp)
    def LockWallet(self, request: qrlwallet_pb2.LockWalletReq, context) -> qrlwallet_pb2.LockWalletResp:
        resp = qrlwallet_pb2.LockWalletResp()
        try:
            self._walletd.lock_wallet()
        except Exception as e:
            resp.status = 1
            resp.error_message = str(e)

        return resp

    @GrpcExceptionWrapper(qrlwallet_pb2.UnlockWalletResp)
    def UnlockWallet(self, request: qrlwallet_pb2.UnlockWalletReq, context) -> qrlwallet_pb2.UnlockWalletResp:
        resp = qrlwallet_pb2.UnlockWalletResp()
        try:
            self._walletd.unlock_wallet(request.passphrase)
        except Exception as e:
            resp.status = 1
            resp.error_message = str(e)

        return resp

    @GrpcExceptionWrapper(qrlwallet_pb2.ChangePassphraseResp)
    def ChangePassphrase(self, request: qrlwallet_pb2.ChangePassphraseReq, context) -> qrlwallet_pb2.ChangePassphraseResp:
        resp = qrlwallet_pb2.ChangePassphraseResp()
        try:
            self._walletd.change_passphrase(request.oldPassphrase, request.newPassphrase)
        except Exception as e:
            resp.status = 1
            resp.error_message = str(e)

        return resp

    @GrpcExceptionWrapper(qrlwallet_pb2.TransactionResp)
    def GetTransaction(self, request: qrlwallet_pb2.TransactionReq, context) -> qrlwallet_pb2.TransactionResp:
        resp = qrlwallet_pb2.TransactionResp()
        try:
            tx, confirmations = self._walletd.get_transaction(request.hash)
            resp.tx.MergeFrom(tx)
            resp.confirmations = confirmations
        except Exception as e:
            resp.status = 1
            resp.error_message = str(e)

        return resp

    @GrpcExceptionWrapper(qrlwallet_pb2.BalanceResp)
    def GetBalance(self, request: qrlwallet_pb2.BalanceReq, context) -> qrlwallet_pb2.BalanceResp:
        resp = qrlwallet_pb2.BalanceResp()
        try:
            resp.balance = self._walletd.get_balance(request.address)
        except Exception as e:
            resp.status = 1
            resp.error_message = str(e)

        return resp

    @GrpcExceptionWrapper(qrlwallet_pb2.OTSResp)
    def GetOTS(self, request: qrlwallet_pb2.OTSReq, context) -> qrlwallet_pb2.OTSResp:
        resp = qrlwallet_pb2.OTSResp()
        try:
            ots_bitfield, next_unused_ots_index = self._walletd.get_ots(request.address)
            resp.ots_bitfield.extend(ots_bitfield)
            resp.next_unused_ots_index = next_unused_ots_index
        except Exception as e:
            resp.status = 1
            resp.error_message = str(e)

        return resp

    @GrpcExceptionWrapper(qrlwallet_pb2.HeightResp)
    def GetHeight(self, request: qrlwallet_pb2.HeightReq, context) -> qrlwallet_pb2.HeightResp:
        resp = qrlwallet_pb2.HeightResp()
        try:
            resp.height = self._walletd.get_height()
        except Exception as e:
            resp.status = 1
            resp.error_message = str(e)

        return resp

    @GrpcExceptionWrapper(qrlwallet_pb2.BlockResp)
    def GetBlock(self, request: qrlwallet_pb2.BlockReq, context) -> qrlwallet_pb2.BlockResp:
        resp = qrlwallet_pb2.BlockResp()
        try:
            resp.block.MergeFrom(self._walletd.get_block(request.hash))
        except Exception as e:
            resp.status = 1
            resp.error_message = str(e)

        return resp

    @GrpcExceptionWrapper(qrlwallet_pb2.BlockResp)
    def GetBlockByNumber(self, request: qrlwallet_pb2.BlockByNumberReq, context) -> qrlwallet_pb2.BlockResp:
        resp = qrlwallet_pb2.BlockResp()
        try:
            resp.block.MergeFrom(self._walletd.get_block_by_number(request.block_number))
        except Exception as e:
            resp.status = 1
            resp.error_message = str(e)

        return resp
