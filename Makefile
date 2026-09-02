PYTHON ?= /usr/bin/python3
PREFIX ?= /usr
SYSCONFDIR ?= /etc
LIBEXECDIR ?= $(PREFIX)/libexec
DATADIR ?= $(PREFIX)/share
SYSTEMD_SYSTEM_DIR ?= $(PREFIX)/lib/systemd/system
SYSTEMD_USER_DIR ?= $(PREFIX)/lib/systemd/user
PRODUCT_LIBDIR ?= $(PREFIX)/lib/oh-no-parent-control
ACTIVATION_MANIFEST_PATHS := \
	$(LIBEXECDIR)/oh-no-parent-control-broker \
	$(LIBEXECDIR)/oh-no-parent-control-migrate-state \
	$(PRODUCT_LIBDIR)/broker \
	$(PRODUCT_LIBDIR)/common \
	$(PRODUCT_LIBDIR)/child/extension \
	$(PRODUCT_LIBDIR)/kiosk \
	$(SYSTEMD_SYSTEM_DIR)/oh-no-parent-control-broker.service \
	$(SYSTEMD_USER_DIR)/oh-no-parent-control-app.service \
	$(SYSTEMD_USER_DIR)/oh-no-parent-control-polkit-agent.service \
	$(SYSTEMD_USER_DIR)/gnome-session@oh-no-parent-control.target.d/session.conf \
	$(DATADIR)/dbus-1/system-services/com.puffyslippers.OhNoParentControl1.service \
	$(DATADIR)/dbus-1/interfaces/com.puffyslippers.OhNoParentControl1.xml \
	$(DATADIR)/dbus-1/system.d/com.puffyslippers.OhNoParentControl1.conf \
	$(SYSCONFDIR)/fapolicyd/rules.d/99-oh-no-parent-control-allow.rules \
	$(DATADIR)/gnome-session/sessions/oh-no-parent-control.session \
	$(DATADIR)/wayland-sessions/oh-no-parent-control.desktop \
	$(DATADIR)/icons/hicolor/512x512/apps/com.puffyslippers.OhNoParentControl.png \
	$(DATADIR)/pam-configs/oh-no-parent-control-session-limits \
	$(DATADIR)/pam-configs/oh-no-parent-control-kiosk-only \
	$(SYSCONFDIR)/polkit-1/rules.d/00-oh-no-parent-control-session.rules \
	/etc/gdm3/PreSession/Default
UUID := oh-no-parent-control@tech.puffyslippers.com
CHILD_DIR := child
EXTENSION_SOURCES := aboutDialog.js appFilterClient.js appPolicyStore.js approverClient.js branding.js logger.js parentalApproval.js previewMode.js remainingTimeIndicator.js requestDialog.js requestOptions.js requestPreferencesStore.js sessionLimitsClient.js sharedPreferencesClient.js timeCalculationClient.js timerQuery.js
EXTENSION_ASSETS := request-options.json
BRANDING_ASSETS := data/brand.json data/app.json data/app_logo.png data/company_logo.png
EXTENSION_PACK_ASSETS := $(BRANDING_ASSETS) LICENSE
EXTENSION_BASE ?= $(HOME)/.local/share
EXTENSION_DIR := $(EXTENSION_BASE)/gnome-shell/extensions/$(UUID)

.PHONY: check _install-product-files _generate-package-activation-manifest uninstall pack-extension install-extension preview-kiosk preview-parent preview-child

check:
	@bash -n install.sh
	@for file in extension.js $(filter %.js,$(EXTENSION_SOURCES)); do node --check "$(CHILD_DIR)/$$file"; done
	@PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=broker:kiosk $(PYTHON) -m unittest discover -s tests/unit -v
	@$(PYTHON) -c 'import ast,pathlib; [ast.parse(p.read_text(), filename=str(p)) for p in pathlib.Path(".").glob("**/*.py") if ".git" not in p.parts]'
	@$(PYTHON) -c 'import pathlib,xml.etree.ElementTree as E; [E.parse(p) for p in pathlib.Path("data").glob("**/*.xml")]; [E.parse(p) for p in pathlib.Path(".").glob("**/*.policy")]'
	@$(PYTHON) -c 'import xml.etree.ElementTree as E; r=E.parse("child/policy/org.gnome.shell.extensions.oh-no-parent-control.policy").getroot(); a=r.find("./action[@id=\"org.gnome.shell.extensions.oh-no-parent-control.ApproveTimeAndApps\"]"); assert a is not None; i=a.find("./annotate[@key=\"org.freedesktop.policykit.imply\"]").text.split(); assert i == ["com.endlessm.ParentalControls.SessionLimits.ChangeOwn", "com.endlessm.ParentalControls.AppFilter.ChangeOwn"]'
	@! grep -REn 'resource:///org/gnome/shell|AuthPrompt|UnlockDialog|Main\.screenShield|_estimatedTimes' kiosk broker data config tools README.md

