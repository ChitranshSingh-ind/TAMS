from app.ui.settings_dialog import SettingsDialog
from PyQt6.QtCore import Qt
from app.database.connection import SessionLocal
from app.services.batch_service import get_active_batches
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

NAVY = "#012D54"
DARK_NAVY = "#04294D"
GOLD = "#D9B85F"
LIGHT_GOLD = "#E9DEBA"
CREAM = "#F8F6EA"
WHITE = "#FEFEFE"
TEXT = "#1F2937"
MUTED = "#615F4B"
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("TAMS - Coaching Management System")
        self.resize(1280, 800)

        self.setup_ui()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0,0,0,0)
        main_layout.setSpacing(0)

        # Top bar
        top_bar = QFrame()
        top_bar.setObjectName("topBar")

        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(20, 12, 20, 12)

        title = QLabel("Coaching Management System")
        title.setObjectName("appTitle")

        

        settings_button = QPushButton("⚙")
        settings_button.setObjectName("settingButton")
        settings_button.clicked.connect(self.open_settings)

        top_layout.addWidget(title)
     
        top_layout.addStretch()
        
        top_layout.addWidget(settings_button)

        main_layout.addWidget(top_bar)
        #  Main area
        content_widget = QWidget()
        content_widget.setObjectName("contentWidget")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0,0,0,0)
        content_layout.setSpacing(0)
        

        content_toolbar = QFrame()
        content_toolbar.setObjectName("contentToolbar")

        content_toolbar_layout = QHBoxLayout(content_toolbar)
        content_toolbar_layout.setContentsMargins(20,12,20,12)

        content_toolbar_layout.addStretch()

        batch_label = QLabel("Batch:")
        batch_label.setObjectName("batchLabel")

        self.batch_selector = QComboBox()
        self.batch_selector.setObjectName("batchSelector")
        self.batch_selector.setMinimumWidth(180)
        self.batch_selector.addItem("All Batches", None)

        content_toolbar_layout.addWidget(batch_label)
        content_toolbar_layout.addWidget(self.batch_selector)

        content_layout.addWidget(content_toolbar)

        workspace_layout = QHBoxLayout()
        workspace_layout.setContentsMargins(0,0,0,0)
        workspace_layout.setSpacing(0)

        


        

        

        # Sidebar
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(210)

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(10, 15, 10, 15)
        sidebar_layout.setSpacing(5)

        self.pages = QStackedWidget()

        menu_items = [
            ("Dashboard", 0),
            ("Students", 1),
            ("Attendance", 2),
            ("Results", 3),
            ("Fees", 4),
            ("Expenses", 5),
            ("Teaching", 6),
            ("Analysis", 7),
            ("Messages", 8),
        ]
        workspace_layout.addWidget(sidebar)
        
        self.sidebar_buttons = []
        for name, index in menu_items:
            button = QPushButton(name)
            button.setCursor(Qt.CursorShape.PointingHandCursor)

            button.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )

            button.setProperty("page_index", index)
            button.setProperty("active", index == 0)

            button.clicked.connect(
                lambda checked=False, i=index: self.change_page(i)
            )

            sidebar_layout.addWidget(button)
            self.sidebar_buttons.append(button)

        sidebar_layout.addStretch()
        

        # Placeholder pages
        for name, _ in menu_items:
            page = QWidget()
            layout = QVBoxLayout(page)

            label = QLabel(name)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("font-size: 28px;")

            layout.addWidget(label)

            self.pages.addWidget(page)

        workspace_layout.addWidget(self.pages)
        content_layout.addLayout(workspace_layout)

        main_layout.addWidget(content_widget)

        self.apply_styles()
        self.load_batches()
    def open_settings(self):
        dialog = SettingsDialog(self)
        dialog.exec()
        
    def apply_styles(self):
        self.setStyleSheet(f"""
            QMainWindow {{
                background: {LIGHT_GOLD};
            }}
    
            #topBar {{
                background: {NAVY};
                border-bottom: 2px solid {GOLD};
            }}
    
            #appTitle {{
                color: {WHITE};
                font-size: 24px;
                font-weight: bold;
            }}
    
            #batchLabel {{
                color: {NAVY};
                font-weight: 600;
            }}
    
            #sidebar {{
                background: {CREAM};
                border-right: 1px solid {LIGHT_GOLD};
            }}
    
            #batchSelector {{
                background-color: {WHITE};
                color: {NAVY};
                border: 1px solid {GOLD};
                border-radius: 6px;
                padding: 7px 10px;
            }}
    
            #batchSelector QAbstractItemView {{
                background-color: {WHITE};
                color: {TEXT};
                selection-background-color: {NAVY};
                selection-color: {WHITE};
            }}
    
            #sidebar QPushButton {{
                text-align: left;
                padding: 10px 14px;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                color: {NAVY};
                background: transparent;
            }}
    
            #sidebar QPushButton:hover {{
                background: {LIGHT_GOLD};
                color: {DARK_NAVY};
            }}
    
            #contentToolbar {{
                background: {CREAM};
                border-bottom: 1px solid {LIGHT_GOLD};
            }}
    
            QComboBox {{
                padding: 7px 10px;
                border: 1px solid {GOLD};
                border-radius: 10px;
                background: {WHITE};
            }}
    
            #settingButton {{
                background: transparent;
                color: {WHITE};
                border: none;
                font-size: 18px;
            }}
    
            #settingButton:hover {{
                background: {DARK_NAVY};
            }}
    
            #batchSelector::drop-down {{
                border: none;
                width: 0px;
            }}
    
            #batchSelector::down-arrow {{
                image: none;
                width: 0px;
                height: 0px;
            }}
            #sidebar QPushButton[active="true"] {{
                background: {GOLD};
                color: {NAVY};
                font-weight: 700;
            }}
        """)
    def change_page(self,index):
        self.pages.setCurrentIndex(index)

        for button in self.sidebar_buttons:
            button.setProperty("active", button.property("page_index") == index)
            button.style().unpolish(button)
            button.style().polish(button)
    def load_batches(self):
        self.batch_selector.clear()

        self.batch_selector.addItem("All Batches", None)
        with SessionLocal() as session:
            batches = get_active_batches(session)
            for batch in batches:
                self.batch_selector.addItem(
                    batch.name, 
                    batch.id
                )
                
        self.pages.setCurrentIndex(0)
    