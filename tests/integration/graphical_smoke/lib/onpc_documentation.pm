package onpc_documentation;
use strict;
use warnings;
use onpc_progress ();

# INFO02: read one registered command's public output. The caller owns any
# final desktop return; no terminal launch, arbitrary command or output projection.
sub read {
    onpc_progress::operation('Reading installed command documentation');
    my ($journey, $binding) = @_;
    my %bindings = map { $_ => 1 } qw(parent-help station-help parent-manual station-manual);
    die 'help:binding' unless @_ == 2 && ref($journey) eq 'onpc_journey'
        && defined($binding) && $bindings{$binding};
    return $journey->seen($binding . '-content');
}

1;
