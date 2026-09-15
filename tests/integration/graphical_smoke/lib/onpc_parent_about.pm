package onpc_parent_about;
use strict;
use warnings;
use testapi ();
use onpc_journey ();
use onpc_parent ();

sub run {
    my ($exchange, $review) = @_;
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'parent', review => $review);
    # Password recipient checks stay in the qualified input helper. From the
    # desktop onward the controller operates and observes public AT-SPI widgets.
    # No app pixels, geometry, fonts, colors or screenshot similarity can fail it.
    onpc_parent::login($journey, 1);
    testapi::send_key('super-a');
    testapi::type_string('Oh No! Parent Control');
    $journey->seen('app-grid');
    testapi::send_key('ret');
    my $choice = $journey->seen('child-picker-opened');
    $journey->navigate_choice($choice);
    $journey->seen('child-choice-highlighted');
    testapi::send_key('ret');
    $journey->seen('parent-selected');
    $journey->seen('about');
    $journey->seen('license');
    testapi::send_key('alt-f4');
    testapi::send_key('tab');
    # GtkScrolledWindow binds End to vertical end; Ctrl-End is horizontal.
    testapi::send_key('end');
    $journey->seen('about-returned');
    testapi::send_key('alt-f4');
    $journey->seen('parent-returned');
    $journey->finish();
}

1;
