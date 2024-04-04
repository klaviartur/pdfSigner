#!/usr/bin/env python3
import sys
import os
import random
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QLabel, QPushButton, QToolButton, QFileDialog, QScrollArea, QWidget, QSizePolicy, QMessageBox, QComboBox, QToolBar, QAction, QDialog, QCheckBox, QTableWidget, QTableWidgetItem, QStyle
from PyQt5.QtGui import QPixmap, QImage, QImageReader, QPainter, QCursor, QIcon
from PyQt5.QtCore import Qt, QByteArray, QBuffer, QRectF, QSize, pyqtSignal
import fitz
import platform
import locale
import subprocess
import copy
import time

class CustomToolBar(QToolBar):
    def contextMenuEvent(self, event):
        # Override the contextMenuEvent to prevent the default context menu
        pass

class WheellessScrollArea(QScrollArea):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def wheelEvent(self, event):
        # Do not scroll
        pass

class MouseDetectingQLabel(QLabel):
    mouseEntered = pyqtSignal()
    mouseLeft = pyqtSignal()

    def __init__(self, parent=None):
        super(MouseDetectingQLabel, self).__init__(parent)

    def enterEvent(self, event):
        self.mouseEntered.emit()

    def leaveEvent(self, event):
        self.mouseLeft.emit()

class ToggleableSplitComboBox(QComboBox):
    def __init__(self):
        super().__init__()
        self.is_main_icon_toggled = False

    def mousePressEvent(self, event):
        arrow_rect = self.style().subControlRect(QStyle.CC_ComboBox, self.lineEdit(), QStyle.SC_ComboBoxArrow, self)

        if event.button() == Qt.LeftButton:
            if self.rect().contains(event.pos()) and not arrow_rect.contains(event.pos()):
                # Clicked on the main icon
                self.is_main_icon_toggled = not self.is_main_icon_toggled
                print("Main icon toggled:", self.is_main_icon_toggled)
            else:
                # Clicked on the arrow or elsewhere
                super().mousePressEvent(event)

