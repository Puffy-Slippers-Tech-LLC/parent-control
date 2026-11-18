"""Stable application identity and packaging selection for the supplied launchers."""
import platform

LUNAR = 'com.lunarclient.LunarClient'


def fedora():
    return platform.freedesktop_os_release().get('ID') == 'fedora'
