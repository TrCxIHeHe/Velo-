import 'package:intl/intl.dart';

/// Formats a server-provided amount in the server-provided currency.
/// The client never computes or converts money, it only presents it.
String formatMoney(num amount, String currencyCode) {
  final code = currencyCode.toUpperCase();
  final format = code == 'INR'
      ? NumberFormat.currency(locale: 'en_IN', symbol: '₹', decimalDigits: 2)
      : NumberFormat.currency(locale: 'en_IN', name: code, decimalDigits: 2);
  return format.format(amount);
}
