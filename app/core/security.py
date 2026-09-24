"""User-facing security notice copy shared by the desktop interface."""

SECURITY_NOTICE_PREFERENCE_KEY = "transfercove.security_notice_acknowledged.v1"
SECURITY_NOTICE_TITLE = "Security notice"
SECURITY_NOTICE_SUMMARY = (
    "Transfers use plain HTTP without encryption or authentication. "
    "Use TransferCove only on a trusted local network."
)
SECURITY_NOTICE_DETAILS = (
    "TransferCove does not encrypt network traffic and does not provide "
    "authentication. Files are sent over plain HTTP. Use it only inside a trusted, "
    "verified local network. Do not expose the server to the public internet or an "
    "untrusted Wi-Fi network."
)
