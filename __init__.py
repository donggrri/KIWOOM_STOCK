from kiwoom.kiwoom import *
from PyQt5.QtWidgets import *
import sys

class Main():
    def __init__(self):
        print("Main() class start")

        self.app = QApplication(sys.argv)
        self.kiwoom = Kiwoom()
        self.app.exec_() # 이벤트 루프 실행

if __name__ == "__main__":
       Main()