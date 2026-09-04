PYTHON ?= /usr/bin/python3
CC ?= cc
PREFIX ?= /usr
SYSCONFDIR ?= /etc
LIBEXECDIR ?= $(PREFIX)/libexec
DATADIR ?= $(PREFIX)/share
SYSTEMD_SYSTEM_DIR ?= $(PREFIX)/lib/systemd/system
SYSTEMD_USER_DIR ?= $(PREFIX)/lib/systemd/user
PRODUCT_LIBDIR ?= $(PREFIX)/lib/oh-no-parent-control
MULTIARCH ?= $(shell $(CC) -print-multiarch)
PAM_MODULE_DIR ?= $(PREFIX)/lib/$(MULTIARCH)/security
UUID := oh-no-parent-control@tech.puffyslippers.com
ACTIVATION_MANIFEST_PATHS := \
	$(LIBEXECDIR)/oh-no-parent-control-broker \
	$(LIBEXECDIR)/oh-no-parent-control-migrate-state \
	$(LIBEXECDIR)/oh-no-parent-control-login-check \
	$(LIBEXECDIR)/oh-no-parent-control-preserve-extension-state \
	$(LIBEXECDIR)/oh-no-parent-control-execution-policy-ready \
	$(LIBEXECDIR)/oh-no-parent-control-execution-policy-probe \
	$(LIBEXECDIR)/oh-no-parent-control-session-limit-check \
	$(LIBEXECDIR)/oh-no-parent-control-clear-session-runtime-max \
	$(PAM_MODULE_DIR)/pam_oh_no_parent_control.so \
	$(PRODUCT_LIBDIR)/broker \
	$(PRODUCT_LIBDIR)/common \
	$(DATADIR)/gnome-shell/extensions/$(UUID) \
	$(PRODUCT_LIBDIR)/kiosk \
	$(SYSTEMD_SYSTEM_DIR)/oh-no-parent-control-broker.service \
	$(SYSTEMD_SYSTEM_DIR)/oh-no-parent-control-restore-extension-state.service \
	$(SYSTEMD_SYSTEM_DIR)/fapolicyd.service.d/oh-no-parent-control-readiness.conf \
	$(SYSTEMD_SYSTEM_DIR)/display-manager.service.d/oh-no-parent-control.conf \
	$(SYSTEMD_USER_DIR)/oh-no-parent-control-app.service \
	$(SYSTEMD_USER_DIR)/oh-no-parent-control-polkit-agent.service \
	$(SYSTEMD_USER_DIR)/gnome-session@oh-no-parent-control.target.d/session.conf \
	$(DATADIR)/dbus-1/system-services/com.puffyslippers.OhNoParentControl1.service \
	$(DATADIR)/dbus-1/interfaces/com.puffyslippers.OhNoParentControl1.xml \
	$(DATADIR)/dbus-1/system.d/com.puffyslippers.OhNoParentControl1.conf \
	$(DATADIR)/polkit-1/actions/tech.puffyslippers.com.ohnoparentcontrol.child.request-own-access.policy \
	$(DATADIR)/polkit-1/actions/tech.puffyslippers.com.ohnoparentcontrol.kiosk.request-access.policy \
	$(SYSCONFDIR)/fapolicyd/rules.d/99-oh-no-parent-control-allow.rules \
	$(DATADIR)/gnome-session/sessions/oh-no-parent-control.session \
	$(DATADIR)/wayland-sessions/oh-no-parent-control.desktop \
	$(DATADIR)/icons/hicolor/512x512/apps/com.puffyslippers.OhNoParentControl.png \
	$(DATADIR)/oh-no-parent-control/app_logo.png \
	$(DATADIR)/oh-no-parent-control/app_logo_gnome_launcher.png \
	$(DATADIR)/pam-configs/oh-no-parent-control-session-limits \
	$(DATADIR)/pam-configs/oh-no-parent-control-kiosk-only \
	$(SYSCONFDIR)/polkit-1/rules.d/00-oh-no-parent-control-session.rules \
	/etc/gdm3/PreSession/Default
