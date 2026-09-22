package onpc_terminal;
use strict;
use warnings;
use onpc_progress ();
use testapi ();

# FILE01: terminal opening is environment preparation, using the desktop's
# direct shortcut. Input readiness is observed separately and is also usable
# for independently opened terminals.
sub open {
    onpc_progress::operation('Opening Terminal with Ctrl+Alt+T');
    my ($journey, $desktop) = @_;
    die 'terminal:arguments' unless @_ == 2 && ref($journey) eq 'onpc_journey';
    $journey->consume_observation('desktop', $desktop);
    $journey->seen('system-prompt');
    $journey->seen('terminal-wrong-surface');
    testapi::send_key('ctrl-alt-t');
    return $journey->seen('terminal-opened');
}

# UI21: the supplied input observation is single-use; a fresh check must prove
# focus after the public accessibility focus action before any command is typed.
sub focus {
    onpc_progress::operation('Focusing the terminal input surface');
    my ($journey, $input, $entry) = @_;
    die 'terminal:arguments' unless @_ == 3 && ref($journey) eq 'onpc_journey'
        && ($entry eq 'opened' || $entry eq 'input');
    $journey->consume_observation('terminal-' . $entry, $input);
    return $journey->seen($entry eq 'opened' ? 'terminal-opened-focused' : 'terminal-focused');
}

# FILE06: the launch result is the product's specific GUI refusal. Its observer
# also excludes management controls before this helper returns to the caller.
sub observe_denial {
    onpc_progress::operation('Reading the Parent management-access denial');
    my ($journey) = @_;
    die 'terminal:arguments' unless @_ == 1 && ref($journey) eq 'onpc_journey';
    return $journey->seen('management-denied');
}

# Retired Parent-specific terminal path. PARENT01 owns all command launches;
# terminal command/help blocks remain separate for actual terminal consumers.
sub submit_parent {
    onpc_progress::operation('Refusing the retired Parent terminal launch');
    die 'terminal:parent-launch-requires-shared-block';
}

1;
