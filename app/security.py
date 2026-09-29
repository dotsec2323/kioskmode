"""
security.py
------------
Shared password-gate mechanism used by both the Diagnostics page (see
diagnostics_tab.py) and the Live Camera kiosk-mode exit prompt (see
camera_tab.py) -- both are gated by the same password, per spec.

This is separate from, and does not change, the Hardware Configuration
page's existing admin login (username/password root/3322, in
hardware_config_tab.py / config.py) -- that is a different, unrelated
credential for a different page.

HONEST LIMITS -- READ BEFORE RELYING ON THIS:
The password is never stored as a literal plaintext string here -- only
its SHA-256 hash is compared against, which is what was asked for
("don't store it in plain text if a safer option is available"). Be
realistic about what this actually buys you: for an open Python source
distribution (or even a PyInstaller .exe, which is straightforward to
inspect/decompile), hashing a 4-digit PIN is a mild speed bump, not real
security -- anyone who gets the hash can brute-force all 10,000 possible
4-digit PINs offline in well under a second. This raises the bar above
"the password is sitting right there as a string literal" (stops a casual
glance at the source from revealing it directly), but it is NOT a
substitute for real secrets management if this ever needs to gate
something more sensitive than "keep casual operators out of a
diagnostics page or fullscreen mode."
"""
import hashlib

from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton

# SHA-256 hash of the shared protected-access password -- used by both the
# Diagnostics page gate and the Live Camera kiosk-mode exit prompt (per
# spec: same password, both places). The plaintext value is intentionally
# not present anywhere in this file or its comments.
_PROTECTED_PASSWORD_HASH = "c6f5c46f9e3daea6422f8a004682a5de6f6946a9cfb7c9ca71912c029a981403"


def check_protected_password(candidate: str) -> bool:
    return hashlib.sha256((candidate or "").encode("utf-8")).hexdigest() == _PROTECTED_PASSWORD_HASH


class PasswordPromptDialog(QDialog):
    """
    Small modal password prompt. Use PasswordPromptDialog.prompt(...) --
    it returns True only if the password entered was correct AND the
    dialog was submitted (not cancelled/closed).

    Cancelling or closing THIS dialog (including pressing Escape while
    it's open) simply closes the prompt with no effect -- it does NOT by
    itself unlock kiosk mode or grant diagnostics access. Only a verified
    correct password does that, checked by the caller via the return
    value of prompt().
    """
    def __init__(self, title, message, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self._ok = False

        root = QVBoxLayout(self)
        lbl = QLabel(message)
        lbl.setWordWrap(True)
        root.addWidget(lbl)

        row = QHBoxLayout()
        row.addWidget(QLabel("Password:"))
        self.pw_edit = QLineEdit()
        self.pw_edit.setEchoMode(QLineEdit.Password)
        self.pw_edit.returnPressed.connect(self._try_accept)
        row.addWidget(self.pw_edit)
        root.addLayout(row)

        self.lbl_error = QLabel("")
        self.lbl_error.setStyleSheet("color:#c62828; font-weight:600;")
        root.addWidget(self.lbl_error)

        btn_row = QHBoxLayout()
        self.btn_ok = QPushButton("Submit")
        self.btn_ok.clicked.connect(self._try_accept)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_ok)
        btn_row.addWidget(self.btn_cancel)
        root.addLayout(btn_row)

        self.pw_edit.setFocus()

    def _try_accept(self):
        if check_protected_password(self.pw_edit.text()):
            self._ok = True
            self.accept()
        else:
            self.lbl_error.setText("Incorrect password.")
            self.pw_edit.clear()
            self.pw_edit.setFocus()

    @staticmethod
    def prompt(parent, title="Password Required", message="Enter the password to continue."):
        dlg = PasswordPromptDialog(title, message, parent=parent)
        result = dlg.exec_()
        return result == QDialog.Accepted and dlg._ok
