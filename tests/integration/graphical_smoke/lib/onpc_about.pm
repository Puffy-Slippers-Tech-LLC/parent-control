package onpc_about;
use strict;
use warnings;
use onpc_progress ();
use onpc_window ();

# ABOUT01/02: owned About information and link clickability; no external launch.
sub overlay_license {
    onpc_progress::operation('Reading overlay About/license and returning to unchanged choices');
    my ($journey, $proof, $entry, $invocation, $links) = @_;
    $links //= 'license';
    die 'overlay-about:binding' unless (@_ == 4 || @_ == 5) && ref($journey) eq 'onpc_journey'
        && $entry =~ /\A[a-z][a-z0-9-]*\z/ && $invocation =~ /\A(?:[a-z][a-z0-9-]*-)?\z/;
    die 'overlay-about:links' unless $links eq 'license' || $links eq 'browser-links';
    $journey->consume_observation($entry, $proof);
    for my $stage ('about-open', ($links eq 'license' ? ('license-read') : ('website-read', 'privacy-read'))) {
        $journey->consume_observation($invocation . $stage, $journey->seen($invocation . $stage));
    }
    $journey->consume_observation($invocation . 'about-closed', onpc_window::close(
        $journey, 'overlay-about', $journey->seen($invocation . 'about-close-ready'), $invocation));
    return $journey->seen($invocation . 'form-returned');
}

sub open_about {
    onpc_progress::operation('Opening About');
    my ($journey, $selected) = @_;
    $journey->consume_observation('parent-selected', $selected);
    return $journey->seen('about');
}

sub read_help {
    onpc_progress::operation('Checking Parent Help clickability');
    my ($journey, $selected) = @_;
    $journey->consume_observation('parent-selected', $selected);
    return $journey->seen('help');
}

sub open_from_help {
    onpc_progress::operation('Opening About from the owned menu');
    my ($journey, $help) = @_;
    $journey->consume_observation('help', $help);
    return $journey->seen('about');
}

sub open_license {
    onpc_progress::operation('Checking the license link is clickable');
    my ($journey, $about, $stage) = @_;
    $stage //= 'about';
    die 'about:license-stage' unless (@_ == 2 && $stage eq 'about')
        || (@_ == 3 && $stage eq 'about-rechecked');
    return check_link($journey, $about, 'license', $stage);
}

sub check_link {
    onpc_progress::operation('Checking declared information link clickability');
    my ($journey, $about, $link, $stage) = @_;
    $stage //= 'about';
    die 'about:link-binding' unless (@_ == 3 || @_ == 4)
        && ($link eq 'website' || $link eq 'license' || $link eq 'privacy'
            || $link eq 'support' || $link eq 'information')
        && ($stage eq 'about' || $stage eq 'about-rechecked');
    $journey->consume_observation($stage, $about);
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
    my ($journey, $license, $route, $stage) = @_;
    $stage //= 'license';
    die 'about:return-binding' unless (@_ == 3 || @_ == 4)
        && $route eq 'semantic-reveal'
        && ($stage eq 'license' || $stage eq 'license-provider-refusals');
    $journey->consume_observation($stage, $license);
    my $returned = $journey->seen('license-closed');
    my $footer = read_footer($journey, $returned, $route);
    return onpc_window::close($journey, 'about', $footer);
}

1;
