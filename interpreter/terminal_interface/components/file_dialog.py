"""Simple class and method to launch the users system filedialog """

from PyQt5.QtWidgets import QApplication, QFileDialog, QMessageBox

class FileDialog:
    def get_path(self, type=None):
        """
        Open a file dialog and return the selected file or folder path.
        
        :param type: str, optional (default=None)
            Specifies the type of path to select ("file", "folder", or None).
            If None, the user will be asked whether to select a file or a folder.
        :return: str
            The path selected by the user. If the user cancels the operation, it returns None.
        """
        app = QApplication.instance()
        if app is None:
            app = QApplication([])

        options = QFileDialog.Options()
        options |= QFileDialog.ReadOnly

        if type is None:
            msg_box = QMessageBox()
            msg_box.setWindowTitle("Choose Action")
            msg_box.setText("Do you want to select a file or a folder?")
            btn_file = msg_box.addButton("File", QMessageBox.YesRole)
            btn_folder = msg_box.addButton("Folder", QMessageBox.NoRole)
            msg_box.addButton(QMessageBox.Cancel)
            user_choice = msg_box.exec_()

            if user_choice == QMessageBox.Cancel:
                return None
            type = "file" if msg_box.clickedButton() == btn_file else "folder"

        if type == "file":
            path, _ = QFileDialog.getOpenFileName(None, "Open File", "",
                                                  "All Files (*)", options=options)
        elif type == "folder":
            path = QFileDialog.getExistingDirectory(None, "Open Folder",
                                                    "", options=options)
        else:
            path = self.get_path(type=None) # this or val err, may aswell explicitly pass none.

        return path