CHILD_DIR := child
EXTENSION_SOURCES := branding.js indicatorLogic.mjs logger.js previewMode.js remainingTimeIndicator.js sessionPreparationClient.js timeCalculationClient.js timerQuery.js
OBSOLETE_EXTENSION_SOURCES := aboutDialog.js appFilterClient.js appPolicyStore.js approverClient.js parentalApproval.js requestAccessClient.js requestDialog.js requestOptions.js requestPreferencesStore.js sessionLimitsClient.js sharedPreferencesClient.js
EXTENSION_ASSETS := request-options.json
# app_logo.png is intentionally limited to 128 pixels for AccountsService;
# app_logo_gnome_launcher.png is the full-resolution GNOME launcher asset.
BRANDING_ASSETS := data/brand.json data/app.json data/app_logo.png data/company_logo.png
EXTENSION_PACK_ASSETS := $(BRANDING_ASSETS) LICENSE COPYRIGHT NOTICE
EXTENSION_BASE ?= $(HOME)/.local/share
EXTENSION_DIR := $(EXTENSION_BASE)/gnome-shell/extensions/$(UUID)
SYSTEM_EXTENSION_DIR := $(DATADIR)/gnome-shell/extensions/$(UUID)

.PHONY: bump-version build installdeb check-release-version check check-unit check-component check-child-node check-child-gjs check-marker check-coverage check-static check-shell check-gjs _install-product-files _generate-package-activation-manifest uninstall pack-extension install-extension preview-kiosk preview-parent preview-child preview-child-overlay

DEB_HOST_ARCH ?= amd64

bump-version:
	@test -n "$(VERSION)" || (echo 'Usage: make bump-version VERSION=x.y [CHANGE="description"]' >&2; exit 2)
	@$(PYTHON) tools/bump_version.py "$(VERSION)" $(if $(CHANGE),--change "$(CHANGE)",)

check-release-version:
	@$(PYTHON) tools/bump_version.py --check

ifeq ($(shell id -u),0)
APT := apt
else
APT := sudo apt
endif

build: check-release-version
	$(APT) update
	$(APT) build-dep .
	dpkg-buildpackage --build=binary --no-sign -a$(DEB_HOST_ARCH)
	version=$$(dpkg-parsechangelog -S Version); \
	architecture=$$(dpkg-architecture -qDEB_HOST_ARCH); \
	output_dir="$(CURDIR)/output"; \
	mkdir -p "$$output_dir"; \
	mv "../oh-no-parent-control_$${version}_$${architecture}.deb" "$$output_dir/"; \
	mv "../oh-no-parent-control_$${version}_$${architecture}.changes" "$$output_dir/"; \
	mv "../oh-no-parent-control_$${version}_$${architecture}.buildinfo" "$$output_dir/"

installdeb:
	@deb_files="$$(find "$(CURDIR)/output" -maxdepth 1 -type f -name '*.deb' -print)"; \
	deb_count="$$(printf '%s\n' "$$deb_files" | sed '/^$$/d' | wc -l)"; \
	test "$$deb_count" -eq 1 || (echo "Expected exactly one .deb file in $(CURDIR)/output, found $$deb_count" >&2; exit 1); \
	echo "Installing $$deb_files"; \
	$(APT) install "$$deb_files"

TEST_ENV = PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=broker:kiosk:$${PYTHONPATH:-}
PYTEST = $(TEST_ENV) $(PYTHON) -m pytest
UI_TEST_PYTHON ?= $(CURDIR)/.venv/onpc-ui-tests/bin/python

check-unit:
	@$(PYTEST) tests/unit -m "unit or contract"

check-component:
	@$(PYTEST) tests/component -m component
	@$(MAKE) --no-print-directory check-child-node
	@$(MAKE) --no-print-directory check-child-gjs
	@test -x "$(UI_TEST_PYTHON)" || (echo 'UI test environment missing; run ./setup.sh' >&2; exit 1)
	@PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=broker:kiosk:$(CURDIR):$${PYTHONPATH:-} \
		"$(UI_TEST_PYTHON)" -m pytest tests/ui -m ui

check-marker:
	@test -n "$(MARKER)" || (echo 'Usage: make check-marker MARKER=unit' >&2; exit 2)
	@$(PYTEST) -m "$(MARKER)"

check-coverage:
	@$(PYTEST) --cov=broker --cov=parent --cov=kiosk --cov=common --cov=tools --cov-branch \
		--cov-report=term-missing --cov-report=html:artifacts/coverage/html \
		--cov-report=xml:artifacts/coverage/coverage.xml

check-shell:
	@$(PYTHON) tools/check_shell.py

check-gjs:
	@$(PYTHON) tools/check_gjs.py

check-static: check-shell check-gjs

