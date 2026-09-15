package onpc_parent;
use strict;
use warnings;
use testapi ();
use onpc_gdm ();
use onpc_password ();
use onpc_pointer ();

# Installed account pixels and negative recipient qualification are shared by
# Parent customers. An observation tag alone never authorizes password input.
sub login {
    my ($journey, $functional) = @_;
    onpc_gdm::reattach_after_setup();
    $journey->seen('installed-greeter');
    die 'parent:list-is-password' if testapi::check_screen('onpc-gdm-parent-masked-password', 0);
    onpc_pointer::click('onpc-gdm-other-parent-installed-input-account', 30);
    testapi::wait_still_screen(1, 10);
    die 'parent:other-prompt-is-list' if testapi::check_screen('onpc-gdm-parent-installed-account', 0);
    die 'parent:wrong-password-recipient' if testapi::check_screen('onpc-gdm-parent-masked-password', 0);
    testapi::send_key('esc');
    onpc_pointer::click('onpc-gdm-parent-installed-input-account', 30);
    die 'parent:list-still-visible' if testapi::check_screen('onpc-gdm-parent-installed-account', 0);
    testapi::assert_screen('onpc-gdm-parent-masked-password', 30);
    $journey->seen('recipient-qualified');
    onpc_password::enter_password('parent', 'gdm');
    testapi::send_key('ret');
    testapi::assert_screen('onpc-parent-desktop', 90) unless $functional;
    $journey->seen('desktop');
}

sub launch_from_app_grid {
    my ($journey) = @_;
    open_app_grid($journey);
    testapi::type_string('Oh No! Parent Control');
    testapi::wait_still_screen(1, 10);
    testapi::send_key('ret');
}

sub open_app_grid {
    my ($journey) = @_;
    testapi::send_key('super-a');
    testapi::assert_screen('onpc-parent-app-grid', 30);
    $journey->seen('app-grid');
}

sub login_standard {
    my ($journey) = @_;
    onpc_gdm::reattach_after_setup();
    $journey->seen('installed-greeter');
    die 'parent-access:list-is-password'
        if testapi::check_screen('onpc-gdm-other-child-masked-password', 0);
    onpc_gdm::inspect_installed_standard(sub {
        die 'parent-access:parent-matches-standard'
            if testapi::check_screen('onpc-gdm-other-child-masked-password', 0);
    });
    die 'parent-access:list-still-visible'
        if testapi::check_screen('onpc-gdm-parent-installed-account', 0);
    die 'parent-access:wrong-password-recipient'
        if testapi::check_screen('onpc-gdm-parent-masked-password', 0);
    testapi::assert_screen('onpc-gdm-other-child-masked-password', 30);
    $journey->seen('recipient-qualified');
    onpc_password::enter_password('other-child', 'gdm');
    testapi::send_key('ret');
    testapi::assert_screen('onpc-parent-desktop', 90);
    $journey->seen('desktop');
}

sub select_existing_child {
    my ($journey) = @_;
    onpc_pointer::click('onpc-parent-child-picker', 90);
    # Choose the reviewed existing fixture through the ordinary dropdown.
    onpc_pointer::click('onpc-parent-child-choice', 30);
    $journey->observe('onpc-parent-child-selected', 30);
    $journey->seen('parent-selected');
}

1;
