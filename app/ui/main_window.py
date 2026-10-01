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
    QGridLayout,
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
        
        self.pages.addWidget(self.create_dashboard_page())
        # Placeholder pages
        for name, index in menu_items:
            if index == 0:
                continue
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
        self.load_batches()
        
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
            #dashboardPage {{
        background: #F8F6EA;
    }}

    #dashboardGreeting {{
        color: #012D54;
        font-size: 26px;
        font-weight: 700;
    }}

    #dashboardSubtitle {{
        color: #615F4B;
        font-size: 13px;
    }}

    #dashboardCard {{
        background: #FEFEFE;
        border: 1px solid #E9DEBA;
        border-radius: 10px;
    }}

    #dashboardCard:hover {{
        border: 1px solid #D9B85F;
    }}

    #dashboardCardTitle {{
        color: #615F4B;
        font-size: 12px;
        font-weight: 600;
    }}

    #dashboardCardValue {{
        color: #012D54;
        font-size: 28px;
        font-weight: 700;
    }}

    #dashboardCardDescription {{
        color: #615F4B;
        font-size: 11px;
    }}

    #dashboardSectionCard {{
        background: #FEFEFE;
        border: 1px solid #E9DEBA;
        border-radius: 10px;
        min-height: 180px;
    }}

    #dashboardSectionTitle {{
        color: #012D54;
        font-size: 16px;
        font-weight: 700;
    }}

    #dashboardSectionText {{
        color: #615F4B;
        font-size: 13px;
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

    def create_dashboard_page(self):
        page = QWidget()
        page.setObjectName("dashboardPage")

        layout = QVBoxLayout(page)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(20)

        # ── Header ──────────────────────────────────────
        header_layout = QVBoxLayout()
        header_layout.setSpacing(4)

        greeting = QLabel("Good afternoon 👋")
        greeting.setObjectName("dashboardGreeting")

        subtitle = QLabel(
            "Here's what's happening with your coaching today."
        )
        subtitle.setObjectName("dashboardSubtitle")

        header_layout.addWidget(greeting)
        header_layout.addWidget(subtitle)

        layout.addLayout(header_layout)

        # ── Summary Cards ───────────────────────────────
        cards_layout = QGridLayout()
        cards_layout.setSpacing(15)

        cards = [
            ("Students", "0", "Total students"),
            ("Attendance", "—", "Today's attendance"),
            ("Fees Pending", "₹0", "Outstanding amount"),
            ("Upcoming Tests", "0", "Tests scheduled"),
        ]

        for column, (title, value, description) in enumerate(cards):
            card = QFrame()
            card.setObjectName("dashboardCard")
            card.setMinimumHeight(125)

            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(20, 18, 20, 18)
            card_layout.setSpacing(5)

            title_label = QLabel(title)
            title_label.setObjectName("dashboardCardTitle")

            value_label = QLabel(value)
            value_label.setObjectName("dashboardCardValue")

            description_label = QLabel(description)
            description_label.setObjectName(
                "dashboardCardDescription"
            )

            card_layout.addWidget(title_label)
            card_layout.addWidget(value_label)
            card_layout.addWidget(description_label)
            card_layout.addStretch()

            cards_layout.addWidget(card, 0, column)

        layout.addLayout(cards_layout)

        # ── Lower Section ───────────────────────────────
        lower_layout = QHBoxLayout()
        lower_layout.setSpacing(15)

        today_card = QFrame()
        today_card.setObjectName("dashboardSectionCard")

        today_layout = QVBoxLayout(today_card)
        today_layout.setContentsMargins(20, 18, 20, 18)

        today_title = QLabel("Today's Classes")
        today_title.setObjectName("dashboardSectionTitle")

        today_info = QLabel(
            "No classes scheduled for today."
        )
        today_info.setObjectName("dashboardSectionText")

        today_layout.addWidget(today_title)
        today_layout.addSpacing(10)
        today_layout.addWidget(today_info)
        today_layout.addStretch()

        alerts_card = QFrame()
        alerts_card.setObjectName("dashboardSectionCard")

        alerts_layout = QVBoxLayout(alerts_card)
        alerts_layout.setContentsMargins(20, 18, 20, 18)

        alerts_title = QLabel("Alerts & Notifications")
        alerts_title.setObjectName("dashboardSectionTitle")

        alerts_info = QLabel(
            "No alerts at the moment."
        )
        alerts_info.setObjectName("dashboardSectionText")

        alerts_layout.addWidget(alerts_title)
        alerts_layout.addSpacing(10)
        alerts_layout.addWidget(alerts_info)
        alerts_layout.addStretch()

        lower_layout.addWidget(today_card, 1)
        lower_layout.addWidget(alerts_card, 1)

        layout.addLayout(lower_layout)

        return page


        