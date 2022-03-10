import os
#==========輸入數字=========#
canGo = False
TotalStudentNum = 0
while canGo == False:
    TotalStudentNum = input("有幾個學生(必須>=4)？\n")#>=4才能有正常數量的打掃股長&做Json時會正常執行
    
    try:
        TotalStudentNum = int(TotalStudentNum)
        if TotalStudentNum <= 4:
            os.system("echo 必須>=4人！")
            os.system("echo 我想小班級應該用不到我")
        else:
            ConfirmWord = input("確定有 %i 個學生？(Y:對/其他字:錯)\n"%TotalStudentNum)
            if ConfirmWord != "Y":
                os.system("echo 重新輸入！")
            else:
                canGo = True
    except:
        os.system("echo 輸入數字！")
#==========================#   
      
#=========下載函式庫=========#
os.system("echo .")
os.system("echo .")
os.system("echo 開始下載必要函式庫...")

os.system("echo .")
os.system("pip install redis")
os.system("echo fin download redis API")
os.system("echo .")
os.system("pip install oauth2client")
os.system("echo fin download oauth2client API")
os.system("echo .")
os.system("pip install gspread")
os.system("echo fin download gspread API")
os.system("echo .")
os.system("pip install line-bot-sdk")
os.system("echo fin download linebot SDK")
os.system("echo .")
os.system("pause")
os.system("echo .")
os.system("echo 函式庫下載完成...")
os.system("echo .")
os.system("echo .")
#==========================#

#==========更新人數=========#
os.system("echo .")
os.system("echo .")
os.system("echo 開始更新人數...")

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
config.read('config.ini', encoding="utf-8")
rds = redis.Redis(
host = config.get('redis','host'),
port = int(config.get('redis','port')),
password = config.get('redis','password')
)
#紀錄有幾個學生 
rds.set("TotalStudentNum",TotalStudentNum)

os.system("echo fin redis TotalStudentNum")
#==========================#   
os.system("echo .")
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

worksheet.update("A1","號碼")
worksheet.update("B1","分數")
for i in range(1,TotalStudentNum+1):
    worksheet.append_row((i,80))
    os.system("echo fin google sheet set %i/%i"%(i,TotalStudentNum))
#==========================# 
os.system("echo .")
#=====更新RichMenu的Id=====#
#imprt東西
from linebot import (LineBotApi)
import requests
import json
#準備LineBot資料
channel_access_token = config.get('line-bot','channel_access_token')
line_bot_api = LineBotApi(channel_access_token)#放channel_access_token
headers = {"Authorization":"Bearer %s"%channel_access_token,"Content-Type":"application/json"}

#製作開始
total = len(config.sections())#有3個區域非RichMenu
count = 0
for sectionName in config.sections():
    if "RM" in sectionName:#是RichMenu
    
        #要大的還是小的RichMenu(改變高度與層數)
        if config.has_option(sectionName,'data5'):#有data5的都是大RichMenu
            Height = 1631 #1631 = 843*2 - 55
            IconLayer = 2
        else:#小的
            Height = 843
            IconLayer = 1
        
        #分別要做什麼RichMenu(只要之盪是不是UClick即可)
        if "Clicked" not in sectionName and "Finish" not in sectionName:
            ClickState = "UnClick"
        else:
            ClickState = "NotUnClicked"
        
        #找回Icon名
        nowIconNames = []
        for key_value in config.items(sectionName):
            if key_value[0] != "id":#key不是id
                nowIconNames.append(key_value[1])#加value，也就是名子

        #弄出PostBack Data(不用紀錄於config) 
        DataArea = []
        for m in range(0,IconLayer):        
            for i in range(0,3):
                if ClickState == "UnClick":#要輸入PostBack，其他就不用了(但RichMenu不能沒有area，所以仍要加東西)
                    BackData = nowIconNames[i+m*3]
                    DataArea.append({
                                    "bounds": {"x": 30 + 815*i, "y": 30 + 788*m, "width": 785, "height": 758},
                                    "action": {"type": "postback","data":BackData}
                                    })
                else:
                    DataArea.append({
                                    "bounds": {"x": 55 + 815*i, "y": 55 + 788*m, "width": 785, "height": 758},
                                    "action": {"type": "postback","data":"0"}#空的(data必須塞東西，所以放0)
                                    })
             
        #申請RichMenu + 記錄其Id + 設定RichMenu圖片 
        body = {
            "size": {"width": 2500, "height": Height},
            "selected": "true",
            "name": sectionName.lstrip("RM").lstrip("_"),
            "chatBarText": "點我開關選單",
            "areas":DataArea
          }
        req = requests.request('POST', 'https://api.line.me/v2/bot/richmenu', 
                               headers=headers,data=json.dumps(body).encode('utf-8'))
        os.system("echo richMenuId : " + req.text)
        Id = req.text[15:].rstrip("\"}")#get RichMenu Id
        config.set(sectionName, "Id", Id)#紀錄Id
        with open("製作RichMenu相關/%s.png"%sectionName, 'rb') as f:#打開之前做好的RichMenu圖
            line_bot_api.set_rich_menu_image(Id, "image/png", f)#設定圖片
            
    #記數
    count = count + 1
    os.system("echo fin RichMenu Id change %s/%s"%(count,total))
#======================#
os.system("echo .")
os.system("echo .")
os.system("echo 人數更新結束")
os.system("echo .")
os.system("pause")