check:
	@bash -n install.sh
	@$(CC) $(CPPFLAGS) $(CFLAGS) -Wall -Wextra -Werror -fsyntax-only tools/pam_oh_no_parent_control.c
	@for file in extension.js $(filter %.js %.mjs,$(EXTENSION_SOURCES)); do node --check "$(CHILD_DIR)/$$file"; done
	@$(PYTHON) tools/verify_test_traceability.py --mode stage
	@$(MAKE) --no-print-directory check-unit
	@$(PYTEST) tests/component -m component
	@$(PYTHON) -c 'import ast,pathlib; [ast.parse(p.read_text(), filename=str(p)) for p in pathlib.Path(".").glob("**/*.py") if ".git" not in p.parts]'
	@$(PYTHON) -c 'import pathlib,xml.etree.ElementTree as E; [E.parse(p) for p in pathlib.Path("data").glob("**/*.xml")]; [E.parse(p) for p in pathlib.Path(".").glob("**/*.policy")]'
	@! grep -REn 'org\.freedesktop\.policykit\.imply|ApproveTimeAndApps|Properties.*Set.*(AppFilter|ActiveExtension)' child data/polkit-1
	@! grep -REn 'resource:///org/gnome/shell|AuthPrompt|UnlockDialog|Main\.screenShield|_estimatedTimes' kiosk broker data config tools README.md

preview-kiosk:
	# The preview watches kiosk assets and source files; no manual relaunch is needed.
	PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=kiosk $(PYTHON) -m oh_no_parent_control_kiosk.main --preview --soundtrack "$(CURDIR)/data/Gearbox_Waltz.mp3"

preview-child-overlay:
	# The child overlay is the kiosk GUI in overlay mode, with the current child locked.
	PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=kiosk $(PYTHON) -m oh_no_parent_control_kiosk.main --preview --child-overlay --soundtrack "$(CURDIR)/data/Gearbox_Waltz.mp3"

preview-parent:
	# The preview watches parent source and CSS files; no backend or installation is needed.
	PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=parent $(PYTHON) -m oh_no_parent_control_parent.main --preview

preview-child:
	# A nested Shell loads the checkout by temporary symlink; host settings stay untouched.
	$(CHILD_DIR)/preview

pack-extension:
	gnome-extensions pack "$(CHILD_DIR)" --force --out-dir=. $(EXTENSION_SOURCES:%=--extra-source=%) $(EXTENSION_ASSETS:%=--extra-source=%) $(EXTENSION_PACK_ASSETS:%=--extra-source=%)

install-extension:
	install -d "$(EXTENSION_DIR)"
	rm -f $(foreach file,$(OBSOLETE_EXTENSION_SOURCES),"$(EXTENSION_DIR)/$(file)")
	install -m 0644 $(addprefix $(CHILD_DIR)/,metadata.json stylesheet.css extension.js $(EXTENSION_SOURCES) $(EXTENSION_ASSETS)) "$(EXTENSION_DIR)/"
	install -m 0644 $(BRANDING_ASSETS) LICENSE COPYRIGHT NOTICE "$(EXTENSION_DIR)/"
	@echo "Installed $(UUID) to $(EXTENSION_DIR)"

