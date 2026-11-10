from PySide6.QtWidgets import QDialog, QFormLayout, QLabel, QLineEdit, QDialogButtonBox, QMessageBox


class ApiInventoryDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("API Inventory 불러오기")
        self.setMinimumWidth(440)
        form = QFormLayout(self)
        url = QLabel(settings.base_url)
        url.setWordWrap(True)
        form.addRow("서버", url)
        self.user_id = QLineEdit()
        self.user_id.setAccessibleName("API ID")
        self.password = QLineEdit()
        self.password.setAccessibleName("API 비밀번호")
        self.password.setEchoMode(QLineEdit.Password)
        form.addRow("ID", self.user_id)
        form.addRow("비밀번호", self.password)
        hint = QLabel("인증이 필요한 서버는 ID와 비밀번호를 입력하세요.\n공개 조회가 허용된 서버는 둘 다 비워두세요.\n자격 증명은 파일에 저장하지 않습니다.")
        hint.setWordWrap(True)
        form.addRow(hint)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("불러오기")
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def validate_and_accept(self):
        if bool(self.user_id.text().strip()) != bool(self.password.text()):
            QMessageBox.warning(self, "API 인증", "ID와 비밀번호를 모두 입력하거나 둘 다 비워두세요.")
            return
        self.accept()

    def take_credentials(self):
        result = self.user_id.text().strip(), self.password.text()
        self.user_id.clear()
        self.password.clear()
        return result
