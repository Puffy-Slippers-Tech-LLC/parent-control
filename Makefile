PYTHON ?= /usr/bin/python3
PREFIX ?= /usr
SYSCONFDIR ?= /etc
LIBEXECDIR ?= $(PREFIX)/libexec
DATADIR ?= $(PREFIX)/share
SYSTEMD_SYSTEM_DIR ?= $(PREFIX)/lib/systemd/system
SYSTEMD_USER_DIR ?= $(PREFIX)/lib/systemd/user
PRODUCT_LIBDIR ?= $(PREFIX)/lib/oh-no-parent-control
KIOSK_CONFINEMENT_VERIFIED ?= 0
UUID := oh-no-parent-control@tech.puffyslippers.com
EXTENSION_SOURCES := appCatalog.js appFilterClient.js appPolicyStore.js approvedGrantStore.js malcontentClient.js parentalApproval.js parentalControlsIntegration.js remainingTimeIndicator.js requestDialog.js requestPreferencesStore.js sessionLimitsClient.js timerQuery.js
EXTENSION_BASE ?= $(HOME)/.local/share
EXTENSION_DIR := $(EXTENSION_BASE)/gnome-shell/extensions/$(UUID)

.PHONY: check install provision uninstall pack-extension install-extension install-extension-policy

check:
	@for file in extension.js prefs.js $(EXTENSION_SOURCES); do node --check "$$file"; done
	@PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=broker:app $(PYTHON) -m unittest discover -s tests/unit -v
	@$(PYTHON) -c 'import ast,pathlib; [ast.parse(p.read_text(), filename=str(p)) for p in pathlib.Path(".").glob("**/*.py") if ".git" not in p.parts]'
	@$(PYTHON) -c 'import pathlib,xml.etree.ElementTree as E; [E.parse(p) for p in pathlib.Path("data").glob("**/*.xml")]; E.parse("data/polkit-1/actions/com.puffyslippers.OhNoParentControl1.policy")'
	@! grep -REn 'resource:///org/gnome/shell|AuthPrompt|UnlockDialog|Main\.screenShield|_estimatedTimes' app broker data config tools README.md

pack-extension:
	gnome-extensions pack . --force --out-dir=. --extra-source=prefs.css $(EXTENSION_SOURCES:%=--extra-source=%)

install-extension:
	install -d "$(EXTENSION_DIR)"
	install -m 0644 metadata.json stylesheet.css prefs.css extension.js prefs.js $(EXTENSION_SOURCES) "$(EXTENSION_DIR)/"
	@echo "Installed $(UUID) to $(EXTENSION_DIR)"

install-extension-policy:
	install -d "$(DESTDIR)$(DATADIR)/polkit-1/actions"
	install -m 0644 policy/org.gnome.shell.extensions.oh-no-parent-control.policy "$(DESTDIR)$(DATADIR)/polkit-1/actions/"

