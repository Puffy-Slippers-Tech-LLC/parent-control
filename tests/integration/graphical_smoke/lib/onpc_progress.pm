package onpc_progress;
use strict;
use warnings;
use JSON::PP ();
use Fcntl qw(O_WRONLY O_CREAT O_EXCL);

my $sequence = 0;

# Fixed prose only: never pass a password, typed text, account name or UI output.
# Unit consumers without a worker directory do not publish spectator files.
sub operation {
    my ($label) = @_;
    return unless -f 'vars.json';
    eval {
        my $pending = 'watch-operation.tmp';
        sysopen(my $file, $pending, O_WRONLY | O_CREAT | O_EXCL, 0600) or return;
        print {$file} JSON::PP::encode_json({sequence => ++$sequence, operation => $label});
        close($file) or return;
        rename($pending, 'watch-operation.json');
        print STDERR 'ONPC-E2E-OPERATION ' . JSON::PP::encode_json(
            {sequence => $sequence, operation => $label}) . "\n";
    };
    # Viewing is optional and must never change input or acceptance behavior.
    return;
}

1;
