package onpc_format;
use strict;
use warnings;
use testapi ();
use onpc_progress ();
use onpc_gdm ();
use onpc_journey ();
use onpc_parent ();
use onpc_text ();

sub apply_bold {
    onpc_progress::operation('Formatting the declared synthetic range and reading public text attributes');
    my ($journey) = @_;
    die 'format:arguments' unless @_ == 1 && ref($journey) eq 'onpc_journey';
    $journey->consume_observation('format-focus', $journey->seen('format-focus'));
    testapi::send_key('ctrl-home');
    $journey->consume_observation('format-home', $journey->seen('format-home'));
    testapi::send_key('shift-right') for 1 .. 9;
    for my $stage ('format-selected', 'format-read') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
}

sub run {
    onpc_progress::operation('Qualifying feedback formatting without sending');
    my ($exchange) = @_;
    die 'format:arguments' unless @_ == 1 && ref($exchange) eq 'CODE';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'format', review => 0);
    onpc_gdm::reattach_functional();
    my $selected = onpc_parent::open_for_child($journey, 'gdm', 'fresh', 'new', 'child');
    $journey->consume_observation('parent-selected', $selected);
    $journey->consume_observation('feedback-open', $journey->seen('feedback-open'));
    onpc_text::replace_text($journey, 'body-first');
    $journey->consume_observation('format-before', $journey->seen('format-before'));
    apply_bold($journey);
    for my $stage ('format-close', 'format-wrong-entry', 'format-reopen') {
        $journey->consume_observation($stage, $journey->seen($stage));
    }
    $journey->finish();
}
1;