class ManageSignaturesDialog(QDialog):
    def __init__(self, parent, signatures, language, iconSize):
        super().__init__(parent)

        self.language = language
        self.iconSize = iconSize * 2
        self.setGeometry(100, 100, 1600, 1200)
        self.setWindowTitle('Signaturen verwalten' if self.language == 'de' else 'Manage Signatures')

        # Create a table to display existing signatures
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        #self.table.setHorizontalHeaderLabels(['Signature', 'Move Up', 'Move Down', 'Delete'])
        # Hide the column headers
        self.table.horizontalHeader().setVisible(False)
        self.table.setIconSize(self.iconSize)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        # Populate the table with existing signatures
        self.populate_table(signatures)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.table)

        save_button = QPushButton('Speichern' if self.language == 'de' else 'Save')
        save_button.clicked.connect(self.save_signatures)
        layout.addWidget(save_button)

        cancel_button = QPushButton('Abbrechen' if self.language == 'de' else 'Cancel')
        cancel_button.clicked.connect(self.reject)
        layout.addWidget(cancel_button)

        self.setLayout(layout)

        self.show()

        if self.table.rowCount() == 1:
            self.add_signatures()

    def populate_table(self, signatures):
        self.table.setRowCount(len(signatures) + 1)

        for index in range(len(signatures) + 1):
            if index < len(signatures):
                # Display pixmap and store the name
                self.setPreview(index, signatures[index][0], signatures[index][2])
            else:
                add_button = QPushButton(QIcon.fromTheme('list-add'), '')
                add_button.clicked.connect(self.add_signatures)
                self.table.setCellWidget(index, 0, add_button)

        self.setButtons()
        self.table.resizeColumnToContents(0)

    def setPreview(self, index, path, icon):
        item = QTableWidgetItem()
        item.setData(Qt.DecorationRole, icon)
        item.setData(Qt.UserRole, path)  # Store the path as user data
        self.table.setItem(index, 0, item)
        self.table.resizeRowToContents(index)

    def setButtons(self):
        for index in range(self.table.rowCount() - 1):
            # Button to move up
            if 0 < index < self.table.rowCount() - 1:
                move_up_button = QPushButton(QIcon.fromTheme('go-up'), '')
                #print(f'set up to {index}->{index - 1}')
                move_up_button.clicked.connect(lambda _, i=index: self.move_signature(i, i - 1))
                self.table.setCellWidget(index, 1, move_up_button)
            else:
                self.table.setCellWidget(index, 1, None)
            # Button to move down
            if index < self.table.rowCount() - 2:
                move_down_button = QPushButton(QIcon.fromTheme('go-down'), '')
                move_down_button.clicked.connect(lambda _, i=index: self.move_signature(i, i + 1))
                self.table.setCellWidget(index, 2, move_down_button)
            else:
                self.table.setCellWidget(index, 2, None)
            delete_button = QPushButton(QIcon.fromTheme('user-trash'), '')
            delete_button.clicked.connect(lambda _, row=index: self.delete_signature(row))
            self.table.setCellWidget(index, 3, delete_button)

    def get_signature_path(self, row):
        if 0 <= row < self.table.rowCount() - 1:
            item = self.table.item(row, 0)
            if item:
                # Retrieve the stored name from user data
                return item.data(Qt.UserRole)
        return None

    def move_signature(self, from_index, to_index):
        if 0 <= to_index < self.table.rowCount() - 1:
            #print(f'{from_index}->{to_index}')
            item_from = self.table.takeItem(from_index, 0)
            item_to = self.table.takeItem(to_index, 0)
            self.table.setItem(from_index, 0, item_to)
            self.table.setItem(to_index, 0, item_from)

    def delete_signature(self, index):
        if 0 <= index < self.table.rowCount():
            # Remove the row from the table
            self.table.removeRow(index)
            self.setButtons()

    def add_signatures(self):
        # Open a file dialog to choose new signature PNG files
        file_paths, _ = QFileDialog.getOpenFileNames(None,
                                              'Signatur-Datei(en) hinzufügen' if self.language == 'de' else 'Add signature file(s)',
                                              '',
                                              'PNG-Dateien (*.png)' if self.language == 'de' else 'PNG Files (*.png)',
                                              options=QFileDialog.Options() | QFileDialog.ReadOnly)

        if file_paths:
            for file_path in file_paths:
                if file_path in [self.get_signature_path(i) for i in range(self.table.rowCount() - 1)]:
                    error_msg = QMessageBox()
                    error_msg.setIcon(QMessageBox.Information)
                    error_msg.setWindowTitle('PDF Signer')
                    error_msg.setText('Signatur bereits vorhanden:' if self.language == 'de' else 'Signature already present:')
                    error_msg.setInformativeText(f'{file_path}')
                    error_msg.setStandardButtons(QMessageBox.Ok)
                    error_msg.exec_()
                    continue

                # Load the image with QImageReader to enable automatic alpha channel handling
                reader = QImageReader(file_path)
                reader.setAutoTransform(True)
                image = reader.read()

                signature_pixmap = QPixmap.fromImage(image)
                target_height = 20
                signature_scale_factor = target_height / signature_pixmap.height()

                preview_pixmap = QPixmap(signature_pixmap.width() + 100, signature_pixmap.height() + 100)
                preview_pixmap.fill(Qt.white)
                painter = QPainter(preview_pixmap)
                painter.drawPixmap(50, 50, signature_pixmap)
                painter.end()

                # Add the new signature to the table
                index = self.table.rowCount() - 1
                self.table.insertRow(index)

                # Display pixmap
                self.setPreview(index, file_path, QIcon(preview_pixmap))

                # Button to move up
                self.setButtons()

                # Adjust the row heights
                self.table.resizeRowToContents(index)
                self.table.resizeColumnToContents(0)

    def save_signatures(self):
        try:
            if platform.system() == 'Windows':
                signatures_list_file = os.path.expandvars('%APPDATA%\\pdfsigner\\signatures.ini')
            elif platform.system() == 'Linux':
                signatures_list_file = os.path.expanduser('~/.config/pdfsigner/signatures.conf')
            elif platform.system() == 'Darwin':  # MacOS
                signatures_list_file = os.path.expanduser('~/Library/Application Support/pdfsigner/signatures.conf')
            else:
                raise NotImplementedError('Betriebssystem nicht unterstützt' if self.language == 'de' else 'Unsupported operating system')

            os.makedirs(os.path.dirname(signatures_list_file), exist_ok=True)

            with open(signatures_list_file, 'w') as file:
                for index in range(self.table.rowCount() - 1):
                    file.write(f"{self.get_signature_path(index)}\n")
        except Exception as e:
            error_msg = QMessageBox()
            error_msg.setIcon(QMessageBox.Critical)
            error_msg.setWindowTitle('PDF Signer')
            error_msg.setText('Fehler' if self.language == 'de' else 'Error')
            error_msg.setInformativeText(f'Details: {str(e)}')
            error_msg.setStandardButtons(QMessageBox.Ok)
            error_msg.exec_()

        self.accept()


class SettingsDialog(QDialog):

    def __init__(self, settings_info, settings, locale, language):
        super().__init__()

        self.settings_info = settings_info
        self.settings = copy.copy(settings)
        self.locale = locale
        self.language = language

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # Create checkboxes based on loaded settings
        self.checkboxes = []
        for key, info in self.settings_info.items():
            checkbox = QCheckBox(key)
            checkbox.setChecked(self.settings[key])
            checkbox.stateChanged.connect(lambda state, key=key: self.update_setting(key, state))
            layout.addWidget(checkbox)
            self.checkboxes.append((key, checkbox))

        # Save and Cancel buttons
        self.save_button = QPushButton()
        self.save_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton()
        self.cancel_button.clicked.connect(self.reject)

        layout.addWidget(self.save_button)
        layout.addWidget(self.cancel_button)

        self.setLayout(layout)
        self.setTexts(self.language)


    def update_setting(self, key, state):
        self.settings[key] = state == 2  # Checked state is 2, unchecked state is 0
        if key == 'forceEnglish':
            self.language = self.locale if state == 0 else 'en'
            self.setTexts(self.language)

    def setTexts(self, language):
        for key, checkbox in self.checkboxes:
            checkbox.setText(self.settings_info[key][f'text_{language}'])
        self.save_button.setText('Speichern' if self.language == 'de' else 'Save')
        self.cancel_button.setText('Abbrechen' if self.language == 'de' else 'Cancel')
        self.setWindowTitle('Einstellungen' if language == 'de' else 'Settings')

