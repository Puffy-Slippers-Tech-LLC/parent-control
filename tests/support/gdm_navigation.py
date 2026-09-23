"""Shared Perl harness for GDM navigation qualification contracts."""

RUN = r'''
use strict;
use warnings;
use JSON::PP;
our @events;
BEGIN { $INC{'testapi.pm'} = 1; }
package testapi;
sub current_console { 'sut' }
sub reset_consoles { push @main::events, ['reset'] }
sub select_console { push @main::events, ['console', $_[0]] }
sub send_key { push @main::events, ['key', $_[0]] }
sub record_info { push @main::events, ['stage', $_[0]] }
sub console { bless {}, 'Console' }
sub power { push @main::events, ['power', $_[0]] }
sub check_shutdown { 1 }
package Console;
sub disable { push @main::events, ['disable'] }
package main;
require onpc_gdm;
my $ok = eval {
    onpc_gdm::navigation_qualification(sub {
        my ($stage) = @_;
        push @events, ['exchange', $stage];
        return {ui_focused => 1} if $stage =~ /-list\z/;
        return {observed => $stage};
    });
    1;
};
print encode_json({ok => $ok ? 1 : 0, error => $@, events => \@events});
'''
