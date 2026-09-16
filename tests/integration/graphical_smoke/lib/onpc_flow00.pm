package onpc_flow00;
use strict;
use warnings;
use testapi ();
use onpc_harness ();
use onpc_gdm ();
use onpc_serial ();

# FLOW00's serial phase also preserves the existing run_functional entry point.
sub serial {
    my ($exchange) = @_;
    my $count = scalar @_;
    return onpc_serial::attempt($exchange, sub {
        my ($state) = @_;
        die 'flow00:arguments' unless $count == 1;
        onpc_serial::login($state);
        onpc_serial::command($state);
        my $logout = onpc_serial::logout($state);
        onpc_serial::return_graphics($state, $logout);
        testapi::record_info('serial-command',
            'Real fixture serial login, fixed command output, logout and graphical return verified.');
    });
}

sub run {
    my ($journey, $exchange) = @_;
    die 'flow00:arguments' unless @_ == 2 && ref($journey) eq 'onpc_journey'
        && ref($exchange) eq 'CODE';
    onpc_harness::select_console('initial', 'sut');
    my $prompt = onpc_gdm::select_prompt($journey, 'parent', 'prompt');
    onpc_gdm::dismiss_observed_prompt($journey, $prompt);
    serial(sub {
        my ($stage, $shot) = @_;
        return $stage eq 'gdm-return' ? $journey->seen($stage) : $exchange->($stage, $shot);
    });
}

1;
