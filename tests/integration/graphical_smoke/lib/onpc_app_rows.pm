package onpc_app_rows;
use strict;
use warnings;
use onpc_progress ();
use onpc_gdm ();
use onpc_journey ();
use onpc_parent ();

sub run {
    onpc_progress::operation('Qualifying complete App Limits row observations');
    my ($exchange) = @_;
    die 'app-rows:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(
        exchange => $exchange, prefix => 'app-rows', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    read_rows($journey);
    $journey->finish();
}

# PARENT12/UI13 shared finite complete-read, refusals and independent reread.
sub read_rows {
    onpc_progress::operation('Reading complete public App Limits rows');
    my ($journey) = @_;
    die 'app-rows:arguments' unless @_ == 1 && ref($journey) eq 'onpc_journey';
    for my $stage ('apps-page', 'app-rows', 'wrong-child', 'wrong-page', 'reopened-rows') {
        my $result = $journey->seen($stage);
        $journey->consume_observation($stage, $result);
    }
}

sub native_fixtures {
    onpc_progress::operation('Verifying baseline native fixtures and observing their public catalogue rows');
    my ($exchange) = @_;
    die 'native:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'native-fixtures', review => 0);
    onpc_gdm::reattach_functional();
    my $desktop = onpc_parent::enter_desktop($journey, 'gdm', 'parent', 'fresh', 'success');
    onpc_parent::launch($journey, $desktop, 'management');
    my $selected = onpc_parent::select_child($journey, 'child',
        $journey->seen('child-picker-opened'), 'child-picker-opened',
        'child-choice-highlighted', 'parent-selected');
    $journey->consume_observation('parent-selected', $selected);
    read_rows($journey);
    $journey->finish();
}

1;