class PDFSigner(QMainWindow):
    def __init__(self, pdf_path=None):
        super().__init__()

        self.pdf_path = pdf_path
        self.current_page = 0
        self.total_pages = 0
        self.pages = [] # [QPixmap, [(int sig_idx, float zoom, int x, int y)]]
        self.pdf_scale_factor = 1.0
        self.display_zoom_factor = 1.0
        self.signatures = [] # [(path, QPixmap, preview QIcon, scale_factor)]
        self.signature_zoom_factor = 1.0
        self.current_signature_index = -1
        self.signature_activated = False
        self.doc = None  # Store the loaded PDF document
        self.isSaved = True
        self.last_page_action_time = time.time()

        self.settings_info = self.load_settings_info()
        self.settings = self.load_settings()

        self.init_ui()
        self.load_pdf_document()  # Load the PDF document during initialization

    def init_ui(self):
         # Set up the main window
        self.setGeometry(100, 100, 1600, 1200)

        self.iconSize = QSize(20 * QApplication.font().pointSize(), 10 * QApplication.font().pointSize())
        self.setWindowIcon(QIcon.fromTheme('document-sign'))

        # Create a QToolBar
        toolbar = CustomToolBar(self)
        toolbar.setMovable(False)
        toolbar.setIconSize(self.iconSize)
        self.addToolBar(toolbar)

        # Add open button
        self.open_pdf_action = QAction(QIcon.fromTheme('document-open'), '', self)
        self.open_pdf_action.triggered.connect(self.open_pdf)
        self.open_pdf_button = QToolButton(self)
        self.open_pdf_button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.open_pdf_button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.open_pdf_button.setDefaultAction(self.open_pdf_action)
        toolbar.addWidget(self.open_pdf_button)

        # Add switch page buttons
        self.prev_page_action = QAction(QIcon.fromTheme('go-previous'), '', self)
        self.prev_page_action.triggered.connect(self.prev_page)
        self.prev_page_button = QToolButton(self)
        self.prev_page_button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.prev_page_button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.prev_page_button.setDefaultAction(self.prev_page_action)
        toolbar.addWidget(self.prev_page_button)

        self.next_page_action = QAction(QIcon.fromTheme('go-next'), '', self)
        self.next_page_action.triggered.connect(self.next_page)
        self.next_page_button = QToolButton(self)
        self.next_page_button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.next_page_button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.next_page_button.setDefaultAction(self.next_page_action)
        toolbar.addWidget(self.next_page_button)

        # Add spacer with separators
        toolbar.addSeparator()
        left_spacer_item = QWidget()
        left_spacer_item.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        toolbar.addWidget(left_spacer_item)
        toolbar.addSeparator()

        # Add place signature toggle button with signature selection combo box
        self.toggle_signature_action = QAction(QIcon.fromTheme('document-sign'), '', self)
        self.toggle_signature_action.setCheckable(True)
        self.toggle_signature_action.triggered.connect(self.toggle_signature)
        self.toggle_signature_button = QToolButton(self)
        self.toggle_signature_button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.toggle_signature_button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.toggle_signature_button.setCheckable(True)
        self.toggle_signature_button.setDefaultAction(self.toggle_signature_action)
        toolbar.addWidget(self.toggle_signature_button)

        self.signature_combo_box = QComboBox(self)
        self.signature_combo_box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.load_signatures()
        self.signature_combo_box.activated.connect(self.selectSignature)
        #self.signature_combo_box.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.signature_combo_box.setIconSize(self.iconSize)
        toolbar.addWidget(self.signature_combo_box)

        # Add spacer with separators
        toolbar.addSeparator()
        right_spacer_item = QWidget()
        right_spacer_item.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        toolbar.addWidget(right_spacer_item)
        toolbar.addSeparator()

        # Add save button
        self.save_pdf_action = QAction(QIcon.fromTheme('document-save'), '', self)
        self.save_pdf_action.triggered.connect(self.save_pdf)
        self.save_pdf_button = QToolButton(self)
        self.save_pdf_button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.save_pdf_button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.save_pdf_button.setDefaultAction(self.save_pdf_action)
        toolbar.addWidget(self.save_pdf_button)

        toolbar.addSeparator()

        # Add settings button
        self.settings_action = QAction(QIcon.fromTheme('configure'), '', self)
        self.settings_action.triggered.connect(self.change_settings)
        self.settings_button = QToolButton(self)
        self.settings_button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.settings_button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.settings_button.setDefaultAction(self.settings_action)
        toolbar.addWidget(self.settings_button)

        # Create widgets
        self.scroll_area = WheellessScrollArea()
        #self.scroll_area.setStyleSheet('background-color: lightgreen;')
        self.scroll_area.setAlignment(Qt.AlignCenter)
        self.scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

        self.pdf_label = MouseDetectingQLabel()
        self.pdf_label.setAlignment(Qt.AlignCenter)
        self.pdf_label.mouseEntered.connect(self.enter_pdf_label)
        self.pdf_label.mouseLeft.connect(self.leave_pdf_label)
        self.scroll_area.setWidget(self.pdf_label)

        self.setCentralWidget(self.scroll_area)

        self.setTexts()
        self.update_page_buttons()

        # Initial setup
        self.showMaximized()

    def setTexts(self):
        self.setWindowTitle('PDF Signieren' if self.language == 'de' else 'PDF Signer')
        self.open_pdf_action.setText('PDF Öffnen …' if self.language == 'de' else 'Open PDF …')
        self.prev_page_action.setText('Vorherige Seite' if self.language == 'de' else 'Previous page')
        self.next_page_action.setText('Nächste Seite' if self.language == 'de' else 'Next page')
        self.toggle_signature_action.setText('Signieren' if self.language == 'de' else 'Place signature')
        self.save_pdf_action.setText('Signierte PDF Speichern …' if self.language == 'de' else 'Save signed PDF …')
        self.settings_action.setText('Einstellungen …' if self.language == 'de' else 'Settings …')
        self.signature_combo_box.setItemText(self.signature_combo_box.count() - 1, 'Signaturen verwalten …' if self.language == 'de' else 'Manage signatures …')
        #self.setSignatureIcon()

    def load_settings_info(self):
        # Dictionary containing settings information
        return {
            'forceEnglish': {'value': False, 'text_de': 'Englisch erzwingen', 'text_en': 'Force English'},
            'autoNextSignature': {'value': True, 'text_de': 'Automatisch zur nächsten Signatur wechseln', 'text_en': 'Switch to next signature automatically'},
            'saveGray': {'value': True, 'text_de': 'In Graustufen speichern', 'text_en': 'Use greyscale when saving'},
            'saveSkewed': {'value': True, 'text_de': 'Leicht schief speichern', 'text_en': 'Skew slightly when saving'},
        }

    def load_settings(self):
        default_settings = {key: info['value'] for key, info in self.settings_info.items()}

        settings = default_settings.copy()

        if platform.system() == 'Windows':
            self.config_path = os.path.expandvars('%APPDATA%\\pdfsigner\\config.ini')
        elif platform.system() == 'Linux':
            self.config_path = os.path.expanduser('~/.config/pdfsigner/config.conf')

        try:
            with open(self.config_path, 'r') as file:
                for line in file:
                    key, value = line.strip().split('=')
                    if key in default_settings:
                        settings[key] = value.lower() == 'true'
        except FileNotFoundError:
            pass

        # Determine language
        self.locale, _ = locale.getdefaultlocale()
        self.locale = self.locale[:2]
        if self.locale == 'de' and not settings['forceEnglish']:
            self.language = 'de'
        else:
            self.language = 'en'

        return settings

    def save_settings(self):
        with open(self.config_path, 'w') as file:
            for key, value in self.settings.items():
                file.write(f'{key}={value}\n')

    def change_settings(self):
        #print(f'old language:\n{self.language}')
        # Create and show the settings dialog
        dialog = SettingsDialog(self.settings_info, self.settings, self.locale, self.language)
        #dialog.settings_changed.connect(self.update_settings)
        result = dialog.exec_()
        if result == QDialog.Accepted:
            self.settings = dialog.settings
            self.language = dialog.language
            self.setTexts()
            self.update_page_buttons()
            self.save_settings()

    def open_pdf(self, file_path=None):
        if not file_path:
            documents_path = os.path.join(os.path.expanduser('~'), 'Documents')
            file_path, _ = QFileDialog.getOpenFileName(self, 'PDF Öffnen' if self.language == 'de' else 'Open PDF', documents_path, 'PDF-Dateien (*.pdf)' if self.language == 'de' else 'PDF-Files (*.pdf)', options=QFileDialog.Options() | QFileDialog.ReadOnly)

        if file_path:
            self.pdf_path = file_path
            self.current_page = 0
            self.load_pdf_document()  # Load the PDF document when opening a new file

    def load_pdf_document(self):
        if self.pdf_path:
            try:
                self.doc = fitz.open(self.pdf_path)
            except Exception as e:
                error_msg = QMessageBox()
                error_msg.setIcon(QMessageBox.Critical)
                error_msg.setWindowTitle('Fehler' if self.language == 'de' else 'Error')
                error_msg.setText('Fehler beim Öffnen der PDF-Datei!' if self.language == 'de' else 'Could not open this pdf file!')
                error_msg.setInformativeText(f'Details: {str(e)}')
                error_msg.setStandardButtons(QMessageBox.Ok)
                error_msg.exec_()
                return

            self.total_pages = self.doc.page_count

            for page_number in range(self.total_pages):
                page = self.doc.load_page(page_number)
                pixmap = page.get_pixmap(matrix=fitz.Matrix(150/72.0, 150/72.0))  # Set DPI to 150
                image = QImage(pixmap.samples, pixmap.width, pixmap.height, pixmap.stride, QImage.Format_RGB888)
                qt_pixmap = QPixmap.fromImage(image)
                self.pages.append([qt_pixmap, []])

            self.update_pdf_display()
            self.update_page_buttons()
            #self.isSaved = False

    def update_pdf_display(self):
        if not self.doc:
            return

        pdf_pixmap = self.assemble_pixmap(self.pages[self.current_page], self.display_zoom_factor)
        self.pdf_label.setFixedSize(pdf_pixmap.width(), pdf_pixmap.height())
        self.pdf_label.setPixmap(pdf_pixmap)

    def resizeEvent(self, event):
        if hasattr(self, 'scroll_area'):
            self.update_pdf_display()
            self.draw_signature_cursor()

    def enter_pdf_label(self):
        if self.signature_activated:
            self.setCursor(self.signature_cursor)
            self.draw_signature_cursor()

    def leave_pdf_label(self):
        if self.signature_activated:
            self.unsetCursor()

    def wheelEvent(self, event):
        cursor_pos = event.pos()
        if event.angleDelta().y() != 0:
            #print('zooming…')
            self.zoomAroundCursor(event.angleDelta().y(), cursor_pos)
        if event.angleDelta().x() < -300 and self.scroll_area.horizontalScrollBar().value() == self.scroll_area.horizontalScrollBar().maximum():
            current_time = time.time() * 1000
            if current_time - self.last_page_action_time >= 250:
                self.next_page_action.trigger()
                self.last_page_action_time = current_time
        elif event.angleDelta().x() > 300 and self.scroll_area.horizontalScrollBar().value() == 0:
            current_time = time.time() * 1000
            if current_time - self.last_page_action_time >= 250:
                self.prev_page_action.trigger()
                self.last_page_action_time = current_time
        elif event.angleDelta().x() != 0:
            self.scroll_area.horizontalScrollBar().setValue(self.scroll_area.horizontalScrollBar().value() - event.angleDelta().x())

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.signature_activated and self.pdf_label.underMouse():
            # Calculate the position of the cursor in relation to the PDF pixmap
            cursor = self.pdf_label.mapFrom(self, event.pos())
            cursor /= self.pdf_scale_factor * self.display_zoom_factor  # Normalize
            self.pages[self.current_page][1].append((self.current_signature_index, self.signature_zoom_factor, cursor.x(), cursor.y()))
            self.toggle_signature()
            self.update_pdf_display()
            if self.settings['autoNextSignature']:
                self.selectSignature()
            self.isSaved = False
        elif event.button() == Qt.RightButton and self.pdf_label.underMouse():
            self.toggle_signature_action.trigger()

    def keyPressEvent(self, event):
        cursor_pos = QCursor.pos()
        cursor_pos = self.mapFromGlobal(cursor_pos)
        if event.key() == Qt.Key_Plus:
            self.zoomAroundCursor(-1, cursor_pos)
        elif event.key() == Qt.Key_Minus:
            self.zoomAroundCursor(1, cursor_pos)
        elif event.key() == Qt.Key_Escape and self.signature_activated:
            self.toggle_signature_action.trigger()
        # else:
        #     super().keyPressEvent(event)

    def zoomAroundCursor(self, delta, cursor_pos):
        if not self.signature_activated:
            if self.pdf_label.underMouse():
                # Calculate the position of the cursor in relation to the PDF pixmap
                pdf_cursor_pos_before_zoom = self.pdf_label.mapFrom(self, cursor_pos)
                pdf_cursor_pos_before_zoom /= self.display_zoom_factor  # Normalize

                # Zoom into/out of the PDF pixmap
                if delta < 0 and self.display_zoom_factor < 3.0:
                    self.display_zoom_factor = min(3.0, self.display_zoom_factor + 0.1)
                elif delta > 0 and self.display_zoom_factor > 1.0:
                    self.display_zoom_factor = max(1.0, self.display_zoom_factor - 0.1)

                # Update the PDF display
                self.update_pdf_display()

                # Calculate the new position of the cursor in relation to the PDF pixmap after zoom
                pdf_cursor_pos_after_zoom = self.pdf_label.mapFrom(self, cursor_pos)
                pdf_cursor_pos_after_zoom /= self.display_zoom_factor  # Normalize

                cursor_change = (pdf_cursor_pos_before_zoom - pdf_cursor_pos_after_zoom) * self.display_zoom_factor  # Normalize

                # Adjust the scroll position to keep the cursor position fixed
                self.scroll_area.horizontalScrollBar().setValue(self.scroll_area.horizontalScrollBar().value() + cursor_change.x())
                self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().value() + cursor_change.y())

        else:
            # change size of cursor-attached pixmap
            if delta < 0 and self.signature_zoom_factor < 5.0:
                self.signature_zoom_factor = min(5.0, self.signature_zoom_factor + 0.1)
            elif delta > 0 and self.signature_zoom_factor > 0.5:
                self.signature_zoom_factor = max(0.5, self.signature_zoom_factor - 0.1)
            self.draw_signature_cursor()

    def update_page_buttons(self):
        if self.total_pages>0:
            self.prev_page_button.setEnabled(self.current_page > 0)
            self.next_page_button.setEnabled(self.current_page < self.total_pages - 1)
            self.save_pdf_button.setEnabled(True)
        else:
            self.prev_page_button.setEnabled(False)
            self.next_page_button.setEnabled(False)
            self.save_pdf_button.setEnabled(False)

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.display_zoom_factor = 1.0
            self.update_pdf_display()
            self.update_page_buttons()

    def next_page(self):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.display_zoom_factor = 1.0
            self.update_pdf_display()
            self.update_page_buttons()

    def load_signatures(self):
        try:
            if platform.system() == 'Windows':
                signatures_list_file = os.path.expandvars('%APPDATA%\\pdfsigner\\signatures.ini')
            elif platform.system() == 'Linux':
                signatures_list_file = os.path.expanduser('~/.config/pdfsigner/signatures.conf')
            elif platform.system() == 'Darwin':  # MacOS
                signatures_list_file = os.path.expanduser('~/Library/Application Support/pdfsigner/signatures.conf')
            else:
                # Handle other platforms or raise an exception if not supported
                raise NotImplementedError('Betriebssystem nicht unterstützt' if self.language == 'de' else 'Unsupported operating system')
        except Exception as e:
            error_msg = QMessageBox()
            error_msg.setIcon(QMessageBox.Critical)
            error_msg.setWindowTitle('PDF Signer')
            error_msg.setText('Fehler' if self.language == 'de' else 'Error')
            error_msg.setInformativeText(f'Details: {str(e)}')
            error_msg.setStandardButtons(QMessageBox.Ok)
            error_msg.exec_()
            sys.exit(1)

        try:
            with open(signatures_list_file, 'r') as file:
                signature_path_list = [line.strip() for line in file]
        except Exception as e:
            signature_path_list = []

        #
        if self.signature_combo_box.count() > 0:
            # reset on reload after saving manage dialog
            self.signatures = []
            # save manage action item text
            manage_text = self.signature_combo_box.itemText(self.signature_combo_box.count() - 1)
            self.signature_combo_box.clear()
            self.current_signature_index = -1
        else:
            manage_text = ''

        for signature_path in signature_path_list:
            if os.path.exists(signature_path):
                # Load the image with QImageReader to enable automatic alpha channel handling
                reader = QImageReader(signature_path)
                if not reader.size().isValid():
                    continue
                reader.setAutoTransform(True)
                image = reader.read()

                signature_pixmap = QPixmap.fromImage(image)
                target_height = 20
                signature_scale_factor = target_height / signature_pixmap.height()

                preview_pixmap = QPixmap(signature_pixmap.width() + 100, signature_pixmap.height() + 100)
                preview_pixmap.fill(Qt.white)
                painter = QPainter(preview_pixmap)
                painter.drawPixmap(50, 50, signature_pixmap)
                painter.end()

                self.signatures.append((signature_path, signature_pixmap, QIcon(preview_pixmap), signature_scale_factor))
                self.signature_combo_box.addItem(QIcon(preview_pixmap), '')

        self.signature_combo_box.addItem(manage_text)
        self.selectSignature()

    def manage_signatures(self):
        dialog = ManageSignaturesDialog(self, self.signatures, self.language, self.iconSize)
        result = dialog.exec_()
        if result == QDialog.Accepted:
            self.load_signatures()

    def toggle_signature(self, force_activate = False):
        if self.signature_combo_box.count() == 1:
            self.manage_signatures()

        if self.doc and (not self.signature_activated or force_activate):
            #print('want to toggle on')
            if self.current_signature_index == -1:
                #print('no signature selected. trying to get one.')
                self.selectSignature()

            if self.current_signature_index > -1 and self.current_signature_index < self.signature_combo_box.count() - 1:
                #print(f'activating signature {self.current_signature_index}')
                self.signature_activated = True
                self.draw_signature_cursor()
                if not self.pdf_label.underMouse():
                    cursor = self.cursor()
                    cursor.setPos(self.scroll_area.mapToGlobal(self.scroll_area.rect().center()))
                    self.setCursor(cursor)
        else:
            #print('want to toggle off')
            self.signature_activated = False
            self.unsetCursor()
            #self.setSignatureIcon()
        self.toggle_signature_button.setChecked(self.signature_activated)

    def draw_signature_cursor(self):
        if self.signature_activated:
            _, signature_pixmap, _, signature_scale_factor = self.signatures[self.current_signature_index]
            scale_factor = signature_scale_factor * self.signature_zoom_factor * self.display_zoom_factor * self.pdf_scale_factor
            self.signature_cursor = QCursor(signature_pixmap.scaled(
                                        int(signature_pixmap.width() * scale_factor),
                                        int(signature_pixmap.height() * scale_factor),
                                        aspectRatioMode=Qt.KeepAspectRatio,
                                        transformMode=Qt.SmoothTransformation), 0, 0)
            self.setCursor(self.signature_cursor)

    def selectSignature(self, index = -1):
        #print(f'signature {index} requested')
        if index == self.signature_combo_box.count() - 1:
            #print('managing signatures')
            self.manage_signatures()
            self.signature_combo_box.setCurrentIndex(self.current_signature_index)
            return
        if index == -1 and self.signature_combo_box.count() > 1:
            #print('selecting next signature in line')
            #print(f'was {self.signature_combo_box.currentIndex()}')
            self.signature_combo_box.setCurrentIndex((self.current_signature_index + 1) % (self.signature_combo_box.count() - 1))
            #print(f'is {self.signature_combo_box.currentIndex()}')
        if self.signature_combo_box.currentIndex() < self.signature_combo_box.count() - 1:
            #print(f'saving index {self.signature_combo_box.currentIndex()}')
            self.current_signature_index = self.signature_combo_box.currentIndex()
        #self.setSignatureIcon()
        # if index > -1:
        #     print('trying to activate')
        #     self.toggle_signature(force_activate = True)

    # def setSignatureIcon(self):
    #     if self.current_signature_index > -1:
    #         #print(f'setting icon to {self.current_signature_index}')
    #         self.toggle_signature_button.setIcon(self.signature_combo_box.itemIcon(self.current_signature_index))
    #     else:
    #         self.toggle_signature_button.setIcon(self.toggle_signature_action.icon())

    def save_pdf(self, skip = False):
        if not self.doc:
            return

        # Save the modified PDF
        new_pdf_path = os.path.splitext(self.pdf_path)[0] + ('_signiert' if self.language == 'de' else '_signed') + '.pdf'

        choice = None
        tries = 0
        while os.path.exists(new_pdf_path) and choice != 0 and tries < 10:
            #print(f'{tries}: {new_pdf_path}, {choice}, {QMessageBox.Yes}')
            tries += 1
            if choice == None:
                msg_box = QMessageBox()
                msg_box.setIcon(QMessageBox.Question)
                msg_box.setText(f'Die Datei\n{new_pdf_path}\nexistiert bereits.\n\nÜberschreiben?' if self.language == 'de' else f'The file\n{new_pdf_path}\nalready exists.\n\nDo you want to overwrite it?')


                msg_box_yes_button = msg_box.addButton('Ja' if self.language == 'de' else 'Yes', QMessageBox.YesRole)
                msg_box_no_button = msg_box.addButton('Nein, Zahl anhängen' if self.language == 'de' else 'No, append number', QMessageBox.NoRole)
                msg_box.addButton('Abbrechen' if self.language == 'de' else 'Cancel', QMessageBox.RejectRole)

                msg_box.setDefaultButton(msg_box_no_button)

                choice = msg_box.exec_()
            if choice == 1:
                new_pdf_path = os.path.splitext(self.pdf_path)[0] + ('_signiert' if self.language == 'de' else '_signed') + f'{tries}' + '.pdf'
            elif choice == 2:
                return

        new_pdf_document = fitz.open()

        for page_number, page in enumerate(self.pages):

            pdf_pixmap = self.assemble_pixmap(page, 1.0, noScale = True)

            image = pdf_pixmap.toImage()
            if self.settings['saveGray']:
                image = image.convertToFormat(QImage.Format_Grayscale8)

            if self.settings['saveSkewed']:
                rotation_angle = random.uniform(0.1, 0.5)

                # Create a blank QImage with the same size as image
                rotated_image = QImage(image.size(), QImage.Format_RGB32)
                rotated_image.fill(Qt.white)

                # Perform the rotation using a QPainter
                painter = QPainter(rotated_image)
                painter.setRenderHint(QPainter.Antialiasing, False)  # Set anti-aliasing to False
                painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
                painter.translate(image.width() / 2, image.height() / 2)
                painter.rotate(rotation_angle)
                target_rect = QRectF(-image.width() / 2, -image.height() / 2, image.width(), image.height())
                painter.drawImage(target_rect, image)
                painter.end()
                image = rotated_image

            byte_array = QByteArray()
            buffer = QBuffer(byte_array)
            buffer.open(QBuffer.WriteOnly)
            image.save(buffer, 'PNG')

            # Get raw bytes from QByteArray
            byte_array = buffer.data()
            image_bytes = bytearray(byte_array.data())

            # Create a fitz.Pixmap from the bytes-like object
            fitz_pixmap = fitz.Pixmap(image_bytes)

            new_page = new_pdf_document.new_page(-1, self.doc[page_number].rect.width, self.doc[page_number].rect.height)

            new_page.insert_image(self.doc[page_number].rect, pixmap=fitz_pixmap)

        new_pdf_document.save(new_pdf_path)
        new_pdf_document.close()
        self.isSaved = True

        if not skip:
            options_box = QMessageBox()
            options_box.setWindowTitle('Was nun?' if self.language == 'de' else 'What next?')
            options_box.setText(('Signierte PDF gespeichert unter:'  if self.language == 'de' else 'Saved signed PDF as:') + f'\n{new_pdf_path}')
            options_box.setIcon(QMessageBox.Question)

            option_open_file_button = options_box.addButton('PDF anzeigen' if self.language == 'de' else 'Open PDF', QMessageBox.ActionRole)
            option_open_dir_button = options_box.addButton('Beinhaltendes Verzeichnis öffnen' if self.language == 'de' else 'Open containing directory', QMessageBox.ActionRole)
            option_quit_button = options_box.addButton('Schließen' if self.language == 'de' else 'Quit', QMessageBox.ActionRole)
            options_box.addButton('Abbrechen' if self.language == 'de' else 'Cancel', QMessageBox.RejectRole)

            options_box.exec_()

            if options_box.clickedButton() == option_open_file_button:
                try:
                    # Check the operating system and construct the appropriate command
                    if sys.platform == 'win32':
                        # On Windows, use the 'start' command
                        subprocess.Popen(['start', new_pdf_path], shell=True, close_fds=True, creationflags=subprocess.DETACHED_PROCESS)
                    elif sys.platform == 'darwin':
                        # On macOS, use the 'open' command
                        subprocess.Popen(['open', new_pdf_path], close_fds=True)
                    elif sys.platform.startswith('linux'):
                        # On Linux, use the 'xdg-open' command
                        subprocess.Popen(['xdg-open', new_pdf_path], close_fds=True)
                    else:
                        raise NotImplementedError('Betriebssystem nict unterstützt' if self.language == 'de' else 'Unsupported operating system')
                except Exception as e:
                    error_msg = QMessageBox()
                    error_msg.setIcon(QMessageBox.Critical)
                    error_msg.setWindowTitle('Fehler' if self.language == 'de' else 'Error')
                    error_msg.setText('Konnte Datei nicht öffnen' if self.language == 'de' else 'Could not open file.')
                    error_msg.setInformativeText(f'Details: {str(e)}')
                    error_msg.setStandardButtons(QMessageBox.Ok)
                    error_msg.exec_()
                QApplication.quit()
            elif options_box.clickedButton() == option_open_dir_button:
                try:
                    #print(f'trying to open {os.path.dirname(self.pdf_path)}')
                    # Check the operating system and construct the appropriate command
                    if sys.platform == 'win32':
                        # On Windows, use the 'explorer' command
                        subprocess.Popen(['explorer', os.path.dirname(self.pdf_path)], shell=True, close_fds=True, creationflags=subprocess.DETACHED_PROCESS)
                    elif sys.platform == 'darwin':
                        # On macOS, use the 'open' command
                        subprocess.Popen(['open', os.path.dirname(self.pdf_path)], close_fds=True)
                    elif sys.platform.startswith('linux'):
                        # On Linux, use the 'xdg-open' command
                        subprocess.Popen(['xdg-open', os.path.dirname(self.pdf_path)], close_fds=True)
                    else:
                        raise NotImplementedError('Betriebssystem nict unterstützt' if self.language == 'de' else 'Unsupported operating system')
                except Exception as e:
                    error_msg = QMessageBox()
                    error_msg.setIcon(QMessageBox.Cfileritical)
                    error_msg.setWindowTitle('Fehler' if self.language == 'de' else 'Error')
                    error_msg.setText('Konnte Verzeichnis nicht öffnen' if self.language == 'de' else 'Could not open directory.')
                    error_msg.setInformativeText(f'Details: {str(e)}')
                    error_msg.setStandardButtons(QMessageBox.Ok)
                    error_msg.exec_()
                QApplication.quit()
            elif options_box.clickedButton() == option_quit_button:
                QApplication.quit()
            else:
                pass

    def closeEvent(self, event):
        if not self.isSaved:
            msgbox = QMessageBox()
            msgbox.setIcon(QMessageBox.Question)
            msgbox.setWindowTitle('Speichern?' if self.language == 'de' else 'Save?')
            msgbox.setText('Es liegen ungespeicherte Änderungen vor!\nVor dem Schließen speichern?'    if self.language == 'de' else 'There are unsaved changes!\nSave before quitting?')
            save_button = msgbox.addButton('Speichern'  if self.language == 'de' else 'Save', QMessageBox.YesRole)
            discard_button = msgbox.addButton('Verwerfen'  if self.language == 'de' else 'Discard', QMessageBox.NoRole)
            cancel_button = msgbox.addButton('Abbrechen'  if self.language == 'de' else 'Cancel', QMessageBox.RejectRole)

            msgbox.setDefaultButton(save_button)

            reply = msgbox.exec_()

            if msgbox.clickedButton() == save_button:
                self.save_pdf(skip = True)
                event.accept()
            elif msgbox.clickedButton() == discard_button:
                event.accept()
            else:
                event.ignore()

    def assemble_pixmap(self, page, zoom, noScale = False):

        pdf_pixmap, signatures = page
        # Scale pixmap to fit the screen initially
        if noScale == False:
            self.pdf_scale_factor = min((self.scroll_area.width() - self.scroll_area.verticalScrollBar().width() - 2) / pdf_pixmap.width(),
                        (self.scroll_area.height() - self.scroll_area.horizontalScrollBar().height() - 2) / pdf_pixmap.height())
            scale_factor = self.pdf_scale_factor
        else:
            scale_factor = 1.0

        pdf_pixmap = pdf_pixmap.scaled(int(pdf_pixmap.width() * scale_factor * zoom),
                                    int(pdf_pixmap.height() * scale_factor * zoom),
                                    aspectRatioMode=Qt.KeepAspectRatio,
                                    transformMode=Qt.SmoothTransformation)

        painter = QPainter(pdf_pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        for sig in signatures:
            sig_idx = sig[0]
            painter.drawPixmap(int(sig[2] * scale_factor * zoom),
                                int(sig[3] * scale_factor * zoom),
                                self.signatures[sig_idx][1].scaled(int(self.signatures[sig_idx][1].width() * self.signatures[sig_idx][3] * sig[1] * zoom * scale_factor),
                                                            int(self.signatures[sig_idx][1].height() * self.signatures[sig_idx][3] * sig[1] * zoom * scale_factor),
                                                            aspectRatioMode=Qt.KeepAspectRatio,
                                                            transformMode=Qt.SmoothTransformation))
        painter.end()

        return pdf_pixmap

if __name__ == '__main__':
    app = QApplication(sys.argv)

    pdf_path = sys.argv[1] if len(sys.argv) > 1 else None
    ex = PDFSigner(pdf_path)
    sys.exit(app.exec_())
