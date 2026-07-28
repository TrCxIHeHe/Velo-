import 'package:flutter_test/flutter_test.dart';
import 'package:scooter/features/wallet/domain/models/wallet.dart';
import 'package:scooter/features/wallet/domain/models/wallet_transaction.dart';

void main() {
  group('Wallet.fromJson', () {
    test('maps backend WalletResponse fields', () {
      final wallet = Wallet.fromJson({
        'id': 'w1',
        'user_id': 'u1',
        'balance': 248.5,
        'currency': 'INR',
        'updated_at': '2026-07-24T09:12:00Z',
      });
      expect(wallet.balance, 248.5);
      expect(wallet.currency, 'INR');
    });
  });

  group('WalletTransaction.fromJson', () {
    test('maps CREDIT/TOPUP correctly', () {
      final tx = WalletTransaction.fromJson({
        'id': 't1',
        'type': 'CREDIT',
        'source': 'TOPUP',
        'amount': 500.0,
        'balance_after': 748.5,
        'reference_id': 'razorpay:pay_123',
        'note': null,
        'created_at': '2026-07-24T09:12:00Z',
      });
      expect(tx.type, WalletTransactionType.credit);
      expect(tx.source, WalletTransactionSource.topup);
      expect(tx.amount, 500.0);
    });

    test('maps DEBIT/RIDE_FARE correctly', () {
      final tx = WalletTransaction.fromJson({
        'id': 't2',
        'type': 'DEBIT',
        'source': 'RIDE_FARE',
        'amount': 42.0,
        'balance_after': 706.5,
        'reference_id': null,
        'note': null,
        'created_at': '2026-07-24T18:32:00Z',
      });
      expect(tx.type, WalletTransactionType.debit);
      expect(tx.source, WalletTransactionSource.rideFare);
    });
  });

  group('TransactionPage.fromJson', () {
    test('maps items and total', () {
      final page = TransactionPage.fromJson({
        'items': [
          {
            'id': 't1',
            'type': 'CREDIT',
            'source': 'TOPUP',
            'amount': 500.0,
            'balance_after': 500.0,
            'reference_id': null,
            'note': null,
            'created_at': '2026-07-24T09:12:00Z',
          },
        ],
        'total': 1,
      });
      expect(page.items.length, 1);
      expect(page.total, 1);
    });
  });
}
