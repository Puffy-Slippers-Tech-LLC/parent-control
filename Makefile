UUID := oh-no-parent-control@example.com
SOURCES := appCatalog.js appFilterClient.js appPolicyStore.js approvedGrantStore.js customDurationStore.js malcontentClient.js parentalApproval.js parentalControlsIntegration.js remainingTimeIndicator.js requestDialog.js sessionLimitsClient.js timerQuery.js
# Shell extensions belong to the host user's data directory. In particular,
# terminals launched by a confined IDE can export a sandbox-specific
# XDG_DATA_HOME which GNOME Shell never searches.
EXTENSION_BASE ?= $(HOME)/.local/share
EXTENSION_DIR := $(EXTENSION_BASE)/gnome-shell/extensions/$(UUID)
RUNTIME_FILES := metadata.json stylesheet.css prefs.css extension.js prefs.js $(SOURCES)
POLICY_FILE := policy/org.gnome.shell.extensions.oh-no-parent-control.policy
POLKIT_ACTION_DIR ?= /usr/share/polkit-1/actions

.PHONY: pack check install install-policy

pack:
	gnome-extensions pack . --force --out-dir=. --extra-source=prefs.css $(SOURCES:%=--extra-source=%)

check:
	@for file in extension.js prefs.js $(SOURCES); do node --check "$$file"; done

install:
	install -d "$(EXTENSION_DIR)"
	install -m 0644 $(RUNTIME_FILES) "$(EXTENSION_DIR)/"
	@echo "Installed $(UUID) to $(EXTENSION_DIR)"
	@echo "Enable it with: gnome-extensions enable $(UUID)"

install-policy:
	install -d "$(DESTDIR)$(POLKIT_ACTION_DIR)"
	install -m 0644 $(POLICY_FILE) "$(DESTDIR)$(POLKIT_ACTION_DIR)/"
	@echo "Installed polkit policy to $(DESTDIR)$(POLKIT_ACTION_DIR)"
