# dock_vision package — temporary MVP layer.
# Decodes a QR image sent by an ESP32-CAM into a ride_token string,
# then hands off to the existing, unmodified RideService.confirm_ride().
# Delete this entire package once dock hardware moves to a dedicated
# barcode-scanner module that sends a decoded string directly.