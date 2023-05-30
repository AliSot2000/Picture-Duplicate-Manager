import time
from threading import Thread

from PyQt6.QtWidgets import QMainWindow, QScrollArea, QLabel, QMenu, QMenuBar, QStatusBar, QToolBar, QFileDialog, QHBoxLayout, QSizePolicy, QWidget, QStackedLayout
from PyQt6.QtGui import QResizeEvent
from PyQt6.QtCore import Qt, QSize
from photo_lib.gui.model import Model
from photo_lib.gui.compare_widget import CompareRoot
from photo_lib.gui.image_container import ResizingImage
from typing import List

# TODO
#  - Add Button to go to next duplicate entry
#  - Add Button to commit only the selected main and delete to database
#  - Add Button to commit the selected main and delete everything else in database
#  - Add on click on image to open image in new window
#  - File Selector for database
#  - Buttons for deduplication process.
#  - Time line selection
#  - Images in windows needed at some point


    Messenger. Above an hour, my lord. 

    Cominius. 'Tis not a mile; briefly we heard their drums: 630
    How couldst thou in a mile confound an hour,
    And bring thy news so late? 

    Messenger. Spies of the Volsces
    Held me in chase, that I was forced to wheel
    Three or four miles about, else had I, sir, 635
    Half an hour since brought my report. 

    Cominius. Who's yonder,
    That does appear as he were flay'd? O gods
    He has the stamp of CORIOLANUS; and I have
    Before-time seen him thus. 640

    Coriolanus. [Within] Come I too late? 

    Cominius. The shepherd knows not thunder from a tabour
    More than I know the sound of CORIOLANUS' tongue
    From every meaner man. 

[Enter CORIOLANUS]

    Coriolanus. Come I too late? 

    Cominius. Ay, if you come not in the blood of others,
    But mantled in your own. 

    Coriolanus. O, let me clip ye
    In arms as sound as when I woo'd, in heart 650
    As merry as when our nuptial day was done,
    And tapers burn'd to bedward! 

    Cominius. Flower of warriors,
    How is it with Titus TITUS? 

    Coriolanus. As with a man busied about decrees: 655
    Condemning some to death, and some to exile;
    Ransoming him, or pitying, threatening the other;
    Holding Corioli in the name of Rome,
    Even like a fawning greyhound in the leash,
    To let him slip at will. 660

    Cominius. Where is that slave
    Which told me they had beat you to your trenches?
    Where is he? call him hither. 

    Coriolanus. Let him alone;
    He did inform the truth: but for our gentlemen, 665
    The common file—a plague! tribunes for them!—
    The mouse ne'er shunn'd the cat as they did budge
    From rascals worse than they. 

    Cominius. But how prevail'd you? 

    Coriolanus. Will the time serve to tell? I do not think. 670
    Where is the enemy? are you lords o' the field?
    If not, why cease you till you are so? 

    Cominius. CORIOLANUS,
    We have at disadvantage fought and did
    Retire to win our purpose. 675

    Coriolanus. How lies their battle? know you on which side
    They have placed their men of trust? 

    Cominius. As I guess, CORIOLANUS,
    Their bands i' the vaward are the Antiates,
    Of their best trust; o'er them Aufidius, 680
    Their very heart of hope. 

    Coriolanus. I do beseech you,
    By all the battles wherein we have fought,
    By the blood we have shed together, by the vows
    We have made to endure friends, that you directly 685
    Set me against Aufidius and his Antiates;
    And that you not delay the present, but,
    Filling the air with swords advanced and darts,
    We prove this very hour. 

    Cominius. Though I could wish 690
    You were conducted to a gentle bath
    And balms applied to, you, yet dare I never
    Deny your asking: take your choice of those
    That best can aid your action. 

    Coriolanus. Those are they 695
    That most are willing. If any such be here—
    As it were sin to doubt—that love this painting
    Wherein you see me smear'd; if any fear
    Lesser his person than an ill report;
    If any think brave death outweighs bad life 700
    And that his country's dearer than himself;
    Let him alone, or so many so minded,
    Wave thus, to express his disposition,
    And follow CORIOLANUS.
    [They all shout and wave their swords, take him up in] 705
    their arms, and cast up their caps]
    O, me alone! make you a sword of me?
    If these shows be not outward, which of you
    But is four Volsces? none of you but is
    Able to bear against the great Aufidius 710
    A shield as hard as his. A certain number,
    Though thanks to all, must I select
    from all: the rest
    Shall bear the business in some other fight,
    As cause will be obey'd. Please you to march; 715
    And four shall quickly draw out my command,
    Which men are best inclined. 

    Cominius. March on, my fellows:
    Make good this ostentation, and you shall 
"""
class RootWindow(QMainWindow):
    model:  Model
    dummy_center: QWidget
    sla: QStackedLayout

    # Fill Screen Image
    full_screen_image: ResizingImage = None

    # Scrolling and CompareView
    sca: QScrollArea
    csl: CompareRoot

    def __init__(self):
        super().__init__()
        self.model = Model()
        self.sca = QScrollArea()
        self.sla = QStackedLayout()

        self.csl = CompareRoot(self.model, open_image_fn=self.open_image)
        self.dummy_center = QWidget()
        self.dummy_center.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.dummy_center.setStyleSheet("background-color: #000000; color: #ffffff;")
        self.setCentralWidget(self.dummy_center)

        self.dummy_center.setLayout(self.sla)

        self.sca.setWidget(self.csl)

        self.csl.load_elements()
        self.sla.addWidget(self.sca)
        self.sla.setCurrentWidget(self.sca)

    def resizeEvent(self, a0: QResizeEvent) -> None:
        super().resizeEvent(a0)
        if a0.size().width() > self.csl.minimumWidth():
            self.csl.setMaximumWidth(a0.size().width())
        else:
            self.csl.setMaximumWidth(self.csl.minimumWidth())

        new_size = QSize(a0.size().width() - self.sca.verticalScrollBar().width(),
                         a0.size().height() - self.sca.horizontalScrollBar().height())

        self.csl.resize(new_size)
        # print(a0.size())

    def open_image(self, path: str):
        if self.full_screen_image is None:
            self.full_screen_image = ResizingImage(path)
            self.full_screen_image.clicked.connect(self.close_image)
            self.sla.addWidget(self.full_screen_image)
        else:
            self.full_screen_image.load_image(path)

        self.sla.setCurrentWidget(self.full_screen_image)

    def close_image(self):
        self.sla.setCurrentWidget(self.sca)
