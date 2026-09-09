"""Fresh valid input documents shared by broker and configuration tests."""

def valid_config():
    return {
        "version": 3,
        "kiosk_uid": 991,
        "minimum_request_interval_seconds": 5,
    }
