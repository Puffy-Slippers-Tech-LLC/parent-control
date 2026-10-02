package onpc_parent_about;
use strict;
use warnings;
use onpc_progress ();
use onpc_journey ();
use onpc_parent ();
use onpc_gdm ();
use onpc_about ();
use onpc_request_flow ();

# Complete E2E-042/child-overlay composition; qualifications remain separate.
sub run_overlay {
    onpc_progress::operation('Reading overlay Help and About and returning to the unchanged request');
    my ($exchange, $declared, $challenges) = @_;
    die 'overlay-about:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($declared) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'overlay-about', review => 0);
    $journey->declare_invocations($declared);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    $journey->consume_observation('allowance-configured', onpc_parent::set_allowance(
        $journey, 'gdm', 'parent', 'fresh', 'new', 'child', 0, 30, 1));
    for my $stage ('switch-user', 'gdm-switched') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    onpc_gdm::sign_in_challenge($journey, 'child-login',
        'fresh-installed-greeter', 'fresh-child-focused', 'fresh-desktop');
    onpc_request_flow::overlay_entry($journey, 'direct', 'command');
    onpc_request_flow::prepare($journey, 'open', 'open', 'default',
        'fixture-child', 'fixture-parent', 75, 1, 'overlay');
    $journey->consume_observation('form-returned', onpc_about::overlay_license(
        $journey, $journey->seen('captured-form'), 'captured-form', '', 'information'));
    for my $stage ('cancel', 'returned') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    $journey->finish();
}

sub run {
    onpc_progress::operation('Checking About and license information');
    my ($exchange, $review) = @_;
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'parent', review => $review);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    my $about = onpc_about::open_about($journey, $selected);
    my $license = onpc_about::open_license($journey, $about);
    onpc_about::return_to_parent($journey, $license, 'semantic-reveal');
    $journey->finish();
}

# Complete E2E-042/parent-links composition, independent of qualification.
sub run_links {
    onpc_progress::operation('Reading Parent Help and About information');
    my ($exchange) = @_;
    my $journey = onpc_journey->new(
        exchange => $exchange, prefix => 'parent-links', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    my $help = onpc_about::read_help($journey, $selected);
    my $about = onpc_about::open_from_help($journey, $help);
    my $links = onpc_about::check_link($journey, $about, 'information');
    onpc_about::return_to_parent($journey, $links, 'semantic-reveal');
    $journey->finish();
}

sub run_interval {
    onpc_progress::operation('Qualifying a guarded real interval between About reads');
    my ($exchange) = @_;
    die 'real-interval:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'real-interval', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    onpc_about::open_about($journey, $selected);
    $journey->seen('before');
    $journey->seen('after');
    $journey->finish();
}

1;
