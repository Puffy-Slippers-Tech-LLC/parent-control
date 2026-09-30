# Future COPR SCM source method: "make srpm", repository root, pinned commit.
# Invoked as root only inside COPR's disposable source-build chroot.
# No publishing credentials, upload, or product installation in this recipe.
.PHONY: srpm
srpm:
	@test -n "$(outdir)" || (echo 'COPR must supply outdir' >&2; exit 2)
	dnf -y install python3 rpm-build
	/usr/bin/python3 -B tools/build_rpm.py --srpm --output "$(outdir)"
