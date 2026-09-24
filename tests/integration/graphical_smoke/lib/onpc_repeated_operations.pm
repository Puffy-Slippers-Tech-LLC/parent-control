package onpc_repeated_operations;
use strict;
use warnings;
use onpc_progress ();
use onpc_journey ();
use onpc_parent ();
use onpc_gdm ();

sub run {
    onpc_progress::operation('Qualifying repeated public operations with distinct stages');
    my ($exchange, $declared) = @_;
    my @stages = qw(wrong-child-refused baseline-first apps-first return-first
                    baseline-second apps-second return-second);
    die 'repeated:invocation-plan' unless ref($declared) eq 'ARRAY'
        && join('/', @$declared) eq join('/', @stages);
    my $journey = onpc_journey->new(
        exchange => $exchange, prefix => 'repeated-operations', review => 0);
    $journey->declare_invocations($declared);
    onpc_gdm::reattach_functional();
    my $reply = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    my $prior = 'parent-selected';
    for my $stage (@stages) {
        $journey->consume_observation($prior, $reply);
        $reply = $journey->invoke($stage);
        $prior = $stage;
    }
    $journey->consume_observation($prior, $reply);
    $journey->finish();
}

1;
