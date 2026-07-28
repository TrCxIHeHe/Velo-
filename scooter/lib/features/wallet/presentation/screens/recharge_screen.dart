import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:razorpay_flutter/razorpay_flutter.dart';
import 'package:scooter/core/errors/app_exception.dart';
import 'package:scooter/core/widgets/app_button.dart';
import 'package:scooter/core/widgets/app_snackbar.dart';
import 'package:scooter/core/widgets/app_text_field.dart';
import 'package:scooter/features/wallet/presentation/providers/wallet_providers.dart';

const List<int> _quickAmounts = [100, 200, 500, 1000];

enum _RechargeStep { idle, creatingOrder, awaitingPayment, confirming, success }

class RechargeScreen extends ConsumerStatefulWidget {
  const RechargeScreen({super.key});

  @override
  ConsumerState<RechargeScreen> createState() => _RechargeScreenState();
}

class _RechargeScreenState extends ConsumerState<RechargeScreen> {
  final _amountCtrl = TextEditingController();
  final _razorpay = Razorpay();
  int? _selectedQuickAmount;
  _RechargeStep _step = _RechargeStep.idle;
  String? _error;

  @override
  void initState() {
    super.initState();
    _razorpay.on(Razorpay.EVENT_PAYMENT_SUCCESS, _onPaymentSuccess);
    _razorpay.on(Razorpay.EVENT_PAYMENT_ERROR, _onPaymentError);
    _razorpay.on(Razorpay.EVENT_EXTERNAL_WALLET, _onExternalWallet);
  }

  @override
  void dispose() {
    _razorpay.clear();
    _amountCtrl.dispose();
    super.dispose();
  }

  double? get _amount {
    final text = _amountCtrl.text.trim();
    if (text.isEmpty) return null;
    return double.tryParse(text);
  }

  void _selectQuickAmount(int amount) {
    setState(() {
      _selectedQuickAmount = amount;
      _amountCtrl.text = amount.toString();
      _error = null;
    });
  }

  Future<void> _startRecharge() async {
    final amount = _amount;
    if (amount == null || amount <= 0) {
      setState(() => _error = 'Enter a valid amount.');
      return;
    }

    setState(() {
      _step = _RechargeStep.creatingOrder;
      _error = null;
    });

    try {
      final order = await ref.read(walletRepositoryProvider).createRazorpayOrder(amount);
      if (!mounted) return;
      setState(() => _step = _RechargeStep.awaitingPayment);

      _razorpay.open({
        'key': order.keyId,
        'amount': (order.amount * 100).round(),
        'currency': order.currency,
        'order_id': order.orderId,
        'name': 'Velo',
        'description': 'Wallet recharge',
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _step = _RechargeStep.idle);
      if (e.code == 'PAYMENT_GATEWAY_NOT_CONFIGURED') {
        _showNotConfiguredDialog();
      } else {
        setState(() => _error = e.message);
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _step = _RechargeStep.idle;
        _error = e.toString();
      });
    }
  }

  Future<void> _onPaymentSuccess(PaymentSuccessResponse response) async {
    if (!mounted) return;
    setState(() => _step = _RechargeStep.confirming);

    // The webhook credits the wallet asynchronously — poll briefly for the
    // updated balance rather than assuming it's already reflected.
    for (var attempt = 0; attempt < 5; attempt++) {
      await Future.delayed(const Duration(seconds: 1));
      try {
        await ref.read(walletNotifierProvider.notifier).refresh();
        break;
      } catch (_) {
        // keep retrying until attempts are exhausted
      }
    }

    if (!mounted) return;
    setState(() => _step = _RechargeStep.success);
  }

  void _onPaymentError(PaymentFailureResponse response) {
    if (!mounted) return;
    setState(() {
      _step = _RechargeStep.idle;
      _error = response.message ?? 'Payment failed. Please try again.';
    });
  }

  void _onExternalWallet(ExternalWalletResponse response) {
    if (!mounted) return;
    showAppSnackbar(context, 'Continue in ${response.walletName ?? 'your wallet app'}.');
  }

  void _showNotConfiguredDialog() {
    showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Payments not live yet'),
        content: const Text(
          'Online payments are not configured on this deployment yet. '
          'Please check back later, or contact support to top up your wallet.',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('OK')),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (_step == _RechargeStep.success) {
      return _SuccessView(amount: _amount ?? 0);
    }

    final busy = _step == _RechargeStep.creatingOrder ||
        _step == _RechargeStep.awaitingPayment ||
        _step == _RechargeStep.confirming;

    return Scaffold(
      appBar: AppBar(title: const Text('Add Money')),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Choose an amount', style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 16),
              Wrap(
                spacing: 12,
                runSpacing: 12,
                children: _quickAmounts
                    .map((a) => ChoiceChip(
                          label: Text('₹$a'),
                          selected: _selectedQuickAmount == a,
                          onSelected: busy ? null : (_) => _selectQuickAmount(a),
                        ))
                    .toList(),
              ),
              const SizedBox(height: 24),
              AppTextField(
                label: 'Or enter a custom amount',
                controller: _amountCtrl,
                hintText: '₹0.00',
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                errorText: _error,
                onChanged: (_) => setState(() => _selectedQuickAmount = null),
              ),
              const Spacer(),
              PrimaryButton(
                label: _step == _RechargeStep.confirming ? 'Confirming…' : 'Add Money',
                loading: busy,
                onPressed: busy ? null : _startRecharge,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SuccessView extends StatelessWidget {
  const _SuccessView({required this.amount});
  final double amount;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.check_circle, size: 64, color: Theme.of(context).colorScheme.primary),
                const SizedBox(height: 16),
                Text('Money added', style: Theme.of(context).textTheme.headlineSmall),
                const SizedBox(height: 8),
                Text(
                  'Your wallet has been recharged.',
                  style: Theme.of(context).textTheme.bodyLarge,
                ),
                const SizedBox(height: 32),
                PrimaryButton(
                  label: 'Done',
                  onPressed: () => Navigator.of(context).pop(),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
