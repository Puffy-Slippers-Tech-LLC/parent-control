package onpc_about;
use strict;
use warnings;
use onpc_progress ();
use onpc_window ();

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
    my $returned = onpc_window::close($journey, 'license', $license);
    my $footer = read_footer($journey, $returned, $route);
    return onpc_window::close($journey, 'about', $footer);
}

1;
