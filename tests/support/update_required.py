"""Engineering reboot transport double; never reaches the host system bus."""

from common.oh_no_parent_control_ui import errors


def install_reboot_stub(record):
    def reboot(done):
        record('reboot-requested')
        done(PermissionError('synthetic reboot refusal'))

    errors.request_reboot = reboot
