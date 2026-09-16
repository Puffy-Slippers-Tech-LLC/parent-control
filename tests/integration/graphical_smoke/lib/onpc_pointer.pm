package onpc_pointer;
use strict;
use warnings;
use onpc_progress ();
use testapi ();

# generalhw normalizes screenshots, but its public VNC pointer methods use
# framebuffer coordinates. Derive every click from the positive match and
# the public console dimensions; never fall back to a fixed screen position.
sub click {
    onpc_progress::operation('Clicking the matched control');
    my ($tag, $timeout) = @_;
    die 'pointer:click-arguments' unless @_ == 2 && defined($tag) && defined($timeout)
        && $tag =~ /\Aonpc-[a-z0-9]+(?:-[a-z0-9]+)*\z/
        && $timeout =~ /\A[0-9]+\z/ && $timeout >= 1 && $timeout <= 90;
    die 'pointer:click-console' unless testapi::current_console() eq 'sut';
    my $match = testapi::assert_screen($tag, $timeout);
    die 'pointer:click-match' unless ref($match) eq 'HASH' && ref($match->{area}) eq 'ARRAY'
        && @{$match->{area}};
    for my $area (@{$match->{area}}) {
        die 'pointer:click-quality' unless defined($area->{similarity}) && $area->{similarity} == 1;
    }
    my $area = $match->{area}->[-1];
    my $point = $area->{click_point};
    die 'pointer:click-point' unless ref($point) eq 'HASH'
        && $point->{xpos} > 0 && $point->{xpos} < $area->{w}
        && $point->{ypos} > 0 && $point->{ypos} < $area->{h}
        && $area->{x} >= 0 && $area->{x} + $area->{w} <= 1024
        && $area->{y} >= 0 && $area->{y} + $area->{h} <= 768;
    die 'pointer:click-image-size' unless testapi::get_var('XRES', 1024) == 1024
        && testapi::get_var('YRES', 768) == 768;
    my $console = testapi::console('sut');
    my ($width, $height) = ($console->mouse_width(), $console->mouse_height());
    die 'pointer:click-framebuffer-size' unless defined($width) && defined($height)
        && (($width == 1280 && $height == 800) || ($width == 1024 && $height == 768));
    testapi::mouse_set(int(($area->{x} + $point->{xpos}) * $width / 1024),
                       int(($area->{y} + $point->{ypos}) * $height / 768));
    testapi::mouse_click('left');
    testapi::wait_still_screen(1, 10);
    testapi::mouse_hide();
}

1;
