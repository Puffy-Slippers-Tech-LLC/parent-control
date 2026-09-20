package onpc_parent_about;
use strict;
use warnings;
use onpc_progress ();
use testapi ();
use onpc_journey ();
use onpc_parent ();
use onpc_gdm ();

# ABOUT01/02: the registered adapter composes public menu/link actions and reads.
sub open_about {
    onpc_progress::operation('Opening About');
    my ($journey, $selected) = @_;
    $journey->consume_observation('parent-selected', $selected);
    return $journey->seen('about');
}

sub open_license {
    onpc_progress::operation('Opening the license');
    my ($journey, $about) = @_;
    $journey->consume_observation('about', $about);
    return $journey->seen('license');
}

# UI18: consume fresh active-window proof, close once, observe the destination.
sub close_window {
    onpc_progress::operation('Closing the current window');
    my ($journey, $window, $proof) = @_;
    my %stages = (license => ['license', 'license-closed'],
                  about => ['about-returned', 'parent-returned']);
    die 'about:close-binding' unless @_ == 3 && exists($stages{$window});
    my ($before, $after) = @{$stages{$window}};
    $journey->consume_observation($before, $proof);
    testapi::send_key('alt-f4');
    return $journey->seen($after);
}

# ABOUT04: the controller reveals and reads the ID-addressed footer.
sub read_footer {
    onpc_progress::operation('Reading the About footer');
    my ($journey, $returned, $route) = @_;
    die 'about:footer-binding' unless @_ == 3 && $route eq 'semantic-reveal';
    $journey->consume_observation('license-closed', $returned);
    return $journey->seen('about-returned');
}

# ABOUT03: recipe-owned settings comparison runs before the terminal reply.
sub return_to_parent {
    onpc_progress::operation('Returning to Parent');
    my ($journey, $license, $route) = @_;
    my $returned = close_window($journey, 'license', $license);
    my $footer = read_footer($journey, $returned, $route);
    return close_window($journey, 'about', $footer);
}

sub run {
    onpc_progress::operation('Checking About and license information');
    my ($exchange, $review) = @_;
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'parent', review => $review);
    # Password recipient checks stay in the qualified input helper. From the
    # desktop onward the controller operates and observes public AT-SPI widgets.
    # No app pixels, geometry, fonts, colors or screenshot similarity can fail it.
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    my $about = open_about($journey, $selected);
    my $license = open_license($journey, $about);
    return_to_parent($journey, $license, 'semantic-reveal');
    $journey->finish();
}

1;
