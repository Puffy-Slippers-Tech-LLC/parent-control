package onpc_parent_presentation;
use strict;
use warnings;
use onpc_progress ();
use onpc_journey ();
use onpc_gdm ();
use onpc_parent ();
use onpc_allowance_boundaries ();
use onpc_text ();

sub run {
    onpc_progress::operation('Testing the complete Parent English Hebrew English presentation history');
    my ($exchange, $invocations, $challenges) = @_;
    die 'parent-presentation:arguments' unless @_ == 3 && ref($exchange) eq 'CODE'
        && ref($invocations) eq 'ARRAY' && ref($challenges) eq 'HASH';
    my $journey = onpc_journey->new(exchange => $exchange, prefix => 'parent-presentation', review => 0);
    $journey->declare_invocations($invocations);
    $journey->declare_challenges($challenges);
    onpc_gdm::reattach_functional();
    my $desktop = onpc_gdm::sign_in_challenge($journey, 'parent-login',
        'installed-greeter', 'parent-focused', 'desktop');
    onpc_parent::launch($journey, $desktop, 'initial-language');
    $journey->seen('initial-save');
    onpc_allowance_boundaries::select_child($journey, 'riley-setup', 'keyboard');
    $journey->seen($_) for qw(riley-enabled riley-saved riley-allowance policy-captured feedback-empty);
    onpc_text::replace_text($journey, $_) for qw(body-rtl reply-rtl);
    $journey->seen('draft-captured');
    onpc_parent::dialog_close($journey, 'draft');
    for my $language ('english-entry', 'hebrew', 'english-return') {
        onpc_parent::language_presentation_roundtrip($journey, $language);
        for my $surface ('about', 'feedback') {
            onpc_parent::dialog_visit($journey, "$language-$surface",
                $language eq 'hebrew' && $surface eq 'feedback' ? 'rtl' : 'ltr');
        }
        $journey->seen("$language-final");
    }
    $journey->finish();
}

1;