# Internal target used by install.sh. Keep privileged host orchestration in the
# shell installer and declarative product-file installation in the Makefile.
_install-product-files:
	install -d "$(DESTDIR)$(PREFIX)/bin" "$(DESTDIR)$(LIBEXECDIR)" "$(DESTDIR)$(PAM_MODULE_DIR)"
	install -m 0755 kiosk/oh-no-parent-control "$(DESTDIR)$(PREFIX)/bin/"
	install -m 0755 parent/oh-no-parent-control-parent "$(DESTDIR)$(PREFIX)/bin/"
	install -m 0755 broker/oh-no-parent-control-broker "$(DESTDIR)$(LIBEXECDIR)/"
	install -m 0755 broker/oh-no-parent-control-migrate-state "$(DESTDIR)$(LIBEXECDIR)/"
	install -m 0755 broker/oh-no-parent-control-uninstall "$(DESTDIR)$(LIBEXECDIR)/"
	install -m 0755 tools/oh-no-parent-control-login-check "$(DESTDIR)$(LIBEXECDIR)/"
	install -m 0755 tools/execution_policy_ready.py "$(DESTDIR)$(LIBEXECDIR)/oh-no-parent-control-execution-policy-ready"
	install -m 0755 tools/execution_policy_probe "$(DESTDIR)$(LIBEXECDIR)/oh-no-parent-control-execution-policy-probe"
	install -m 0755 broker/oh-no-parent-control-query-usage "$(DESTDIR)$(LIBEXECDIR)/"
	install -m 0755 tools/preserve_extension_state.py "$(DESTDIR)$(LIBEXECDIR)/oh-no-parent-control-preserve-extension-state"
	install -m 0755 tools/session_limit_check.py "$(DESTDIR)$(LIBEXECDIR)/oh-no-parent-control-session-limit-check"
	$(CC) $(CPPFLAGS) $(CFLAGS) -Wall -Wextra -Werror -fPIC -shared $(LDFLAGS) -Wl,-z,defs \
		-o "$(DESTDIR)$(PAM_MODULE_DIR)/pam_oh_no_parent_control.so" \
		tools/pam_oh_no_parent_control.c -lpam
	chmod 0644 "$(DESTDIR)$(PAM_MODULE_DIR)/pam_oh_no_parent_control.so"
	install -m 0755 tools/clear_session_runtime_max.py "$(DESTDIR)$(LIBEXECDIR)/oh-no-parent-control-clear-session-runtime-max"
	install -m 0755 tools/package_activation.py "$(DESTDIR)$(LIBEXECDIR)/oh-no-parent-control-package-activation"
	install -d "$(DESTDIR)$(PRODUCT_LIBDIR)/kiosk/oh_no_parent_control_kiosk" "$(DESTDIR)$(PRODUCT_LIBDIR)/broker/oh_no_parent_control" "$(DESTDIR)$(PRODUCT_LIBDIR)/common/oh_no_parent_control_ui"
	install -m 0644 common/__init__.py "$(DESTDIR)$(PRODUCT_LIBDIR)/common/"
	install -m 0644 common/oh_no_parent_control_ui/*.py "$(DESTDIR)$(PRODUCT_LIBDIR)/common/oh_no_parent_control_ui/"
	install -m 0644 kiosk/oh_no_parent_control_kiosk/*.py kiosk/oh_no_parent_control_kiosk/style.css kiosk/oh_no_parent_control_kiosk/kiosk-background.jpeg data/Gearbox_Waltz.mp3 child/request-options.json "$(DESTDIR)$(PRODUCT_LIBDIR)/kiosk/oh_no_parent_control_kiosk/"
	install -d "$(DESTDIR)$(PRODUCT_LIBDIR)/kiosk/oh_no_parent_control_kiosk/fonts"
	install -m 0644 kiosk/oh_no_parent_control_kiosk/fonts/Monocraft.ttf kiosk/oh_no_parent_control_kiosk/fonts/OFL.txt "$(DESTDIR)$(PRODUCT_LIBDIR)/kiosk/oh_no_parent_control_kiosk/fonts/"
	install -d "$(DESTDIR)$(PRODUCT_LIBDIR)/parent/oh_no_parent_control_parent" "$(DESTDIR)$(SYSTEM_EXTENSION_DIR)"
	install -m 0644 parent/oh_no_parent_control_parent/*.py parent/oh_no_parent_control_parent/style.css "$(DESTDIR)$(PRODUCT_LIBDIR)/parent/oh_no_parent_control_parent/"
	# GNOME Shell discovers extensions only when the Shell process starts. Keep
	# one immutable system payload discoverable in every session; the broker
	# controls per-child activation through that child's GNOME settings.
	rm -f $(foreach file,$(OBSOLETE_EXTENSION_SOURCES),"$(DESTDIR)$(SYSTEM_EXTENSION_DIR)/$(file)")
	install -m 0644 $(addprefix $(CHILD_DIR)/,metadata.json stylesheet.css extension.js $(EXTENSION_SOURCES) $(EXTENSION_ASSETS)) "$(DESTDIR)$(SYSTEM_EXTENSION_DIR)/"
	install -m 0644 $(BRANDING_ASSETS) LICENSE COPYRIGHT NOTICE "$(DESTDIR)$(SYSTEM_EXTENSION_DIR)/"
	# Clean the obsolete broker source copy during a direct upgrade.
	rm -rf "$(DESTDIR)$(PRODUCT_LIBDIR)/child/extension"
	install -m 0644 broker/oh_no_parent_control/*.py "$(DESTDIR)$(PRODUCT_LIBDIR)/broker/oh_no_parent_control/"
	install -d "$(DESTDIR)$(DATADIR)/dbus-1/system-services" "$(DESTDIR)$(DATADIR)/dbus-1/interfaces"
	install -m 0644 data/dbus-1/system-services/com.puffyslippers.OhNoParentControl1.service "$(DESTDIR)$(DATADIR)/dbus-1/system-services/"
	install -m 0644 data/dbus-1/com.puffyslippers.OhNoParentControl1.xml "$(DESTDIR)$(DATADIR)/dbus-1/interfaces/"
	install -d "$(DESTDIR)$(DATADIR)/polkit-1/actions" "$(DESTDIR)$(SYSTEMD_SYSTEM_DIR)"
	# The broker is the trusted Polkit mechanism for both request front ends.
	# Remove the obsolete child-owned meta-action during direct installations.
	rm -f "$(DESTDIR)$(DATADIR)/polkit-1/actions/org.gnome.shell.extensions.oh-no-parent-control.policy"
	$(PYTHON) tools/render_polkit_policy.py --template data/polkit-1/actions/tech.puffyslippers.com.ohnoparentcontrol.child.request-own-access.policy.in --branding data/brand.json --output "$(DESTDIR)$(DATADIR)/polkit-1/actions/tech.puffyslippers.com.ohnoparentcontrol.child.request-own-access.policy"
	$(PYTHON) tools/render_polkit_policy.py --template data/polkit-1/actions/tech.puffyslippers.com.ohnoparentcontrol.kiosk.request-access.policy.in --branding data/brand.json --output "$(DESTDIR)$(DATADIR)/polkit-1/actions/tech.puffyslippers.com.ohnoparentcontrol.kiosk.request-access.policy"
	install -d "$(DESTDIR)$(SYSCONFDIR)/polkit-1/rules.d"
	install -m 0644 data/polkit-1/rules.d/00-oh-no-parent-control-session.rules "$(DESTDIR)$(SYSCONFDIR)/polkit-1/rules.d/"
	install -d "$(DESTDIR)$(DATADIR)/pam-configs" "$(DESTDIR)$(SYSCONFDIR)/gdm3/PreSession"
	install -m 0644 data/pam-configs/oh-no-parent-control-session-limits data/pam-configs/oh-no-parent-control-kiosk-only "$(DESTDIR)$(DATADIR)/pam-configs/"
	install -m 0755 data/gdm3/PreSession/Default "$(DESTDIR)$(SYSCONFDIR)/gdm3/PreSession/Default"
	install -d "$(DESTDIR)$(SYSCONFDIR)/fapolicyd/rules.d"
	install -m 0644 data/fapolicyd/99-oh-no-parent-control-allow.rules "$(DESTDIR)$(SYSCONFDIR)/fapolicyd/rules.d/"
	install -m 0644 data/systemd/oh-no-parent-control-broker.service "$(DESTDIR)$(SYSTEMD_SYSTEM_DIR)/"
	install -m 0644 data/systemd/oh-no-parent-control-restore-extension-state.service "$(DESTDIR)$(SYSTEMD_SYSTEM_DIR)/"
	install -d "$(DESTDIR)$(SYSTEMD_SYSTEM_DIR)/fapolicyd.service.d" "$(DESTDIR)$(SYSTEMD_SYSTEM_DIR)/display-manager.service.d"
	install -m 0644 data/systemd/fapolicyd.service.d/oh-no-parent-control-readiness.conf "$(DESTDIR)$(SYSTEMD_SYSTEM_DIR)/fapolicyd.service.d/"
	install -m 0644 data/systemd/display-manager.service.d/oh-no-parent-control.conf "$(DESTDIR)$(SYSTEMD_SYSTEM_DIR)/display-manager.service.d/"
	install -d "$(DESTDIR)$(SYSTEMD_USER_DIR)/gnome-session@oh-no-parent-control.target.d"
	install -m 0644 data/systemd/user/oh-no-parent-control-*.service "$(DESTDIR)$(SYSTEMD_USER_DIR)/"
	install -m 0644 data/systemd/user/gnome-session@oh-no-parent-control.target.d/session.conf "$(DESTDIR)$(SYSTEMD_USER_DIR)/gnome-session@oh-no-parent-control.target.d/"
	install -d "$(DESTDIR)$(DATADIR)/gnome-session/sessions" "$(DESTDIR)$(DATADIR)/wayland-sessions" "$(DESTDIR)$(DATADIR)/applications" "$(DESTDIR)$(DATADIR)/icons/hicolor/512x512/apps"
	install -m 0644 data/gnome-session/sessions/oh-no-parent-control.session "$(DESTDIR)$(DATADIR)/gnome-session/sessions/"
	install -m 0644 data/wayland-sessions/oh-no-parent-control.desktop "$(DESTDIR)$(DATADIR)/wayland-sessions/"
	install -m 0644 data/app_logo_gnome_launcher.png "$(DESTDIR)$(DATADIR)/icons/hicolor/512x512/apps/com.puffyslippers.OhNoParentControl.png"
	install -m 0644 data/applications/com.puffyslippers.OhNoParentControl.desktop "$(DESTDIR)$(DATADIR)/applications/"
	# GNOME only indexes desktop entries the signed-in user can read.  The
	# installer/package assigns this file to Ubuntu's administrator group.
	install -m 0640 data/applications/com.puffyslippers.OhNoParentControl.Parent.desktop "$(DESTDIR)$(DATADIR)/applications/"
	install -d "$(DESTDIR)$(DATADIR)/oh-no-parent-control" "$(DESTDIR)$(DATADIR)/doc/oh-no-parent-control"
	install -m 0644 config/config.example.json $(BRANDING_ASSETS) data/app_logo_gnome_launcher.png LICENSE COPYRIGHT NOTICE "$(DESTDIR)$(DATADIR)/oh-no-parent-control/"
	install -m 0644 data/dbus-1/system.d/com.puffyslippers.OhNoParentControl1.conf.in "$(DESTDIR)$(DATADIR)/oh-no-parent-control/"
	install -m 0755 tools/provision.py "$(DESTDIR)$(LIBEXECDIR)/oh-no-parent-control-provision"
	install -m 0644 README.md LICENSE COPYRIGHT NOTICE docs/Compliance.md docs/System-Design.md docs/Package-Update.md docs/Publishing.md docs/Data-Migration.md docs/malcontent014-integration.md "$(DESTDIR)$(DATADIR)/doc/oh-no-parent-control/"
ifneq ($(GENERATE_ACTIVATION_MANIFEST),0)
	$(MAKE) --no-print-directory _generate-package-activation-manifest DESTDIR="$(DESTDIR)" PREFIX="$(PREFIX)" SYSCONFDIR="$(SYSCONFDIR)" LIBEXECDIR="$(LIBEXECDIR)" DATADIR="$(DATADIR)" SYSTEMD_SYSTEM_DIR="$(SYSTEMD_SYSTEM_DIR)" SYSTEMD_USER_DIR="$(SYSTEMD_USER_DIR)" PRODUCT_LIBDIR="$(PRODUCT_LIBDIR)"
endif

_generate-package-activation-manifest:
	$(PYTHON) tools/package_activation.py generate --root "$(if $(strip $(DESTDIR)),$(DESTDIR),/)" --output "$(DESTDIR)$(DATADIR)/oh-no-parent-control/package-activation.json" $(foreach path,$(ACTIVATION_MANIFEST_PATHS),--include "$(patsubst /%,%,$(path))")

uninstall:
	rm -f "$(DESTDIR)$(PREFIX)/bin/oh-no-parent-control" "$(DESTDIR)$(PREFIX)/bin/oh-no-parent-control-parent" "$(DESTDIR)$(LIBEXECDIR)/oh-no-parent-control-broker" "$(DESTDIR)$(LIBEXECDIR)/oh-no-parent-control-migrate-state" "$(DESTDIR)$(LIBEXECDIR)/oh-no-parent-control-uninstall" "$(DESTDIR)$(LIBEXECDIR)/oh-no-parent-control-query-usage" "$(DESTDIR)$(LIBEXECDIR)/oh-no-parent-control-provision" "$(DESTDIR)$(LIBEXECDIR)/oh-no-parent-control-login-check" "$(DESTDIR)$(LIBEXECDIR)/oh-no-parent-control-preserve-extension-state" "$(DESTDIR)$(LIBEXECDIR)/oh-no-parent-control-session-limit-check" "$(DESTDIR)$(LIBEXECDIR)/oh-no-parent-control-clear-session-runtime-max" "$(DESTDIR)$(LIBEXECDIR)/oh-no-parent-control-package-activation" "$(DESTDIR)$(LIBEXECDIR)/oh-no-parent-control-execution-policy-ready" "$(DESTDIR)$(LIBEXECDIR)/oh-no-parent-control-execution-policy-probe" "$(DESTDIR)$(PAM_MODULE_DIR)/pam_oh_no_parent_control.so"
	rm -f "$(DESTDIR)$(DATADIR)/dbus-1/system-services/com.puffyslippers.OhNoParentControl1.service" "$(DESTDIR)$(DATADIR)/dbus-1/interfaces/com.puffyslippers.OhNoParentControl1.xml" "$(DESTDIR)$(DATADIR)/dbus-1/system.d/com.puffyslippers.OhNoParentControl1.conf"
	rm -f "$(DESTDIR)$(DATADIR)/polkit-1/actions/org.gnome.shell.extensions.oh-no-parent-control.policy" "$(DESTDIR)$(DATADIR)/polkit-1/actions/tech.puffyslippers.com.ohnoparentcontrol.child.request-own-access.policy" "$(DESTDIR)$(DATADIR)/polkit-1/actions/tech.puffyslippers.com.ohnoparentcontrol.kiosk.request-access.policy" "$(DESTDIR)$(SYSTEMD_SYSTEM_DIR)/oh-no-parent-control-broker.service" "$(DESTDIR)$(SYSTEMD_SYSTEM_DIR)/oh-no-parent-control-restore-extension-state.service" "$(DESTDIR)$(SYSTEMD_SYSTEM_DIR)/fapolicyd.service.d/oh-no-parent-control-readiness.conf" "$(DESTDIR)$(SYSTEMD_SYSTEM_DIR)/display-manager.service.d/oh-no-parent-control.conf"
	rm -f "$(DESTDIR)$(SYSCONFDIR)/polkit-1/rules.d/00-oh-no-parent-control-session.rules"
	rm -f "$(DESTDIR)$(DATADIR)/pam-configs/oh-no-parent-control-session-limits" "$(DESTDIR)$(DATADIR)/pam-configs/oh-no-parent-control-kiosk-only" "$(DESTDIR)$(SYSCONFDIR)/gdm3/PreSession/Default"
	rm -f "$(DESTDIR)$(SYSCONFDIR)/fapolicyd/rules.d/89-oh-no-parent-control.rules" "$(DESTDIR)$(SYSCONFDIR)/fapolicyd/rules.d/99-oh-no-parent-control-allow.rules"
	rm -f "$(DESTDIR)$(SYSTEMD_USER_DIR)/oh-no-parent-control-app.service" "$(DESTDIR)$(SYSTEMD_USER_DIR)/oh-no-parent-control-polkit-agent.service" "$(DESTDIR)$(SYSTEMD_USER_DIR)/gnome-session@oh-no-parent-control.target.d/session.conf"
	rm -f "$(DESTDIR)$(DATADIR)/gnome-session/sessions/oh-no-parent-control.session" "$(DESTDIR)$(DATADIR)/wayland-sessions/oh-no-parent-control.desktop" "$(DESTDIR)$(DATADIR)/icons/hicolor/512x512/apps/com.puffyslippers.OhNoParentControl.png" "$(DESTDIR)$(DATADIR)/applications/com.puffyslippers.OhNoParentControl.desktop" "$(DESTDIR)$(DATADIR)/applications/com.puffyslippers.OhNoParentControl.Parent.desktop"
	rm -f "$(DESTDIR)$(SYSTEM_EXTENSION_DIR)/"*.js "$(DESTDIR)$(SYSTEM_EXTENSION_DIR)/"*.json "$(DESTDIR)$(SYSTEM_EXTENSION_DIR)/stylesheet.css" "$(DESTDIR)$(SYSTEM_EXTENSION_DIR)/app_logo.png" "$(DESTDIR)$(SYSTEM_EXTENSION_DIR)/company_logo.png" "$(DESTDIR)$(SYSTEM_EXTENSION_DIR)/LICENSE" "$(DESTDIR)$(SYSTEM_EXTENSION_DIR)/COPYRIGHT" "$(DESTDIR)$(SYSTEM_EXTENSION_DIR)/NOTICE"
	rm -f "$(DESTDIR)$(DATADIR)/oh-no-parent-control/config.example.json" "$(DESTDIR)$(DATADIR)/oh-no-parent-control/brand.json" "$(DESTDIR)$(DATADIR)/oh-no-parent-control/app.json" "$(DESTDIR)$(DATADIR)/oh-no-parent-control/app_logo.png" "$(DESTDIR)$(DATADIR)/oh-no-parent-control/app_logo_gnome_launcher.png" "$(DESTDIR)$(DATADIR)/oh-no-parent-control/company_logo.png" "$(DESTDIR)$(DATADIR)/oh-no-parent-control/LICENSE" "$(DESTDIR)$(DATADIR)/oh-no-parent-control/COPYRIGHT" "$(DESTDIR)$(DATADIR)/oh-no-parent-control/NOTICE" "$(DESTDIR)$(DATADIR)/oh-no-parent-control/com.puffyslippers.OhNoParentControl1.conf.in" "$(DESTDIR)$(DATADIR)/oh-no-parent-control/package-activation.json"
	rm -f "$(DESTDIR)$(DATADIR)/doc/oh-no-parent-control/README.md" "$(DESTDIR)$(DATADIR)/doc/oh-no-parent-control/LICENSE" "$(DESTDIR)$(DATADIR)/doc/oh-no-parent-control/COPYRIGHT" "$(DESTDIR)$(DATADIR)/doc/oh-no-parent-control/NOTICE" "$(DESTDIR)$(DATADIR)/doc/oh-no-parent-control/Compliance.md" "$(DESTDIR)$(DATADIR)/doc/oh-no-parent-control/System-Design.md" "$(DESTDIR)$(DATADIR)/doc/oh-no-parent-control/Package-Update.md" "$(DESTDIR)$(DATADIR)/doc/oh-no-parent-control/Publishing.md" "$(DESTDIR)$(DATADIR)/doc/oh-no-parent-control/Data-Migration.md" "$(DESTDIR)$(DATADIR)/doc/oh-no-parent-control/malcontent014-integration.md"
	rm -f "$(DESTDIR)$(SYSCONFDIR)/oh-no-parent-control/config.json"
	rm -f "$(DESTDIR)$(PRODUCT_LIBDIR)/kiosk/oh_no_parent_control_kiosk/"*.py "$(DESTDIR)$(PRODUCT_LIBDIR)/kiosk/oh_no_parent_control_kiosk/style.css" "$(DESTDIR)$(PRODUCT_LIBDIR)/kiosk/oh_no_parent_control_kiosk/kiosk-background.jpeg" "$(DESTDIR)$(PRODUCT_LIBDIR)/kiosk/oh_no_parent_control_kiosk/Gearbox_Waltz.mp3" "$(DESTDIR)$(PRODUCT_LIBDIR)/kiosk/oh_no_parent_control_kiosk/request-options.json" "$(DESTDIR)$(PRODUCT_LIBDIR)/kiosk/oh_no_parent_control_kiosk/fonts/Monocraft.ttf" "$(DESTDIR)$(PRODUCT_LIBDIR)/kiosk/oh_no_parent_control_kiosk/fonts/OFL.txt" "$(DESTDIR)$(PRODUCT_LIBDIR)/broker/oh_no_parent_control/"*.py
	rm -f "$(DESTDIR)$(PRODUCT_LIBDIR)/common/__init__.py" "$(DESTDIR)$(PRODUCT_LIBDIR)/common/oh_no_parent_control_ui/"*.py "$(DESTDIR)$(PRODUCT_LIBDIR)/parent/oh_no_parent_control_parent/"*.py "$(DESTDIR)$(PRODUCT_LIBDIR)/parent/oh_no_parent_control_parent/style.css" "$(DESTDIR)$(PRODUCT_LIBDIR)/child/extension/"*.js "$(DESTDIR)$(PRODUCT_LIBDIR)/child/extension/"*.json "$(DESTDIR)$(PRODUCT_LIBDIR)/child/extension/stylesheet.css" "$(DESTDIR)$(PRODUCT_LIBDIR)/child/extension/app_logo.png" "$(DESTDIR)$(PRODUCT_LIBDIR)/child/extension/company_logo.png" "$(DESTDIR)$(PRODUCT_LIBDIR)/child/extension/LICENSE" "$(DESTDIR)$(PRODUCT_LIBDIR)/child/extension/COPYRIGHT" "$(DESTDIR)$(PRODUCT_LIBDIR)/child/extension/NOTICE"
	@echo 'Product files removed. Accounts and managed-account policies were not changed.'

check-child-node:
	@node --test tests/child/indicator_logic.test.mjs

check-child-gjs:
	@rm -rf artifacts/coverage/gjs-child
	@mkdir -p artifacts/coverage/gjs-child
	@gjs --coverage-prefix="$(CURDIR)/child" --coverage-output="$(CURDIR)/artifacts/coverage/gjs-child" -m tests/child/gjs_adapters_test.js
