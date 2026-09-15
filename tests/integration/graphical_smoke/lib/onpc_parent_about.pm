package onpc_parent_about;
use strict;
use warnings;
use testapi ();
use onpc_journey ();
use onpc_parent ();
use onpc_pointer ();

sub run {
    my ($exchange, $review) = @_;
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'parent', review => $review);
    onpc_parent::login($journey);
    onpc_parent::launch_from_app_grid($journey);
    onpc_parent::select_existing_child($journey);
    onpc_pointer::click('onpc-parent-menu', 30);
    onpc_pointer::click('onpc-parent-about-item', 30);
    $journey->observe('onpc-parent-about', 30);
    $journey->seen('about');
    onpc_pointer::click('onpc-parent-license-link', 30);
    $journey->observe('onpc-parent-license', 60);
    $journey->seen('license');
    testapi::send_key('alt-f4');
    testapi::assert_screen('onpc-parent-about', 30);
    testapi::send_key('tab');
    # GtkScrolledWindow binds End to vertical end; Ctrl-End is horizontal.
    testapi::send_key('end');
    $journey->observe('onpc-parent-about-legal', 30);
    $journey->seen('about-returned');
    testapi::send_key('alt-f4');
    $journey->observe('onpc-parent-child-selected', 30);
    $journey->seen('parent-returned');
    $journey->finish();
}

1;