install:
	install -d "$(DESTDIR)$(PREFIX)/bin" "$(DESTDIR)$(LIBEXECDIR)"
	install -m 0755 app/oh-no-parent-control "$(DESTDIR)$(PREFIX)/bin/"
	install -m 0755 broker/oh-no-parent-control-broker "$(DESTDIR)$(LIBEXECDIR)/"
	install -d "$(DESTDIR)$(PRODUCT_LIBDIR)/app/oh_no_parent_control_app" "$(DESTDIR)$(PRODUCT_LIBDIR)/broker/oh_no_parent_control"
	install -m 0644 app/oh_no_parent_control_app/*.py "$(DESTDIR)$(PRODUCT_LIBDIR)/app/oh_no_parent_control_app/"
	install -m 0644 broker/oh_no_parent_control/*.py "$(DESTDIR)$(PRODUCT_LIBDIR)/broker/oh_no_parent_control/"
	install -d "$(DESTDIR)$(DATADIR)/dbus-1/system-services" "$(DESTDIR)$(DATADIR)/dbus-1/interfaces"
	install -m 0644 data/dbus-1/system-services/com.puffyslippers.OhNoParentControl1.service "$(DESTDIR)$(DATADIR)/dbus-1/system-services/"
	install -m 0644 data/dbus-1/com.puffyslippers.OhNoParentControl1.xml "$(DESTDIR)$(DATADIR)/dbus-1/interfaces/"
	install -d "$(DESTDIR)$(DATADIR)/polkit-1/actions" "$(DESTDIR)$(SYSTEMD_SYSTEM_DIR)"
	install -m 0644 data/polkit-1/actions/com.puffyslippers.OhNoParentControl1.policy "$(DESTDIR)$(DATADIR)/polkit-1/actions/"
	install -m 0644 data/systemd/oh-no-parent-control-broker.service "$(DESTDIR)$(SYSTEMD_SYSTEM_DIR)/"
	install -d "$(DESTDIR)$(SYSTEMD_USER_DIR)/gnome-session@oh-no-parent-control.target.d"
	install -m 0644 data/systemd/user/oh-no-parent-control-*.service "$(DESTDIR)$(SYSTEMD_USER_DIR)/"
	install -m 0644 data/systemd/user/gnome-session@oh-no-parent-control.target.d/session.conf "$(DESTDIR)$(SYSTEMD_USER_DIR)/gnome-session@oh-no-parent-control.target.d/"
	install -d "$(DESTDIR)$(DATADIR)/gnome-session/sessions" "$(DESTDIR)$(DATADIR)/wayland-sessions" "$(DESTDIR)$(DATADIR)/applications"
	install -m 0644 data/gnome-session/sessions/oh-no-parent-control.session "$(DESTDIR)$(DATADIR)/gnome-session/sessions/"
	install -m 0644 data/wayland-sessions/oh-no-parent-control.desktop "$(DESTDIR)$(DATADIR)/wayland-sessions/"
	install -m 0644 data/applications/com.puffyslippers.OhNoParentControl.desktop "$(DESTDIR)$(DATADIR)/applications/"
	install -d "$(DESTDIR)$(DATADIR)/oh-no-parent-control" "$(DESTDIR)$(DATADIR)/doc/oh-no-parent-control"
	install -m 0644 config/config.example.json "$(DESTDIR)$(DATADIR)/oh-no-parent-control/"
	install -m 0644 data/dbus-1/system.d/com.puffyslippers.OhNoParentControl1.conf.in "$(DESTDIR)$(DATADIR)/oh-no-parent-control/"
	install -m 0755 tools/provision.py "$(DESTDIR)$(LIBEXECDIR)/oh-no-parent-control-provision"
	install -m 0644 README.md docs/Deployment.md docs/System-Design.md "$(DESTDIR)$(DATADIR)/doc/oh-no-parent-control/"

provision:
	@test -n "$(KIOSK_USER)" -a -n "$(CHILD_USER)" || { echo 'Set KIOSK_USER and CHILD_USER'; exit 2; }
	@test "$(KIOSK_CONFINEMENT_VERIFIED)" = 1 || { echo 'Complete the confinement gate, then set KIOSK_CONFINEMENT_VERIFIED=1'; exit 2; }
	"$(LIBEXECDIR)/oh-no-parent-control-provision" --kiosk-user "$(KIOSK_USER)" --child-user "$(CHILD_USER)" --confinement-verified

uninstall:
	rm -f "$(DESTDIR)$(PREFIX)/bin/oh-no-parent-control" "$(DESTDIR)$(LIBEXECDIR)/oh-no-parent-control-broker" "$(DESTDIR)$(LIBEXECDIR)/oh-no-parent-control-provision"
	rm -f "$(DESTDIR)$(DATADIR)/dbus-1/system-services/com.puffyslippers.OhNoParentControl1.service" "$(DESTDIR)$(DATADIR)/dbus-1/interfaces/com.puffyslippers.OhNoParentControl1.xml" "$(DESTDIR)$(DATADIR)/dbus-1/system.d/com.puffyslippers.OhNoParentControl1.conf"
	rm -f "$(DESTDIR)$(DATADIR)/polkit-1/actions/com.puffyslippers.OhNoParentControl1.policy" "$(DESTDIR)$(SYSTEMD_SYSTEM_DIR)/oh-no-parent-control-broker.service"
	rm -f "$(DESTDIR)$(SYSTEMD_USER_DIR)/oh-no-parent-control-app.service" "$(DESTDIR)$(SYSTEMD_USER_DIR)/oh-no-parent-control-polkit-agent.service" "$(DESTDIR)$(SYSTEMD_USER_DIR)/gnome-session@oh-no-parent-control.target.d/session.conf"
	rm -f "$(DESTDIR)$(DATADIR)/gnome-session/sessions/oh-no-parent-control.session" "$(DESTDIR)$(DATADIR)/wayland-sessions/oh-no-parent-control.desktop" "$(DESTDIR)$(DATADIR)/applications/com.puffyslippers.OhNoParentControl.desktop"
	rm -f "$(DESTDIR)$(DATADIR)/oh-no-parent-control/config.example.json" "$(DESTDIR)$(DATADIR)/oh-no-parent-control/com.puffyslippers.OhNoParentControl1.conf.in"
	rm -f "$(DESTDIR)$(DATADIR)/doc/oh-no-parent-control/README.md" "$(DESTDIR)$(DATADIR)/doc/oh-no-parent-control/Deployment.md" "$(DESTDIR)$(DATADIR)/doc/oh-no-parent-control/System-Design.md"
	rm -f "$(DESTDIR)$(SYSCONFDIR)/oh-no-parent-control/config.json"
	rm -f "$(DESTDIR)$(PRODUCT_LIBDIR)/app/oh_no_parent_control_app/"*.py "$(DESTDIR)$(PRODUCT_LIBDIR)/broker/oh_no_parent_control/"*.py
	@echo 'Product files removed. Accounts and child policy were not changed.'
