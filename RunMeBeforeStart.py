#==========輸入數字=========#
canGo = False
TotalStudentNum = 0
while canGo == False:
    TotalStudentNum = input("有幾個學生(必須>=4)？\n")#>=4才能有正常數量的打掃股長&做Json時會正常執行
    
    try:
        TotalStudentNum = int(TotalStudentNum)
        if TotalStudentNum <= 4:
            print("必須>=4人！\n我想小班級應該用不到我")
        else:
            ConfirmWord = input("確定有 %i 個學生？(Y:對/其他字:錯)\n"%TotalStudentNum)
            if ConfirmWord != "Y":
                print("重新輸入！")
            else:
                canGo = True
    except:
        print("輸入數字！")
#==========================#   
      

#==========更新人數=========#
print("\n\n開始更新人數...")

#因為import要輸入程式名，不能用sring，所以只能土法煉鋼
import 製作座號JSON as NumJSON
NumJSON.make(TotalStudentNum)
import 製作打掃股長選擇JSON as CleaningJSON
CleaningJSON.make(TotalStudentNum)
import 製作重選管理員JSON as RechoodeManagerJSON
RechoodeManagerJSON.make(TotalStudentNum)
import 製作管理員加扣分JSON as ManagerEditPointJSON
ManagerEditPointJSON.make(TotalStudentNum)
import 製作選替代打掃股長JSON as ChooseReplaceCleaningJSON
ChooseReplaceCleaningJSON.make(TotalStudentNum)
import 製作選擇打掃成員JSON as ChooseFellowJSON
ChooseFellowJSON.make(TotalStudentNum)
#==========================#   

#====更新UnRegisterUser====#
#設定redis物件
import configparser
import redis
config = configparser.ConfigParser()
config.read('config.ini')
rds = redis.Redis(
host = config.get('redis','host'),
port = int(config.get('redis','port')),
password = config.get('redis','password')
)
#紀錄有幾個學生 
rds.set("TotalStudentNum",TotalStudentNum)

print("fin redis TotalStudentNum\n")
#==========================#   

#====更新googlrSheet====#
#設定google sheet
from oauth2client.service_account import ServiceAccountCredentials as SAC
import gspread
GDriveJSON = config.get('google-sheet','GDriveJSON')#GDriveJSON就輸入下載下來Json檔名稱
GSpreadSheet = config.get('google-sheet','GSpreadSheet') #GSpreadSheet是google試算表名稱

scope = ['https://www.googleapis.com/auth/drive']#定義存取的Scope(範圍)，也就是Google Sheet
key = SAC.from_json_keyfile_name(GDriveJSON, scope)
gc = gspread.authorize(key)
worksheet = gc.open(GSpreadSheet).sheet1#sheet1指第一個sheet

for i in range(1,TotalStudentNum+1):
    worksheet.append_row((i,80))
    print("fin google sheet set %i/%i"%(i,TotalStudentNum))
#==========================# 

print("\n\n人數更新結束")