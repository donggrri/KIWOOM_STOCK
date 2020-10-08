from kiwoom.kiwoom import *
# UI 만들 때 이 파일을 사용한다.
import sys
from PyQt5.QtWidgets import * # Pyqt5
class UI_class(): #class 생성시 앞글자는 대문자로
    def __init__(self):
        print("UI class 입니다.")
        self.app = QApplication(sys.argv)#argv 무엇인지 알아보기
        #argv 에는 파이썬 경로가 넘어간다
        self.kiwoom = Kiwoom()

        self.app.exec_()