preview-kiosk:
	# The preview watches kiosk assets and source files; no manual relaunch is needed.
	PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=kiosk $(PYTHON) -m oh_no_parent_control_kiosk.main --preview

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
	install -m 0644 $(addprefix $(CHILD_DIR)/,metadata.json stylesheet.css extension.js $(EXTENSION_SOURCES) $(EXTENSION_ASSETS)) "$(EXTENSION_DIR)/"
	install -m 0644 $(BRANDING_ASSETS) LICENSE "$(EXTENSION_DIR)/"
	@echo "Installed $(UUID) to $(EXTENSION_DIR)"

# Internal target used by install.sh. Keep privileged host orchestration in the
# shell installer and declarative product-file installation in the Makefile.
_install-product-files:
	install -d "$(DESTDIR)$(PREFIX)/bin" "$(DESTDIR)$(LIBEXECDIR)"
	install -m 0755 kiosk/oh-no-parent-control "$(DESTDIR)$(PREFIX)/bin/"
	install -m 0755 parent/oh-no-parent-control-parent "$(DESTDIR)$(PREFIX)/bin/"
	install -m 0755 broker/oh-no-parent-control-broker "$(DESTDIR)$(LIBEXECDIR)/"
	install -m 0755 broker/oh-no-parent-control-migrate-state "$(DESTDIR)$(LIBEXECDIR)/"
	install -m 0755 broker/oh-no-parent-control-query-usage "$(DESTDIR)$(LIBEXECDIR)/"
	install -m 0755 tools/preserve_extension_state.py "$(DESTDIR)$(LIBEXECDIR)/oh-no-parent-control-preserve-extension-state"
	install -m 0755 tools/session_limit_check.py "$(DESTDIR)$(LIBEXECDIR)/oh-no-parent-control-session-limit-check"
	install -m 0755 tools/package_activation.py "$(DESTDIR)$(LIBEXECDIR)/oh-no-parent-control-package-activation"
	install -d "$(DESTDIR)$(PRODUCT_LIBDIR)/kiosk/oh_no_parent_control_kiosk" "$(DESTDIR)$(PRODUCT_LIBDIR)/broker/oh_no_parent_control" "$(DESTDIR)$(PRODUCT_LIBDIR)/common/oh_no_parent_control_ui"
	install -m 0644 common/__init__.py "$(DESTDIR)$(PRODUCT_LIBDIR)/common/"
	install -m 0644 common/oh_no_parent_control_ui/*.py "$(DESTDIR)$(PRODUCT_LIBDIR)/common/oh_no_parent_control_ui/"
	install -m 0644 kiosk/oh_no_parent_control_kiosk/*.py kiosk/oh_no_parent_control_kiosk/style.css kiosk/oh_no_parent_control_kiosk/kiosk-background.jpeg data/Gearbox_Waltz.mp3 child/request-options.json "$(DESTDIR)$(PRODUCT_LIBDIR)/kiosk/oh_no_parent_control_kiosk/"
	install -d "$(DESTDIR)$(PRODUCT_LIBDIR)/parent/oh_no_parent_control_parent" "$(DESTDIR)$(PRODUCT_LIBDIR)/child/extension"
	install -m 0644 parent/oh_no_parent_control_parent/*.py parent/oh_no_parent_control_parent/style.css "$(DESTDIR)$(PRODUCT_LIBDIR)/parent/oh_no_parent_control_parent/"
	install -m 0644 $(addprefix $(CHILD_DIR)/,metadata.json stylesheet.css extension.js $(EXTENSION_SOURCES) $(EXTENSION_ASSETS)) "$(DESTDIR)$(PRODUCT_LIBDIR)/child/extension/"
	install -m 0644 $(BRANDING_ASSETS) LICENSE "$(DESTDIR)$(PRODUCT_LIBDIR)/child/extension/"
	install -m 0644 broker/oh_no_parent_control/*.py "$(DESTDIR)$(PRODUCT_LIBDIR)/broker/oh_no_parent_control/"
	install -d "$(DESTDIR)$(DATADIR)/dbus-1/system-services" "$(DESTDIR)$(DATADIR)/dbus-1/interfaces"
	install -m 0644 data/dbus-1/system-services/com.puffyslippers.OhNoParentControl1.service "$(DESTDIR)$(DATADIR)/dbus-1/system-services/"
	install -m 0644 data/dbus-1/com.puffyslippers.OhNoParentControl1.xml "$(DESTDIR)$(DATADIR)/dbus-1/interfaces/"
	install -d "$(DESTDIR)$(DATADIR)/polkit-1/actions" "$(DESTDIR)$(SYSTEMD_SYSTEM_DIR)"
	# The in-session extension authenticates this meta-action once; its implied
	# permissions cover both the ActiveExtension and AppFilter writes.
	install -m 0644 child/policy/org.gnome.shell.extensions.oh-no-parent-control.policy "$(DESTDIR)$(DATADIR)/polkit-1/actions/"
	$(PYTHON) tools/render_polkit_policy.py --template data/polkit-1/actions/tech.puffyslippers.com.ohnoparentcontrol.kiosk.request-access.policy.in --branding data/brand.json --output "$(DESTDIR)$(DATADIR)/polkit-1/actions/tech.puffyslippers.com.ohnoparentcontrol.kiosk.request-access.policy"
	install -d "$(DESTDIR)$(SYSCONFDIR)/polkit-1/rules.d"
	install -m 0644 data/polkit-1/rules.d/00-oh-no-parent-control-session.rules "$(DESTDIR)$(SYSCONFDIR)/polkit-1/rules.d/"
	install -d "$(DESTDIR)$(SYSCONFDIR)/fapolicyd/rules.d"
	install -m 0644 data/fapolicyd/99-oh-no-parent-control-allow.rules "$(DESTDIR)$(SYSCONFDIR)/fapolicyd/rules.d/"
	install -m 0644 data/systemd/oh-no-parent-control-broker.service "$(DESTDIR)$(SYSTEMD_SYSTEM_DIR)/"
	install -m 0644 data/systemd/oh-no-parent-control-restore-extension-state.service "$(DESTDIR)$(SYSTEMD_SYSTEM_DIR)/"
	install -d "$(DESTDIR)$(SYSTEMD_USER_DIR)/gnome-session@oh-no-parent-control.target.d"
	install -m 0644 data/systemd/user/oh-no-parent-control-*.service "$(DESTDIR)$(SYSTEMD_USER_DIR)/"
	install -m 0644 data/systemd/user/gnome-session@oh-no-parent-control.target.d/session.conf "$(DESTDIR)$(SYSTEMD_USER_DIR)/gnome-session@oh-no-parent-control.target.d/"
	install -d "$(DESTDIR)$(DATADIR)/gnome-session/sessions" "$(DESTDIR)$(DATADIR)/wayland-sessions" "$(DESTDIR)$(DATADIR)/applications" "$(DESTDIR)$(DATADIR)/icons/hicolor/512x512/apps"
	install -m 0644 data/gnome-session/sessions/oh-no-parent-control.session "$(DESTDIR)$(DATADIR)/gnome-session/sessions/"
	install -m 0644 data/wayland-sessions/oh-no-parent-control.desktop "$(DESTDIR)$(DATADIR)/wayland-sessions/"
	install -m 0644 data/app_logo.png "$(DESTDIR)$(DATADIR)/icons/hicolor/512x512/apps/com.puffyslippers.OhNoParentControl.png"
	install -m 0644 data/applications/com.puffyslippers.OhNoParentControl.desktop "$(DESTDIR)$(DATADIR)/applications/"
	# GNOME only indexes desktop entries the signed-in user can read.  The
	# installer/package assigns this file to Ubuntu's administrator group.
	install -m 0640 data/applications/com.puffyslippers.OhNoParentControl.Parent.desktop "$(DESTDIR)$(DATADIR)/applications/"
	install -d "$(DESTDIR)$(DATADIR)/oh-no-parent-control" "$(DESTDIR)$(DATADIR)/doc/oh-no-parent-control"
	install -m 0644 config/config.example.json $(BRANDING_ASSETS) LICENSE "$(DESTDIR)$(DATADIR)/oh-no-parent-control/"
	install -m 0644 data/dbus-1/system.d/com.puffyslippers.OhNoParentControl1.conf.in "$(DESTDIR)$(DATADIR)/oh-no-parent-control/"
	install -m 0755 tools/provision.py "$(DESTDIR)$(LIBEXECDIR)/oh-no-parent-control-provision"
	install -m 0644 README.md LICENSE docs/System-Design.md docs/Package-Update.md docs/Data-Migration.md "$(DESTDIR)$(DATADIR)/doc/oh-no-parent-control/"
ifneq ($(GENERATE_ACTIVATION_MANIFEST),0)
	$(MAKE) --no-print-directory _generate-package-activation-manifest DESTDIR="$(DESTDIR)" PREFIX="$(PREFIX)" SYSCONFDIR="$(SYSCONFDIR)" LIBEXECDIR="$(LIBEXECDIR)" DATADIR="$(DATADIR)" SYSTEMD_SYSTEM_DIR="$(SYSTEMD_SYSTEM_DIR)" SYSTEMD_USER_DIR="$(SYSTEMD_USER_DIR)" PRODUCT_LIBDIR="$(PRODUCT_LIBDIR)"
endif

_generate-package-activation-manifest:
	$(PYTHON) tools/package_activation.py generate --root "$(if $(strip $(DESTDIR)),$(DESTDIR),/)" --output "$(DESTDIR)$(DATADIR)/oh-no-parent-control/package-activation.json" $(foreach path,$(ACTIVATION_MANIFEST_PATHS),--include "$(patsubst /%,%,$(path))")

uninstall:
	rm -f "$(DESTDIR)$(PREFIX)/bin/oh-no-parent-control" "$(DESTDIR)$(PREFIX)/bin/oh-no-parent-control-parent" "$(DESTDIR)$(LIBEXECDIR)/oh-no-parent-control-broker" "$(DESTDIR)$(LIBEXECDIR)/oh-no-parent-control-migrate-state" "$(DESTDIR)$(LIBEXECDIR)/oh-no-parent-control-query-usage" "$(DESTDIR)$(LIBEXECDIR)/oh-no-parent-control-provision" "$(DESTDIR)$(LIBEXECDIR)/oh-no-parent-control-preserve-extension-state" "$(DESTDIR)$(LIBEXECDIR)/oh-no-parent-control-session-limit-check" "$(DESTDIR)$(LIBEXECDIR)/oh-no-parent-control-package-activation"
	rm -f "$(DESTDIR)$(DATADIR)/dbus-1/system-services/com.puffyslippers.OhNoParentControl1.service" "$(DESTDIR)$(DATADIR)/dbus-1/interfaces/com.puffyslippers.OhNoParentControl1.xml" "$(DESTDIR)$(DATADIR)/dbus-1/system.d/com.puffyslippers.OhNoParentControl1.conf"
	rm -f "$(DESTDIR)$(DATADIR)/polkit-1/actions/org.gnome.shell.extensions.oh-no-parent-control.policy" "$(DESTDIR)$(DATADIR)/polkit-1/actions/tech.puffyslippers.com.ohnoparentcontrol.kiosk.request-access.policy" "$(DESTDIR)$(SYSTEMD_SYSTEM_DIR)/oh-no-parent-control-broker.service" "$(DESTDIR)$(SYSTEMD_SYSTEM_DIR)/oh-no-parent-control-restore-extension-state.service"
	rm -f "$(DESTDIR)$(SYSCONFDIR)/polkit-1/rules.d/00-oh-no-parent-control-session.rules"
	rm -f "$(DESTDIR)$(SYSCONFDIR)/fapolicyd/rules.d/89-oh-no-parent-control.rules" "$(DESTDIR)$(SYSCONFDIR)/fapolicyd/rules.d/99-oh-no-parent-control-allow.rules"
	rm -f "$(DESTDIR)$(SYSTEMD_USER_DIR)/oh-no-parent-control-app.service" "$(DESTDIR)$(SYSTEMD_USER_DIR)/oh-no-parent-control-polkit-agent.service" "$(DESTDIR)$(SYSTEMD_USER_DIR)/gnome-session@oh-no-parent-control.target.d/session.conf"
	rm -f "$(DESTDIR)$(DATADIR)/gnome-session/sessions/oh-no-parent-control.session" "$(DESTDIR)$(DATADIR)/wayland-sessions/oh-no-parent-control.desktop" "$(DESTDIR)$(DATADIR)/icons/hicolor/512x512/apps/com.puffyslippers.OhNoParentControl.png" "$(DESTDIR)$(DATADIR)/applications/com.puffyslippers.OhNoParentControl.desktop" "$(DESTDIR)$(DATADIR)/applications/com.puffyslippers.OhNoParentControl.Parent.desktop"
	rm -f "$(DESTDIR)$(DATADIR)/oh-no-parent-control/config.example.json" "$(DESTDIR)$(DATADIR)/oh-no-parent-control/brand.json" "$(DESTDIR)$(DATADIR)/oh-no-parent-control/app.json" "$(DESTDIR)$(DATADIR)/oh-no-parent-control/app_logo.png" "$(DESTDIR)$(DATADIR)/oh-no-parent-control/company_logo.png" "$(DESTDIR)$(DATADIR)/oh-no-parent-control/LICENSE" "$(DESTDIR)$(DATADIR)/oh-no-parent-control/com.puffyslippers.OhNoParentControl1.conf.in" "$(DESTDIR)$(DATADIR)/oh-no-parent-control/package-activation.json"
	rm -f "$(DESTDIR)$(DATADIR)/doc/oh-no-parent-control/README.md" "$(DESTDIR)$(DATADIR)/doc/oh-no-parent-control/LICENSE" "$(DESTDIR)$(DATADIR)/doc/oh-no-parent-control/System-Design.md" "$(DESTDIR)$(DATADIR)/doc/oh-no-parent-control/Package-Update.md" "$(DESTDIR)$(DATADIR)/doc/oh-no-parent-control/Data-Migration.md"
	rm -f "$(DESTDIR)$(SYSCONFDIR)/oh-no-parent-control/config.json"
	rm -f "$(DESTDIR)$(PRODUCT_LIBDIR)/kiosk/oh_no_parent_control_kiosk/"*.py "$(DESTDIR)$(PRODUCT_LIBDIR)/kiosk/oh_no_parent_control_kiosk/style.css" "$(DESTDIR)$(PRODUCT_LIBDIR)/kiosk/oh_no_parent_control_kiosk/kiosk-background.jpeg" "$(DESTDIR)$(PRODUCT_LIBDIR)/kiosk/oh_no_parent_control_kiosk/Gearbox_Waltz.mp3" "$(DESTDIR)$(PRODUCT_LIBDIR)/kiosk/oh_no_parent_control_kiosk/request-options.json" "$(DESTDIR)$(PRODUCT_LIBDIR)/broker/oh_no_parent_control/"*.py
	rm -f "$(DESTDIR)$(PRODUCT_LIBDIR)/common/__init__.py" "$(DESTDIR)$(PRODUCT_LIBDIR)/common/oh_no_parent_control_ui/"*.py "$(DESTDIR)$(PRODUCT_LIBDIR)/parent/oh_no_parent_control_parent/"*.py "$(DESTDIR)$(PRODUCT_LIBDIR)/parent/oh_no_parent_control_parent/style.css" "$(DESTDIR)$(PRODUCT_LIBDIR)/child/extension/"*.js "$(DESTDIR)$(PRODUCT_LIBDIR)/child/extension/"*.json "$(DESTDIR)$(PRODUCT_LIBDIR)/child/extension/stylesheet.css" "$(DESTDIR)$(PRODUCT_LIBDIR)/child/extension/app_logo.png" "$(DESTDIR)$(PRODUCT_LIBDIR)/child/extension/company_logo.png" "$(DESTDIR)$(PRODUCT_LIBDIR)/child/extension/LICENSE"
	@echo 'Product files removed. Accounts and managed-account policies were not changed.'
