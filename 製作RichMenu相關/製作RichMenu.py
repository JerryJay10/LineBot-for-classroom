import requests
import json
import sys
import os
from PIL import Image,ImageDraw
from linebot import (
    LineBotApi, WebhookHandler
)
from tkinter import filedialog
import configparser
import math





#製作圖片
def MakeBlankPic():
    RichMenu = Image.new( "RGB", (2500,Height))
    draw = ImageDraw.Draw(RichMenu) 
    draw.rectangle([(0,0),(2500,Height)], fill="#865fbf")#整張塗紫
    return RichMenu


#貼Icon
def PasteIcons(RichMenu,ClickState):    
    for m in range(0,IconLayer):        
        for i in range(0,3):
            oldPartName = IconNameList[m][i]
            if ClickState == "Clicked" and ClickedIcon != oldPartName:#Clicked時要把其他的換CantClick才可
                PartName = "CantClick" + "_" + oldPartName
            else:
                PartName = ClickState + "_" + oldPartName
            Part = Image.open("C:/LineBot/製作RichMenu相關/" + PartName)
            if ClickState == "UnClick":#Unclick 要凸出來
                RichMenu.paste(Part,(30 + 815*i,30 + 788*m))#788是原寬(843) 減掉 一個空隙寬(55)，才會維持空隙相同
            else:
                RichMenu.paste(Part,(55 + 815*i,55 + 788*m))
    return RichMenu


#設定RichMenu新名子 + 儲存圖片
def SetNewName_SaveRichMenu(RichMenu,ClickState):
    newName = ""
    if ClickState == "UnClick":
        newName = name
    elif ClickState == "CantClick":
        newName = "FinishTo"+ name
    else:#Clicked(需ClickedIcon全域變數)
        newName = name + ClickedIcon.rstrip("png").rstrip(".") + ClickState #名子都有.png，要去除
    RichMenu.save("RM_%s.png"%newName,quality=100)
    return newName


#輸入PostBack Data + 紀錄於config
def GetPostBackData(ClickState):
    config.add_section("RM_%s"%name)#要先家section才可
    DataArea = []
    for m in range(0,IconLayer):        
        for i in range(0,3):
            if ClickState == "UnClick":#要輸入PostBack，其他就不用了(但RichMenu不能沒有area，所以仍要加東西)
                BackData = IconNameList[m][i].rstrip("png").rstrip(".")#名子都有.png，要去除
                DataArea.append({
                                "bounds": {"x": 30 + 815*i, "y": 30 + 788*m, "width": 785, "height": 758},
                                "action": {"type": "postback","data":BackData}
                                })
                config.set("RM_%s"%name, "data%i"%(i+m*3), BackData)#紀錄Data
            else:
                DataArea.append({
                                "bounds": {"x": 55 + 815*i, "y": 55 + 788*m, "width": 785, "height": 758},
                                "action": {"type": "postback","data":"0"}#空的(data必須塞東西，所以放0)
                                })
                config.set("RM_%s"%name, "data%i"%(i+m*3), "0")#紀錄Data
    return DataArea


#申請RichMenu + 記錄其Id + 設定RichMenu圖片 
def RegisterRichMneu():
    body = {
        "size": {"width": 2500, "height": Height},
        "selected": "true",
        "name": name,
        "chatBarText": "點我開關選單",
        "areas":DataArea
      }
    req = requests.request('POST', 'https://api.line.me/v2/bot/richmenu', 
                           headers=headers,data=json.dumps(body).encode('utf-8'))
    print("richMenuId : " + req.text)
    Id = req.text[15:].rstrip("\"}")#get RichMenu Id
    config.set("RM_%s"%name, "Id", Id)#紀錄Id
    with open("RM_%s.png"%name, 'rb') as f:#打開之前做好的RichMenu圖
        line_bot_api.set_rich_menu_image(Id, "image/png", f)#設定圖片
    


    
    

#準備記錄檔
config = configparser.ConfigParser()
config.read('C:/LineBot/config.ini',encoding="utf-8")#要用在上一層的config


#準備LineBot資料
channel_access_token = config.get('line-bot','channel_access_token')
line_bot_api = LineBotApi(channel_access_token)#放channel_access_token
headers = {"Authorization":"Bearer %s"%channel_access_token,"Content-Type":"application/json"}


#要大的還是小的RichMenu(改變高度與層數)
BigOrSmall = input("Big(B) or Small(S)?")
if (BigOrSmall ==  "B" ) or (BigOrSmall == "b"): 
    Height = 1631 #1631 = 843*2 - 55
    IconLayer = 2
else:#小的
    Height = 843
    IconLayer = 1


#Get所有Icon名子 + RichMenu名子
print("選要的CantClick的Icon")
IconNameList = [[0 for _ in range(3)] for _ in range(IconLayer)]
for m in range(IconLayer):        
    for i in range(0,3):
        file_path = filedialog.askopenfilename()#get file path
        Parts = Image.open(file_path)
        PartsName = Parts.filename.lstrip("C:/LineBot/製作RichMenu相關/CantClick")#get Icon名字
        PartsName = PartsName.lstrip("_")#lstrip是從左邊數來，只要有在指定字串中有出線的字元，就會被刪掉，刪到沒出現1次為止，所以不這樣寫了話會有誤刪情形
        IconNameList[m][i] = PartsName
        print(PartsName)
originalName = input("Name?")

    
Check = False
for i in range(0,3*IconLayer + 2):
    name = originalName#name會被做很多改變，要每次重置
    #分別要做什麼RichMenu
    if i == 0:
        ClickState = "UnClick"
    elif i == 1:
        ClickState = "CantClick"
    else:
        ClickState = "Clicked"#因ClickedState有做於找Icon圖片，不可編號
        ClickedIcon = IconNameList[math.floor((i-2)/3)][(i-2)%3]#找到Icon名子(i的+2要扣回來)
        
    #做UnClickRM
    RichMenu = MakeBlankPic()#製作空白圖片
    RichMenu = PasteIcons(RichMenu, ClickState)
    
    #確認一下排列是否正確
    if Check == False:      
        RichMenu.show()
        isOK = input("OK(Y/N)?")
        if (isOK ==  "N" ) or (isOK == "n"):
            sys.exit()#結束程式
        Check = True
    
    #做完UnClickRM圖片
    name = SetNewName_SaveRichMenu(RichMenu, ClickState)
    
    #弄出PostBack Data + 紀錄於config 
    DataArea = GetPostBackData(ClickState)
    
    #申請RichMenu + 記錄其Id + 設定RichMenu圖片 
    RegisterRichMneu()
        
    print("fin save and Make %i/%i"%(i+1,3*IconLayer + 2))


#總儲存config
config.write(open("C:/LineBot/config.ini", "w"))#要用在上一層的config