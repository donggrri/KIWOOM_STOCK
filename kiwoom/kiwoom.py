from PyQt5.QAxContainer import *
from PyQt5.QtCore import *
from config.errorCode import *
from PyQt5.QtTest import *
from config.kiwoomType import *
from config.log_class import *
import sys
from config.slack import *

class Kiwoom(QAxWidget):
    def __init__(self):
        super().__init__()
        self.realType = RealType()
        self.logging = Logging()
        self.slack = Slack() #슬랙 동작

        self.logging.logger.debug("Kiwoom() class start.")

        ####### event loop를 실행하기 위한 변수모음
        self.login_event_loop = QEventLoop() #로그인을 이벤트 루프 안에서 실행하도록 만들기 위해 선언한 변수
        self.detail_account_info_event_loop = QEventLoop()  # 예수금 요청용 이벤트루프
        self.get_stock_price_event_loop = QEventLoop()
        #########################################

        ########### 전체 종목 관리
        self.all_stock_dict = {}
        ###########################


        ####### 계좌 관련된 변수
        self.account_stock_dict = {} #내가 보유하고 있는 종목 리스트
        self.not_account_stock_dict = {}
        self.condition_search_dict = {} # 조건검색해서 찾게된 사전
        self.deposit = 0 #예수금
        self.use_money = 5000000 #실제 투자에 사용할 금액
        self.use_money_percent = 1 #예수금에서 실제 사용할 비율
        self.output_deposit = 0 #출력가능 금액
        self.total_profit_loss_money = 0 #총평가손익금액
        self.total_profit_loss_rate = 0.0 #총수익률(%)
        self.condition_list_count = 5 # 조건검색 된 종목 숫자
        self.buy_checking_code_dict = {} # setrealreg 할 때 기본값을 FALSE로, 매수주문을 한 다음에는 TRUE로 변경
        ########################################

        ######## 종목 정보 가져오기
        self.jango_dict = {}

        ########################

        ########### 종목 분석 용
        self.calcul_data = []
        ##########################################

        ###### 슬랙에 메시지 보낼때 사용될 리스트
        self.slack_msg_condition_stock = []

        ########### 내 계좌번호 저장할 변수
        self.account_num = 0

        ####### 요청 스크린 번호
        self.screen_my_info = "2000"  # 계좌 관련한 스크린 번호
        self.screen_start_stop_real = "1000" #장 시작/종료 실시간 스크린번호
        self.screen_to_buy = "3000" # 구매할 때 사용 할 스크린 번호
        self.screen_get_stock_price = "4000" # 주식일봉요청할 때 사용하는 스크린번호
        ########################################

        ######### 초기 셋팅 함수들 바로 실행
        self.get_ocx_instance() #Ocx 방식을 파이썬에 사용할 수 있게 변환해 주는 함수 실행
        self.event_slots() #키움과 연결하기 위한 signal / slot 모음 함수 실행
        self.signal_login_commConnect() #로그인 시도 함수 실행

        self.get_account_info()
        self.detail_account_info() #예수금 요청 시그널 포함
        self.detail_account_mystock() #계좌평가잔고내역 요청 시그널 포함

        self.condition_event_slot()
        self.condition_signal()
        self.real_event_slot()  # 실시간 이벤트 시그널 / 슬롯 연결

        #########################################
        QTest.qWait(5000)

        # 실시간 수신 관련 함수
        self.dynamicCall("SetRealReg(QString, QString, QString, QString)", self.screen_start_stop_real, '', self.realType.REALTYPE['장시작시간']['장운영구분'], "0")

        for code in self.account_stock_dict.keys():
            screen_num = self.account_stock_dict[code]['스크린번호']
            fids = self.realType.REALTYPE['주식체결']['체결시간']
            self.dynamicCall("SetRealReg(QString, QString, QString, QString)", screen_num, code, fids, "1")

        self.slack.notification(
            pretext="주식자동화 프로그램 동작",
            title="주식 자동화 프로그램 동작",
            fallback="주식 자동화 프로그램 동작",
            text="주식 자동화 프로그램이 동작 되었습니다."
        )

    def get_ocx_instance(self):
        self.setControl("KHOPENAPI.KHOpenAPICtrl.1")


    def event_slots(self):
        self.OnEventConnect.connect(self.login_slot)
        self.OnReceiveTrData.connect(self.trdata_slot) # 트랜잭션 요청 관련 이벤트
        self.OnReceiveMsg.connect(self.msg_slot)


    def signal_login_commConnect(self):
        self.dynamicCall("CommConnect()")

        self.login_event_loop.exec_()

    def login_slot(self, err_code):

        self.logging.logger.debug(errors(err_code)[1])

        self.login_event_loop.exit()


    def stop_screen_cancel(self, sScrNo=None):
        self.dynamicCall("DisconnectRealData(QString)", sScrNo)

    #송수신 메세지 get
    def msg_slot(self, sScrNo, sRQName, sTrCode, msg):
        self.logging.logger.debug("스크린: %s, 요청이름: %s, tr코드: %s --- %s" %(sScrNo, sRQName, sTrCode, msg))

    #조건검색식 이벤트 모음
    def condition_event_slot(self):
        self.OnReceiveConditionVer.connect(self.condition_slot)
        self.OnReceiveTrCondition.connect(self.condition_tr_slot)
        self.OnReceiveRealCondition.connect(self.condition_real_slot)

    def real_event_slot(self):
        self.OnReceiveRealData.connect(self.realdata_slot)  # 실시간 이벤트 연결
        self.OnReceiveChejanData.connect(self.chejan_slot) #종목 주문체결 관련한 이벤트

    def get_account_info(self):
        account_list = self.dynamicCall("GetLoginInfo(QString)", "ACCNO") # 계좌번호 반환
        account_num = account_list.split(';')[0]

        self.account_num = account_num

        self.logging.logger.debug("계좌번호 : %s" % account_num)

    def detail_account_info(self, sPrevNext="0"):

        self.dynamicCall("SetInputValue(QString, QString)", "계좌번호", self.account_num)
        self.dynamicCall("SetInputValue(QString, QString)", "비밀번호", "0000")
        self.dynamicCall("SetInputValue(QString, QString)", "비밀번호입력매체구분", "00")
        self.dynamicCall("SetInputValue(QString, QString)", "조회구분", "1")
        self.dynamicCall("CommRqData(QString, QString, int, QString)", "예수금상세현황요청", "opw00001", sPrevNext, self.screen_my_info)

        self.detail_account_info_event_loop.exec_()

    def detail_account_mystock(self, sPrevNext="0"):

        self.dynamicCall("SetInputValue(QString, QString)", "계좌번호", self.account_num)
        self.dynamicCall("SetInputValue(QString, QString)", "비밀번호", "0000")
        self.dynamicCall("SetInputValue(QString, QString)", "비밀번호입력매체구분", "00")
        self.dynamicCall("SetInputValue(QString, QString)", "조회구분", "1")
        self.dynamicCall("CommRqData(QString, QString, int, QString)", "계좌평가잔고내역요청", "opw00018", sPrevNext, self.screen_my_info)

        self.detail_account_info_event_loop.exec_()

    # 어떤 조건식이 있는지 확인
    def condition_slot(self, lRet, sMsg):
        self.logging.logger.debug("호출 성공 여부 %s, 호출결과 메시지 %s" % (lRet, sMsg))

        condition_name_list = self.dynamicCall("GetConditionNameList()")
        self.logging.logger.debug("HTS의 조건검색식 이름 가져오기 %s" % condition_name_list)

        condition_name_list = condition_name_list.split(";")[:-1]

        for unit_condition in condition_name_list:
            index = unit_condition.split("^")[0]
            index = int(index)
            condition_name = unit_condition.split("^")[1]

            self.logging.logger.debug("조건식 분리 번호: %s, 이름: %s" % (index, condition_name))

            ok  = self.dynamicCall("SendCondition(QString, QString, int, int)", "0156", condition_name, index, 1) #조회요청 + 실시간 조회
            self.logging.logger.debug("조회 성공여부 %s " % ok)



    # 조건식 로딩 하기
    def condition_signal(self):
        self.dynamicCall("GetConditionLoad()")

    # 나의 조건식에 해당하는 종목코드 받기
    def condition_tr_slot(self, sScrNo, strCodeList, strConditionName, index, nNext):
        self.logging.logger.debug("화면번호: %s, 종목코드 리스트: %s, 조건식 이름: %s, 조건식 인덱스: %s, 연속조회: %s" % (sScrNo, strCodeList, strConditionName, index, nNext))

        code_list = strCodeList.split(";")[:-1]
        if index == 6 :
            self.logging.logger.debug("검색된 종목----------------------- \n %s" % code_list)
            self.decide_buy_or_not(code_list)

    # 조건식 실시간으로 받기
    def condition_real_slot(self, strCode, strType, strConditionName, strConditionIndex):
        self.logging.logger.debug("종목코드: %s, 이벤트종류: %s, 조건식이름: %s, 조건명인덱스: %s" % (strCode, strType, strConditionName, strConditionIndex))

        if strType == "I":
            self.logging.logger.debug("종목코드: %s, 종목편입: %s" % (strCode, strType))
            stock_name = self.dynamicCall("GetMasterCodeName(QString)", strCode)
            ####종목이 편입되면 , SetRealReg를 통해서 실시간 등록을 해준다.
            screen_num = self.screen_to_buy
            fids = self.realType.REALTYPE['주식체결']['체결시간']
            self.dynamicCall("SetRealReg(QString, QString, QString, QString)", screen_num, strCode, fids, "1")
            if stock_name not in self.slack_msg_condition_stock :
                self.slack_msg_condition_stock.append(stock_name)
                self.slack.notification(
                    pretext="주식자동화 프로그램 동작",
                    title="조건식 실시간으로 받기",
                    fallback="주식 자동화 프로그램 조건검색",
                    text="종목코드 [%s] 종목명 [%s] 가 포착되었습니다. \n" % (strCode,stock_name)
                )
            self.buy_checking_code_dict.update({strCode:{}}) # 'buy_flag' 가 False인 경우에만 구매하기 위해서 추가하는 사전임
            self.buy_checking_code_dict[strCode].update({'buy_flag': False})
            self.buy_checking_code_dict[strCode].update({'buy_cnt': 0})
        elif strType == "D":
            self.logging.logger.debug("종목코드: %s, 종목이탈: %s" % (strCode, strType))
            stock_name = self.dynamicCall("GetMasterCodeName(QString)", strCode)
            #if stock_name in self.slack_msg_condition_stock:
                #self.slack_msg_condition_stock.pop(stock_name)



    def trdata_slot(self, sScrNo, sRQName, sTrCode, sRecordName, sPrevNext):
        self.logging.logger.debug("sRQName: %s, sTrCode: %s" % (sRQName, sTrCode))

        if sRQName == "예수금상세현황요청":
            deposit = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, 0, "예수금")
            self.deposit = int(deposit)

            use_money = float(self.deposit) * self.use_money_percent
            self.use_money = int(use_money)
            #self.use_money = self.use_money / 4

            output_deposit = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, 0, "출금가능금액")
            self.output_deposit = int(output_deposit)

            self.logging.logger.debug("예수금 : %s" % self.output_deposit)

            self.stop_screen_cancel(self.screen_my_info)

            self.detail_account_info_event_loop.exit()

        elif sRQName == "계좌평가잔고내역요청":

            total_buy_money = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, 0, "총매입금액")
            self.total_buy_money = int(total_buy_money)
            total_profit_loss_money = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, 0, "총평가손익금액")
            self.total_profit_loss_money = int(total_profit_loss_money)
            total_profit_loss_rate = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, 0, "총수익률(%)")
            self.total_profit_loss_rate = float(total_profit_loss_rate)

            self.logging.logger.debug("계좌평가잔고내역요청 싱글데이터 : %s - %s - %s" % (total_buy_money, total_profit_loss_money, total_profit_loss_rate))

            rows = self.dynamicCall("GetRepeatCnt(QString, QString)", sTrCode, sRQName)
            for i in range(rows):
                code = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "종목번호")  # 출력 : A039423 // 알파벳 A는 장내주식, J는 ELW종목, Q는 ETN종목
                code = code.strip()[1:]

                code_nm = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "종목명")  # 출럭 : 한국기업평가
                stock_quantity = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "보유수량")  # 보유수량 : 000000000000010
                buy_price = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "매입가")  # 매입가 : 000000000054100
                learn_rate = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "수익률(%)")  # 수익률 : -000000001.94
                current_price = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "현재가")  # 현재가 : 000000003450
                total_chegual_price = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "매입금액")
                possible_quantity = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, i, "매매가능수량")


                self.logging.logger.debug("종목코드: %s - 종목명: %s - 보유수량: %s - 매입가:%s - 수익률: %s - 현재가: %s" % (
                    code, code_nm, stock_quantity, buy_price, learn_rate, current_price))

                if code in self.account_stock_dict:  # dictionary 에 해당 종목이 있나 확인
                    pass
                else:
                    self.account_stock_dict[code] = {}

                code_nm = code_nm.strip()
                stock_quantity = int(stock_quantity.strip())
                buy_price = int(buy_price.strip())
                learn_rate = float(learn_rate.strip())
                current_price = int(current_price.strip())
                total_chegual_price = int(total_chegual_price.strip())
                possible_quantity = int(possible_quantity.strip())

                self.account_stock_dict[code].update({"종목명": code_nm})
                self.account_stock_dict[code].update({"보유수량": stock_quantity})
                self.account_stock_dict[code].update({"매입가": buy_price})
                self.account_stock_dict[code].update({"수익률(%)": learn_rate})
                self.account_stock_dict[code].update({"현재가": current_price})
                self.account_stock_dict[code].update({"매입금액": total_chegual_price})
                self.account_stock_dict[code].update({'매매가능수량' : possible_quantity})
                self.account_stock_dict[code].update({'스크린번호': self.screen_to_buy})

            self.logging.logger.debug("sPreNext : %s" % sPrevNext)
            print("계좌에 가지고 있는 종목은 %s " % rows)

            if sPrevNext == "2":
                self.detail_account_mystock(sPrevNext="2")
            else:
                self.detail_account_info_event_loop.exit()

        elif sRQName == "주식일봉차트조회":
            self.logging.logger.debug("주식일봉차트조회")
            code = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, 0, "종목코드")
            code = code.strip()
            current_price = self.dynamicCall("GetCommData(QString, QString, int, QString)", sTrCode, sRQName, 0,
                                             "현재가")  # 출력 : 000070
            self.condition_search_dict[code].update({'현재가':current_price})
            self.get_stock_price_event_loop.exit()

    def decide_buy_or_not(self,condition_list=None):
        self.logging.logger.debug("조건검색 식 검색된 list 전달받기")
        self.logging.logger.debug("조건검색 식 검색된 list 종목들 구매 하기전에 내가 이미 가지고 있는 종목 실시간함수에 추가하기")
        for code in self.account_stock_dict :
            self.logging.logger.debug(self.account_stock_dict[code])

        self.logging.logger.debug("검색된 종목들을 리스트에 업데이트")
        self.logging.logger.debug(condition_list)

        for code in condition_list :
            if code not in self.condition_search_dict :
                self.condition_search_dict[code] = {}

                stock_name = self.dynamicCall("GetMasterCodeName(QString)", code)
                self.condition_search_dict[code].update({'종목명': stock_name})
                self.condition_search_dict[code].update({'스크린번호' : self.screen_to_buy})

        if self.use_money >= 300000 :
            #30만원 이상 예수금 있는 경우에는 구매 진행

            self.logging.logger.debug("구매 요청 하기 전에 돈이 남아있는지 확인됨..")
            for code in self.condition_search_dict:
                self.logging.logger.debug("\t"+str(self.condition_search_dict[code]))
                
                self.logging.logger.debug("%s 종목의 가격을 알아내기" %code)
                if code not in self.account_stock_dict :
                    self.logging.logger.debug("실시간 데이터 등록하기 요청 보내기..")
                    screen_num = self.condition_search_dict[code]['스크린번호']
                    fids = self.realType.REALTYPE['주식체결']['체결시간']
                    self.dynamicCall("SetRealReg(QString, QString, QString, QString)", screen_num, code, fids, "1")

        else : 
            # 아무것도 하지 않는다 : 예수금이 충분하지 않으므로
            pass

    def realdata_slot(self, sCode, sRealType, sRealData):
        if sRealType == "장시작시간":
            fid = self.realType.REALTYPE[sRealType]['장운영구분']  # (0:장시작전, 2:장종료전(20분), 3:장시작, 4,8:장종료(30분), 9:장마감)
            value = self.dynamicCall("GetCommRealData(QString, int)", sCode, fid)

            if value == '0':
                self.logging.logger.debug("장 시작 전")

            elif value == '3':
                self.logging.logger.debug("장 시작")

            elif value == "2":
                self.logging.logger.debug("장 종료, 동시호가로 넘어감")

            elif value == "4":
                self.logging.logger.debug("3시30분 장 종료")

                for code in self.condition_search_dict.keys():
                    self.dynamicCall("SetRealRemove(QString, QString)", self.condition_search_dict[code]['스크린번호'], code)

                QTest.qWait(5000)

                sys.exit()

        elif sRealType == "주식체결":

            a = self.dynamicCall("GetCommRealData(QString, int)", sCode, self.realType.REALTYPE[sRealType]['체결시간'])  # 출력 HHMMSS
            b = self.dynamicCall("GetCommRealData(QString, int)", sCode, self.realType.REALTYPE[sRealType]['현재가'])  # 출력 : +(-)2520
            b = abs(int(b))

            c = self.dynamicCall("GetCommRealData(QString, int)", sCode, self.realType.REALTYPE[sRealType]['전일대비'])  # 출력 : +(-)2520
            c = abs(int(c))

            d = self.dynamicCall("GetCommRealData(QString, int)", sCode, self.realType.REALTYPE[sRealType]['등락율'])  # 출력 : +(-)12.98
            d = float(d)

            e = self.dynamicCall("GetCommRealData(QString, int)", sCode, self.realType.REALTYPE[sRealType]['(최우선)매도호가'])  # 출력 : +(-)2520
            e = abs(int(e))

            f = self.dynamicCall("GetCommRealData(QString, int)", sCode, self.realType.REALTYPE[sRealType]['(최우선)매수호가'])  # 출력 : +(-)2515
            f = abs(int(f))

            g = self.dynamicCall("GetCommRealData(QString, int)", sCode, self.realType.REALTYPE[sRealType]['거래량'])  # 출력 : +240124  매수일때, -2034 매도일 때
            g = abs(int(g))

            h = self.dynamicCall("GetCommRealData(QString, int)", sCode, self.realType.REALTYPE[sRealType]['누적거래량'])  # 출력 : 240124
            h = abs(int(h))

            i = self.dynamicCall("GetCommRealData(QString, int)", sCode, self.realType.REALTYPE[sRealType]['고가'])  # 출력 : +(-)2530
            i = abs(int(i))

            j = self.dynamicCall("GetCommRealData(QString, int)", sCode, self.realType.REALTYPE[sRealType]['시가'])  # 출력 : +(-)2530
            j = abs(int(j))

            k = self.dynamicCall("GetCommRealData(QString, int)", sCode, self.realType.REALTYPE[sRealType]['저가'])  # 출력 : +(-)2530
            k = abs(int(k))

            if sCode not in self.condition_search_dict:
                self.condition_search_dict.update({sCode:{}})

            self.condition_search_dict[sCode].update({"체결시간": a})
            self.condition_search_dict[sCode].update({"현재가": b})
            self.condition_search_dict[sCode].update({"전일대비": c})
            self.condition_search_dict[sCode].update({"등락율": d})
            self.condition_search_dict[sCode].update({"(최우선)매도호가": e})
            self.condition_search_dict[sCode].update({"(최우선)매수호가": f})
            self.condition_search_dict[sCode].update({"거래량": g})
            self.condition_search_dict[sCode].update({"누적거래량": h})
            self.condition_search_dict[sCode].update({"고가": i})
            self.condition_search_dict[sCode].update({"시가": j})
            self.condition_search_dict[sCode].update({"저가": k})


            #self.logging.logger.debug("asd dict => [%s]" %self.account_stock_dict.keys())
            if sCode in self.account_stock_dict.keys() and sCode not in self.jango_dict.keys():
                asd = self.account_stock_dict[sCode]
                meme_rate = (b - asd['매입가']) / asd['매입가'] * 100

                if asd['매매가능수량'] > 0 and (meme_rate > 5 or meme_rate < -5):

                    order_success = self.dynamicCall(
                        "SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)",
                        ["신규매도", self.screen_to_buy, self.account_num, 2, sCode, asd['매매가능수량'], 0, self.realType.SENDTYPE['거래구분']['시장가'], ""]
                    )

                    if order_success == 0 :
                        self.logging.logger.debug("매도주문 전달 성공")
                        self.slack.notification(
                            pretext="주식자동화 프로그램 동작",
                            title="주식 자동화 프로그램 동작",
                            fallback="주식 자동화 프로그램 조건검색",
                            text="%s 종목을 '매도' 주문하였습니다.\n \t 체결시간 =\t [%s]" % (sCode,a)
                        )

                        del self.account_stock_dict[sCode]
                    else:
                        self.logging.logger.debug("매도주문 전달 실패")

            elif sCode in self.jango_dict.keys():
                jd = self.jango_dict[sCode]
                meme_rate = (b - jd['매입단가']) / jd['매입단가'] * 100

                if jd['주문가능수량'] > 0 and (meme_rate > 3 or meme_rate < -3):

                    order_success = self.dynamicCall(
                        "SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)",
                        ["신규매도", self.screen_to_buy, self.account_num, 2, sCode, jd['주문가능수량'], 0, self.realType.SENDTYPE['거래구분']['시장가'], ""]
                    )

                    if order_success == 0:
                        self.logging.logger.debug("매도주문 전달 성공")
                        self.slack.notification(
                            pretext="주식자동화 프로그램 동작",
                            title="주식 자동화 프로그램 동작",
                            fallback="주식 자동화 프로그램 조건검색",
                            text="%s 종목 '매도' 주문 완료.\n \t 체결시간 =\t [%s]" % (sCode,a)
                        )

                    else:
                        self.logging.logger.debug("매도주문 전달 실패")


            elif d >= 0.0 and sCode not in self.jango_dict: 
                try:
                    self.logging.logger.debug("매수조건 통과 %s " % sCode)
                    result = 300000 / f
                    quantity = int(result)
                    #self.logging.logger.debug("quantity type is \t" + str(type(quantity)))
                    #self.logging.logger.debug("quantity is \t" + str(quantity))
                    if self.buy_checking_code_dict[sCode]['buy_flag'] is True:
                        self.logging.logger.debug("%s 는 이미 매수한 종목입니다." %sCode)

                    else :
                        order_success = self.dynamicCall(
                            "SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)",
                            ["신규매수", self.screen_to_buy , self.account_num, 1, sCode, quantity,
                             e, self.realType.SENDTYPE['거래구분']['지정가'], ""]
                        )

                        if order_success == 0 and self.buy_checking_code_dict[sCode]['buy_flag'] is False:
                            self.logging.logger.debug("매수주문 전달 성공")
                            #self.buy_checking_code_dict.update({})
                            self.use_money = self.use_money - 300000
                            #
                            self.slack.notification(
                                pretext="조건식 검색 종목 매수",
                                title="매수주문 완료",
                                text="%s 종목 중복 매수 주문 방지.\n \t 체결시간 =\t [%s]" % (sCode, a)
                            )
                            self.buy_checking_code_dict[sCode].update({'buy_flag':True}) # 더이상 해당 종목이 중복주문 되지 않도록 수정.

                        else:
                            self.logging.logger.debug("매수주문 전달 실패")

                except ZeroDivisionError:
                    self.logging.logger.debug("ZeroDivision")
                    pass

            not_meme_list = list(self.not_account_stock_dict)
            for order_num in not_meme_list:
                code = self.not_account_stock_dict[order_num]["종목코드"]
                meme_price = self.not_account_stock_dict[order_num]['주문가격']
                not_quantity = self.not_account_stock_dict[order_num]['미체결수량']
                order_gubun = self.not_account_stock_dict[order_num]['주문구분']


                if order_gubun == "매수" and not_quantity > 0 and e > meme_price:
                    order_success = self.dynamicCall(
                        "SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)",
                        ["매수취소", self.screen_to_buy, self.account_num, 3, code, 0, 0, self.realType.SENDTYPE['거래구분']['지정가'], order_num]
                    )

                    if order_success == 0:
                        self.logging.logger.debug("매수취소 전달 성공")
                    else:
                        self.logging.logger.debug("매수취소 전달 실패")

                elif not_quantity == 0:
                    del self.not_account_stock_dict[order_num]


    # 실시간 체결 정보
    def chejan_slot(self, sGubun, nItemCnt, sFidList):

        if int(sGubun) == 0: #주문체결
            account_num = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['계좌번호'])
            sCode = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['종목코드'])[1:]
            stock_name = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['종목명'])
            stock_name = stock_name.strip()

            origin_order_number = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['원주문번호'])  # 출력 : defaluse : "000000"
            order_number = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['주문번호'])  # 출럭: 0115061 마지막 주문번호

            order_status = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['주문상태'])  # 출력: 접수, 확인, 체결
            order_quan = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['주문수량'])  # 출력 : 3
            order_quan = int(order_quan)

            order_price = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['주문가격'])  # 출력: 21000
            order_price = int(order_price)

            not_chegual_quan = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['미체결수량'])  # 출력: 15, default: 0
            not_chegual_quan = int(not_chegual_quan)

            order_gubun = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['주문구분'])  # 출력: -매도, +매수
            order_gubun = order_gubun.strip().lstrip('+').lstrip('-')

            chegual_time_str = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['주문/체결시간'])  # 출력: '151028'

            chegual_price = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['체결가'])  # 출력: 2110  default : ''
            if chegual_price == '':
                chegual_price = 0
            else:
                chegual_price = int(chegual_price)

            chegual_quantity = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['체결량'])  # 출력: 5  default : ''
            if chegual_quantity == '':
                chegual_quantity = 0
            else:
                chegual_quantity = int(chegual_quantity)

            current_price = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['현재가'])  # 출력: -6000
            current_price = abs(int(current_price))

            first_sell_price = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['(최우선)매도호가'])  # 출력: -6010
            first_sell_price = abs(int(first_sell_price))

            first_buy_price = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['주문체결']['(최우선)매수호가'])  # 출력: -6000
            first_buy_price = abs(int(first_buy_price))

            ######## 새로 들어온 주문이면 주문번호 할당
            if order_number not in self.not_account_stock_dict.keys():
                self.not_account_stock_dict.update({order_number: {}})

            self.not_account_stock_dict[order_number].update({"종목코드": sCode})
            self.not_account_stock_dict[order_number].update({"주문번호": order_number})
            self.not_account_stock_dict[order_number].update({"종목명": stock_name})
            self.not_account_stock_dict[order_number].update({"주문상태": order_status})
            self.not_account_stock_dict[order_number].update({"주문수량": order_quan})
            self.not_account_stock_dict[order_number].update({"주문가격": order_price})
            self.not_account_stock_dict[order_number].update({"미체결수량": not_chegual_quan})
            self.not_account_stock_dict[order_number].update({"원주문번호": origin_order_number})
            self.not_account_stock_dict[order_number].update({"주문구분": order_gubun})
            self.not_account_stock_dict[order_number].update({"주문/체결시간": chegual_time_str})
            self.not_account_stock_dict[order_number].update({"체결가": chegual_price})
            self.not_account_stock_dict[order_number].update({"체결량": chegual_quantity})
            self.not_account_stock_dict[order_number].update({"현재가": current_price})
            self.not_account_stock_dict[order_number].update({"(최우선)매도호가": first_sell_price})
            self.not_account_stock_dict[order_number].update({"(최우선)매수호가": first_buy_price})

        elif int(sGubun) == 1: #잔고

            account_num = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['잔고']['계좌번호'])
            sCode = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['잔고']['종목코드'])[1:]

            stock_name = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['잔고']['종목명'])
            stock_name = stock_name.strip()

            current_price = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['잔고']['현재가'])
            current_price = abs(int(current_price))

            stock_quan = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['잔고']['보유수량'])
            stock_quan = int(stock_quan)

            like_quan = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['잔고']['주문가능수량'])
            like_quan = int(like_quan)

            buy_price = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['잔고']['매입단가'])
            buy_price = abs(int(buy_price))

            total_buy_price = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['잔고']['총매입가']) # 계좌에 있는 종목의 총매입가
            total_buy_price = int(total_buy_price)

            meme_gubun = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['잔고']['매도매수구분'])
            meme_gubun = self.realType.REALTYPE['매도수구분'][meme_gubun]

            first_sell_price = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['잔고']['(최우선)매도호가'])
            first_sell_price = abs(int(first_sell_price))

            first_buy_price = self.dynamicCall("GetChejanData(int)", self.realType.REALTYPE['잔고']['(최우선)매수호가'])
            first_buy_price = abs(int(first_buy_price))

            if sCode not in self.jango_dict.keys():
                self.jango_dict.update({sCode:{}})

            self.jango_dict[sCode].update({"현재가": current_price})
            self.jango_dict[sCode].update({"종목코드": sCode})
            self.jango_dict[sCode].update({"종목명": stock_name})
            self.jango_dict[sCode].update({"보유수량": stock_quan})
            self.jango_dict[sCode].update({"주문가능수량": like_quan})
            self.jango_dict[sCode].update({"매입단가": buy_price})
            self.jango_dict[sCode].update({"총매입가": total_buy_price})
            self.jango_dict[sCode].update({"매도매수구분": meme_gubun})
            self.jango_dict[sCode].update({"(최우선)매도호가": first_sell_price})
            self.jango_dict[sCode].update({"(최우선)매수호가": first_buy_price})

            if stock_quan == 0:
                del self.jango_dict[sCode]