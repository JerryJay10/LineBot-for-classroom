from flask import Flask, request, abort,redirect
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage,TemplateSendMessage,ButtonsTemplate,ConfirmTemplate,PostbackEvent,PostbackTemplateAction,FlexSendMessage,FollowEvent,UnfollowEvent 
from oauth2client.service_account import ServiceAccountCredentials as SAC
import datetime
import gspread
import configparser
import urllib
import json
import redis
import time
import random


app = Flask(__name__)


# 取得config記事本裡的 LINE 聊天機器人基本資料
config = configparser.ConfigParser()
config.read('config.ini',encoding="utf-8")#encoding一定要加，不然會當機


line_bot_api = LineBotApi(config.get('line-bot','channel_access_token'))
handler = WebhookHandler(config.get('line-bot','channel_secret'))
herokuApp_name = config.get('line-bot','herokuApp_name')


# 接收 LINE 的資訊
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']

    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    try:
        print(body, signature)
        handler.handle(body, signature)
        
    except InvalidSignatureError:
        abort(400)

    return 'OK'


#Line Notify第一階段，產生授權網址
client_id = "4XVFGLChmjufoud813nheA"
client_secret = 'YJ9LmymadKN5AOmU85u7DY0gOayv0jsZYfBW6jOnmpP'
redirect_uri = "https://%s.herokuapp.com/callback/notify"%herokuApp_name

def create_auth_link(Id, client_id=client_id, redirect_uri=redirect_uri):
    data={
        'response_type': 'code', 
        'client_id': client_id, 
        'redirect_uri': redirect_uri, 
        'scope': 'notify', 
        'state': Id#此可為任何資料([]的資料不行，不知原因)，此處用於船user_id
        }
    query_str = urllib.parse.urlencode(data)
    return f'https://notify-bot.line.me/oauth/authorize?{query_str}'

#Line Notify第二，三階段，使用者完成授權網址的連動後，LINE Notify 會將 Code 和 State 等資料與使用者送到 Redirect URI，也就是此函式
@app.route("/callback/notify", methods=['GET'])
def callback_nofity():
    #assert request.headers['referer'] == 'https://notify-bot.line.me/'#確認是從 LINE Notify 發送過來的資料(不知why IOS不是，反正不檢查應該沒事)
    code = request.args.get('code')#Get code
    
    Id = request.args.get('state')#get state(user_id)
    
    # 第三階段函式(用code去get access_token)
    access_token = get_token(code)#其他三項已有，只要code就好

    
    #StoreToken
    if Id[0] == "U":#註冊User
        rds.hset("user:%s"%Id,"access_token",access_token)      
        send_message(access_token, "設定完成LineNotify了!!!")#這裡如果Notify已有加入群組，群組又被選到，就會發訊，我想不到更好的方法，只能等全班註冊完再加到班群
        password = random.randrange(0,9999)
        rds.hset("user:%s"%Id,"password",password)
        send_message(access_token, "密碼：%i"%password)
        time.sleep(1)
        actList = [PostbackTemplateAction(label='我沒收到密碼...',data='start&Notify')] 
        line_bot_api.push_message(Id,TemplateSendMessage(alt_text='3.輸入密碼',template=ButtonsTemplate(title = "3.輸入密碼",text="請用訊息告訴我，剛剛Notify傳的密碼是(把密碼本體打出來即可)？",actions = actList)))#alt_text也會出現在跳出的視窗，所以必須改
        rds.hset("user:%s"%Id,"step",3)#前進一步
        return '<h1>恭喜完成 LINE Notify 連動！請關閉此視窗。</h1>'#使用者會看到的網頁
    else:#註冊group#只有第一個管理者(發註冊開始的人)才可拿到註冊Group的Link
        summary = line_bot_api.get_group_summary(Id)
    
        things = {
        "access_token":access_token,
        "name":summary.group_name
        } 
        rds.hmset("group",things)
        send_message(access_token, "全部人都註冊完了!謝謝大家的配合!")
        return '<h1>恭喜完成 LINE Notify Group連動！請關閉此視窗。</h1>'#使用者會看到的網頁
    
    

#Line Notify第三階段，用code去get access_token
def get_token(code, client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri):
    url = 'https://notify-bot.line.me/oauth/token'
    headers = { 'Content-Type': 'application/x-www-form-urlencoded' }
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri,
        'client_id': client_id,
        'client_secret': client_secret
        }
    data = urllib.parse.urlencode(data).encode()#把所有需要data準備好
    req = urllib.request.Request(url, data=data, headers=headers)#傳送資料到 LINE Notify
    page = urllib.request.urlopen(req).read()#讀取 LINE Notify 回傳的資料
    
    res = json.loads(page.decode('utf-8'))#回傳的資料用json.loads轉換為字典物件
    return res['access_token']#讀取字典其中一個key(access_token)

#Line Notify第四階段，有access_token就可以傳訊息了
def send_message(access_token, text_message):
    url = 'https://notify-api.line.me/api/notify'
    headers = {"Authorization": "Bearer "+ access_token}

    data = {'message': text_message}#Line Notify必須傳文字訊息，所以"message"必須有

    data = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=data, headers=headers)
    page = urllib.request.urlopen(req).read()





#設定redis物件
rds = redis.Redis(
host = config.get('redis','host'),
port = int(config.get('redis','port')),
password = config.get('redis','password')
)

#因為heroku多端執行，rpush指令會被重複執行(我都是被重複兩次)，所以先push任意值，再改成想要的值才行#似乎在更新後沒問題了(不確定是不是This means that TLS v1.0 and v1.1 are no longer supported by clients using OpenSSL to make outbound requests造成)
def rdsRpush(Goal,Word):       
    rds.rpush(Goal,Word)#任意值(這裡用「龘」字)
    #realEnd = rds.llen(Goal) - 2#因為重複兩次，所以-2就是End沒錯
    #rds.lset(Goal, realEnd, Word)
    #rds.lrem(Goal, 0, "0")#把所有「龘」刪掉(代表list不能有「龘」字)，醬就不會產生任何影響
    

        

#set 資料(存於redis中)，每一次push heroku main就會檢查一次
def setData():
    if rds.exists("DoReport") == False:
        rds.set("DoReport",1)#0是False
    if rds.exists("DoBroadcast") == False:
        rds.set("DoBroadcast",1)#0是False  
    if rds.exists("UnRegisterUser") == False and not rds.exists("HaveStarted"):#如果list沒東西就算是沒有exists！須限制
        if rds.exists("TotalStudentNum") == True: #在還沒RunMeBeforeStart前上傳Heroku就會出錯，所以限制
            TotalStudentNum = int(rds.get("TotalStudentNum").decode("utf-8"))
            for i in range(1,TotalStudentNum+1):
                rdsRpush("UnRegisterUser",i)
            rdsRpush("UnRegisterUser","師")
    if rds.exists("ReceiveBroadcastEditText") == False:
        rds.set("ReceiveBroadcastEditText",0)#0是False
        rds.set("BroadcastEditArea","Earth")
        rds.set("BroadcastEditNum",2021)
setData()
#文字部分不會受重新開始干擾
if rds.exists("BroadcastWord:打掃") == False:
    rdsRpush("BroadcastWord:打掃","打掃，偷懶重訓")
    rdsRpush("BroadcastWord:打掃","不想愛校就乖乖打掃")
    rdsRpush("BroadcastWord:打掃","請移動您尊貴的臀部執行打掃工作")
    rdsRpush("BroadcastWord:打掃","打掃 ! 打掃長肌肉")
    rdsRpush("BroadcastWord:打掃","打掃 ! 蓄積實力，打倒邪惡資本家!")
    rdsRpush("BroadcastWord:打掃","掃具在手 ! 跟股長走 ! 打掃 !")
    rdsRpush("BroadcastWord:打掃","我們無產階級，靠掃地崛起 ! 打掃!")
    rdsRpush("BroadcastWord:打掃","一日不打掃，三日惡臭。打掃 !")
    rdsRpush("BroadcastWord:打掃","掃地 ! 掃地 ! 掃地 !")
    rdsRpush("BroadcastWord:打掃","拜託掃地 ! 掃地的人都是好人")
if rds.exists("BroadcastWord:午休") == False:
    rdsRpush("BroadcastWord:午休","收手機睡覺")
    rdsRpush("BroadcastWord:午休","誰想要重訓啊 ?")
    rdsRpush("BroadcastWord:午休","你很.累.了，好..想..睡...覺...")
    rdsRpush("BroadcastWord:午休","疲憊，勞累，很..想..睡...覺...")
    rdsRpush("BroadcastWord:午休","還有4節課，好累，睡...覺...吧.")
    rdsRpush("BroadcastWord:午休","好忙，好多事，睡...一...下....")
    rdsRpush("BroadcastWord:午休","不睡覺練肌肉")
    rdsRpush("BroadcastWord:午休","睡.覺..睡...覺....睡......ㄐ.")
    rdsRpush("BroadcastWord:午休","你可以休..息..了...睡...吧...")
    rdsRpush("BroadcastWord:午休","睡.............覺...........")
        



#設定google sheet
GDriveJSON = config.get('google-sheet','GDriveJSON')#GDriveJSON就輸入下載下來Json檔名稱
GSpreadSheet = config.get('google-sheet','GSpreadSheet') #GSpreadSheet是google試算表名稱

scope = ['https://www.googleapis.com/auth/drive']#定義存取的Scope(範圍)，也就是Google Sheet
key = SAC.from_json_keyfile_name(GDriveJSON, scope)
gc = gspread.authorize(key)
worksheet = gc.open(GSpreadSheet).sheet1#sheet1指第一個sheet


    


@handler.add(MessageEvent, message=TextMessage)# 在此接收訊息事件，回傳值事件(postback)要在下面DataReply接收
def reply(event):
    ReplyText = event.message.text    
    try:#只有group才可用指令
        group_id = event.source.group_id
        user_id = event.source.user_id
        
        if ReplyText == "設定開始!!":#註冊Start#(可用於大家都有註冊一次後)
            if not rds.exists("HaveStarted"):#只能用一次
                rds.set("HaveStarted","1")
                rdsRpush("Manager_Id",user_id)#發送者就會獲得管理權
                rds.hset("group","group_id",group_id)
                
                line_bot_api.reply_message(event.reply_token, TextSendMessage("大家好啊！麻煩大家跟我加好友！\n\n幫助我們不要到現在還在用「紙」「紙」這種19XX年前的骨董來紀錄打掃情況！"))
                FlexMessage = json.load(open('座號選擇.json','r',encoding='utf-8'))
                line_bot_api.broadcast(FlexSendMessage('註冊開始!!',FlexMessage))#傳給已是好友的人
            
        elif ReplyText == "Beta測試開始!!":#beta測試，就是把UnRegisterUser改為3個人，其他不變(可用於大家都有註冊一次後)
            if not rds.exists("HaveStarted"):#只能用一次
                rds.set("HaveStarted","1")
                rds.delete("UnRegisterUser")
                rdsRpush("UnRegisterUser",10)
                rdsRpush("UnRegisterUser",19)
                rdsRpush("UnRegisterUser","師")
                
                rdsRpush("Manager_Id",user_id)#發送者就會獲得管理權
                rds.hset("group","group_id",group_id)
                
                line_bot_api.reply_message(event.reply_token, TextSendMessage("大家好啊！麻煩大家跟我加好友！\n(如果已經是好友就不用了)\n\n幫助我們不要到2021年還在用「紙」這種19XX年前的骨董來紀錄打掃情況！"))
                FlexMessage = json.load(open('座號選擇.json','r',encoding='utf-8'))
                line_bot_api.broadcast(FlexSendMessage('註冊開始!!',FlexMessage))#傳給已是好友的人
                
        
            
    except:#只有單人才可用指令
        user_id = event.source.user_id
    
        NowTime = datetime.datetime.now()   #get現在時間
                
        
        
        if rds.hexists("user:%s"%user_id,"step") and rds.hget("user:%s"%user_id,"step").decode("utf-8") == "3":#第四步，LineNotify確認密碼(因為LineNotify的accessToken無規律，LineBot也看不到Notify的訊息，無法確認是否正確註冊到一對一，所以只好人工確認) #ReplyTest即為密碼
            password = ReplyText.rstrip().lstrip()#他們預設是刪除空白
            actList = [PostbackTemplateAction(label='確定',data='start&ConfirmNotify&YES&%s'%password) , PostbackTemplateAction(label='手殘打錯',data='start&ConfirmNotify&NO')] 
            line_bot_api.reply_message(event.reply_token,TemplateSendMessage(alt_text='4.確認密碼',template=ConfirmTemplate(text='4.確認密碼\n\n密碼是%s嗎？'%password,actions = actList)))
            rds.hset("user:%s"%user_id,"step",4)#前進一步
                
                    
       
        if int(rds.get("ReceiveBroadcastEditText")) and rds.hget("user:%s"%user_id,"step").decode("utf-8") == "ㄈ(1)":#編輯廣播文字的ㄈ-1步，要接收文字，所以寫此
            EditArea = rds.get("BroadcastEditArea").decode("utf-8")
            EditNum = rds.get("BroadcastEditNum").decode("utf-8")
            rds.lset("BroadcastWord:%s"%EditArea,int(EditNum),ReplyText)#編輯完成
            line_bot_api.push_message(user_id,TextSendMessage("修改完成 !"))#為了順暢體驗用push
            #回到ㄇ(1)步(懶了寫函式)
            BroadcastWordJSONMaking(EditArea)#製作JSON
            FlexMessage = json.load(open('廣播文字編輯器.json','r',encoding='utf-8'))
            line_bot_api.reply_message(event.reply_token, FlexSendMessage('ㄇ(1).文字編輯',FlexMessage))
            rds.hset("user:%s"%user_id,"step","ㄇ(1)")#前進到ㄇ(1)
            rds.set("ReceiveBroadcastEditText",0)#要改回來才可
        
        
        if ReplyText == "確認註冊情形":
            finalword = ""
            if rds.exists("Cleaning_Id"):
                cleaning_id = "打掃三股長user_id="+str(rds.lrange("Cleaning_Id", 0, -1))
                finalword = finalword + cleaning_id+"\n"
                tokens=[]
                for i in rds.lrange("Cleaning_Id", 0, -1):
                    Id = i.decode("utf-8")
                    if rds.hexists("user:%s"%Id,"access_token"):
                        tokens.append(rds.hmget("user:%s"%Id,"access_token")[0].decode('utf-8'))
                cleaning_token = "打掃三股長access_token="+str(tokens)
                finalword = finalword + cleaning_token+"\n\n"
                  
            if rds.exists("Teacher_Id"):
                Id =  rds.get("Teacher_Id").decode("utf-8")
                teacher_id = "老師user_id=" + Id
                finalword = finalword + teacher_id+"\n"
                tokens=[]
                if rds.hexists("user:%s"%Id,"access_token"):
                    teacher_token = "老師access_token="+rds.hmget("user:%s"%Id,"access_token")[0].decode('utf-8')
                    finalword = finalword + teacher_token+"\n\n"
            
            student_word = ""
            TotalStudentNum = int(rds.get("TotalStudentNum").decode("utf-8"))
            for i in range(1,TotalStudentNum+1):
                if rds.hexists("Number_Id", str(i)):
                    student_id = rds.hmget("Number_Id", str(i))[0].decode('utf-8')
                    student_word = student_word + "%i號user_id="%i + student_id +"\n"
                    if rds.hexists("user:%s"%student_id,"access_token"):
                        student_token = rds.hmget("user:%s"%student_id,"access_token")[0].decode('utf-8')
                        student_word = student_word + "%i號access_token="%i + student_token +"\n"
            student_word = student_word.rstrip()
            finalword = finalword + student_word
                
            line_bot_api.reply_message(event.reply_token,TextSendMessage("結果如下:\n"+finalword))
        
        
        
        elif ReplyText == "確認大家分數":
            student_score = ""
            TotalStudentNum = int(rds.get("TotalStudentNum").decode("utf-8"))
            for i in range(1,TotalStudentNum+1):
                ExcelNum = i + 1#1號在B2格
                Score = worksheet.get("B%i"%ExcelNum).first()
                student_score = student_score + "%i號有 "%i + Score +" 分\n"
            student_score = student_score.rstrip()
            line_bot_api.reply_message(event.reply_token,TextSendMessage("大家分數如下:\n"+student_score+"\n\n附贈的PDF檔:\nhttps://docs.google.com/spreadsheets/d/1frVT_AvqGiZKkZQMBFYkS6twj2tMNbPSdXJjJ0FGyPM/export?format=pdf"))
                

            
        
        elif ReplyText == "RealTest":      
            test = "1"
            line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%test))
        elif ReplyText == "RealTestOff": 
            rds.delete("UnRegisterUser")
            rdsRpush("UnRegisterUser",10)
            rds.lrem("UnRegisterUser",0,10)
            test = "0"
            line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%test))          
        elif ReplyText == "ReportTest":
            CleaningCheckOn()
            line_bot_api.reply_message(event.reply_token,TextSendMessage("Ok on"))
        elif ReplyText == "ReportTestOff":
            CleaningCheckOff()
            line_bot_api.reply_message(event.reply_token,TextSendMessage("Ok off"))            
            
        elif ReplyText == "ResetRichMenu1":
            for i in rds.hkeys("Number_Id"):
                Id = rds.hget("Number_Id",i.decode("utf-8")).decode("utf-8")
                line_bot_api.link_rich_menu_to_user(Id,config.get("RM_MiddleNormal","id"))
                rds.hdel("user:%s"%i,"UsingRichMenu")
            line_bot_api.reply_message(event.reply_token,TextSendMessage("Ok fin reset 1"))
        elif ReplyText == "ResetRichMenu2":
            rds.delete("APersonCanUsingRichMenu")
            rds.delete("CleaningChangedNums")#要刪除所有可能的暫存變數
            rds.delete("CleaningChangedNums")#要刪除所有可能的暫存變數
            for i in rds.lrange("Manager_Id", 0, -1):
                Id = i.decode("utf-8")
                line_bot_api.link_rich_menu_to_user(Id,config.get("RM_MiddleManage","id"))
                
            for i in rds.lrange("Cleaning_Id", 0, -1):
                Id = i.decode("utf-8")
                line_bot_api.link_rich_menu_to_user(Id,config.get("RM_MiddleCleaning","id"))       
                rds.delete("QuittingCleaning:%s"%Id)#要刪除所有可能的暫存變數             
                rds.delete("QuittingCleaning:%s"%Id)#要刪除所有可能的暫存變數
            line_bot_api.reply_message(event.reply_token,TextSendMessage("Ok fin reset 2"))

            
        elif ReplyText == "DeleteUsingRichMenu":
            rds.delete("APersonCanUsingRichMenu")
            line_bot_api.reply_message(event.reply_token,TextSendMessage("Ok delete"))
        elif ReplyText == "Export":
            line_bot_api.reply_message(event.reply_token,TextSendMessage("https://docs.google.com/spreadsheets/d/1frVT_AvqGiZKkZQMBFYkS6twj2tMNbPSdXJjJ0FGyPM/export?format=xlsx"))
        elif ReplyText == "SendTest":
            Send()
            line_bot_api.reply_message(event.reply_token,TextSendMessage("Fin send"))
        elif ReplyText == "Delete": 
            rds.delete("OriginalCleaningNum")#刪除暫存變數
            line_bot_api.reply_message(event.reply_token,TextSendMessage("fin del" ))
        elif ReplyText == "ManageTest":
            line_bot_api.reply_message(event.reply_token,TextSendMessage(config.get("RM_MiddleManage","id")))
            line_bot_api.link_rich_menu_to_user(user_id,config.get("RM_MiddleManage","id"))
            rds.hdel("user:%s"%user_id,"UsingRichMenu")
        elif ReplyText == "CleaningTest":
            line_bot_api.reply_message(event.reply_token,TextSendMessage(config.get("RM_MiddleCleaning","id")))
            line_bot_api.link_rich_menu_to_user(user_id,config.get("RM_MiddleCleaning","id"))
            rds.hdel("user:%s"%user_id,"UsingRichMenu")
        elif ReplyText == "BecomeManager":
            rdsRpush("Manager_Id",user_id)
            rds.lrem("Cleaning_Id",0,user_id)
            line_bot_api.reply_message(event.reply_token,TextSendMessage("fin change Manager(del Cleaning)"))
        elif ReplyText == "BecomeCleaning":
            rdsRpush("Cleaning_Id",user_id)
            rds.lrem("Manager_Id",0,user_id)
            line_bot_api.reply_message(event.reply_token,TextSendMessage("fin change Cleaning(del Manager)"))
        elif ReplyText == "Test":              
            line_bot_api.reply_message(event.reply_token,TextSendMessage(config.get("RM_MiddleNormal","id")))
            line_bot_api.link_rich_menu_to_user(user_id, config.get("RM_MiddleNormal","id"))
            rds.hdel("user:%s"%user_id,"UsingRichMenu") 
        elif ReplyText == "Register":
            FlexMessage = json.load(open('座號選擇.json','r',encoding='utf-8'))
            line_bot_api.reply_message(event.reply_token, FlexSendMessage('註冊開始!!',FlexMessage))
        elif ReplyText == "ResetStep":
            rds.hset("user:%s"%user_id,"step","0")
            line_bot_api.reply_message(event.reply_token,TextSendMessage("fin ResetStep"))
        elif ReplyText == "ResetUnRegisterUser":
            rds.delete("UnRegisterUser")
            setData()#把UnRegisterUser用回來
            line_bot_api.reply_message(event.reply_token,TextSendMessage("fin ResetUnRegisterUser"))
        elif ReplyText == "SetToFinishStep":
            rds.hset("user:%s"%user_id,"step","5")
            rds.hdel("user:%s"%user_id,"UsingRichMenu")
            line_bot_api.reply_message(event.reply_token,TextSendMessage("fin SetStep"))
        elif ReplyText == "ForceRestart":   
            Idlist = []
            if rds.exists("Number_Id"):
                for i in rds.hkeys("Number_Id"):
                    Id = rds.hget("Number_Id",i.decode("utf-8")).decode("utf-8")
                    Idlist.append(Id)
            if rds.exists("Teacher_Id"):
                Idlist.append(rds.get("Teacher_Id").decode("utf-8"))
            if len(Idlist) != 0:
                for i in Idlist:#已不會再未註冊完成時做，所以OK              
                    if rds.hexists("user:%s"%i,"access_token"):
                        Token = rds.hget("user:%s"%i,"access_token").decode("utf-8")
                        send_message(Token, "重製作業已啟動，所有服務都會中止")
                        send_message(Token, "真的")
                        send_message(Token, "極其")
                        send_message(Token, "高度")
                        send_message(Token, "非常")
                        send_message(Token, "超級")
                        send_message(Token, "宇宙")
                        send_message(Token, "世紀")
                        send_message(Token, "無敵")              
                        send_message(Token, "萬分")                  
                        send_message(Token, "深深")
                        send_message(Token, "地感謝您的使用。")#要提醒  
                        send_message(Token, "如果真的結束了，請封鎖或退好友Line Bot，才不會收到更多訊息")
                    line_bot_api.unlink_rich_menu_from_user(i)#刪除RichMenu
            SleepBroadcastList = rds.lrange("BroadcastWord:午休", 0, -1)
            CleaningBroadcastList = rds.lrange("BroadcastWord:打掃", 0, -1)
            TotalStudentNum = int(rds.get("TotalStudentNum").decode("utf-8"))
            rds.flushall()#把所有rds刪除
            rds.set("TotalStudentNum",TotalStudentNum)#把學生總數弄回來
            setData()#一開始的rds要弄回來              
            for i in SleepBroadcastList:
                rdsRpush("BroadcastWord:午休", i.decode("utf-8"))#廣播文字的rds要弄回來 
            for i in CleaningBroadcastList:
                rdsRpush("BroadcastWord:打掃", i.decode("utf-8"))#廣播文字的rds要弄回來 
                
            for i in range(1,TotalStudentNum+1):
                ExcelNum = i + 1#1號在B2格
                worksheet.update("B%i"%ExcelNum, 80)#改回原分數

            line_bot_api.reply_message(event.reply_token,TextSendMessage("重置完成了。\n\n發送 註冊開始!! 到群組從頭開始\n\n感謝您的使用"))
        elif ReplyText == "GetLink":     
            group_id = rds.hget("group","group_id").decode("utf-8")
            send_message(rds.hget("user:%s"%user_id,"access_token").decode("utf-8"),"Group_link(請先加入群組再註冊):"+create_auth_link(group_id))
            line_bot_api.reply_message(event.reply_token,TextSendMessage("temporary person linkk:"+create_auth_link(user_id)))
        elif ReplyText == "Wonwon":  
            Token = event.reply_token
            line_bot_api.reply_message(Token,TextSendMessage("OK!"))
            Wonwon(user_id)     
            
        elif ReplyText == "Hour":
            line_bot_api.reply_message(event.reply_token,TextSendMessage(NowTime.hour))
        elif ReplyText == "Minute":
            line_bot_api.reply_message(event.reply_token,TextSendMessage(NowTime.minute))
        elif ReplyText == "Second":
            line_bot_api.reply_message(event.reply_token,TextSendMessage(NowTime.second))
        
        
        elif rds.hexists("user:%s"%user_id,"step") and rds.hget("user:%s"%user_id,"step").decode("utf-8") == "2":#以為要打密碼(測試後人性化修正)
            line_bot_api.reply_message(event.reply_token,TextSendMessage("請再點一次連結，重新連動Notify！"))
        else:#敷衍系統
            if rds.exists("HaveStarted"):#全部重新開始後就不給聊
                if not rds.exists("user:%s"%user_id) or rds.hget("user:%s"%user_id,"number") in rds.lrange("UnRegisterUser",0,-1):
                    line_bot_api.reply_message(event.reply_token,TextSendMessage("請先註冊，不要瞎聊"))
                else:
                    words = ["喔~","摁~","蛤?","好喔","喔。","耶?","...","已讀","笑死","隨便"]
                    line_bot_api.reply_message(event.reply_token,TextSendMessage(words[random.randint(0,9)]))



@handler.add(FollowEvent)# 加好友事件在此接收
def FollowReply(event):
    if rds.exists("HaveStarted"): #開始才發
        FlexMessage = json.load(open('座號選擇.json','r',encoding='utf-8'))
        line_bot_api.reply_message(event.reply_token, FlexSendMessage('註冊開始!!',FlexMessage))#傳給剛加好友的人
    
@handler.add(UnfollowEvent)# 封鎖事件在此接收(相當於刪除帳號)
def UnFollowReply(event):
    if rds.exists("HaveStarted"): #開始才發
        user_id = event.source.user_id  
        if bytes(user_id,"utf-8") in rds.lrange("Manager_Id", 0, -1):#移除管理員身分
            rds.lrem("Manager_Id",0,user_id)
        elif rds.exists("Cleaning_Id") and bytes(user_id,"utf-8") in rds.lrange("Cleaning_Id", 0, -1):#移除打掃股長身分
            num = rds.hget("user:%s"%user_id,"number").decode("utf-8")    
            rds.lrem("Cleaning_Num",0,num)#刪除選擇，不然重複註冊時仍會成為打掃股長
            rds.lrem("Cleaning_Id",0,user_id)
            LeadArea = rds.hget("user:%s"%user_id,"LeadSection").decode("utf-8")
            rds.hdel("user:%s"%user_id,"LeadSection")
            rds.delete("CleaningSection:%s"%user_id)
            rds.delete("CleaningSection:%s"%LeadArea)
            if rds.exists("QuittingCleaning:%s"%user_id):#有可能正在等是否要替代打掃股長，無效他！
                DeleteAskingQuitting(user_id)
            if rds.exists("CleaningTemporaryReplace:%s"%user_id):#有可能正在暫時委託他人做打掃股長
                DeleteTemporaryReplacement(user_id)
            
            FirstManager_id = rds.lindex("Manager_Id", 0).decode("utf-8")
            send_message(rds.hget("user:%s"%FirstManager_id,"access_token").decode("utf-8"),"有打掃股長很沒品地封鎖我了...，麻煩您重選打掃股長！不然股長會從缺！")
            
        if rds.exists("Teacher_Id") and rds.get("Teacher_Id").decode("utf-8") == user_id:#是老師
            rds.delete("Teacher_Id")
            rdsRpush("UnRegisterUser","師")
        else:#同學
            num = rds.hget("user:%s"%user_id,"number").decode("utf-8")    
            rds.hdel("Number_Id", num)                                          
            rdsRpush("UnRegisterUser",num)
        if rds.hexists("user:%s"%user_id,"UsingRichMenu") and rds.exists("APersonCanUsingRichMenu"):
            UsingClickedRichMenu = rds.hget("user:%s"%user_id,"UsingRichMenu").decode("utf-8")
            if bytes(UsingClickedRichMenu,"utf-8") in rds.hkeys("APersonCanUsingRichMenu"):#正在用的是只能一個人用的RcihMenu，要讓別人可以用
                rds.hdel("APersonCanUsingRichMenu",UsingClickedRichMenu)#讓其他人可用
        rds.delete("user:%s"%user_id)
        line_bot_api.unlink_rich_menu_from_user(user_id)#刪除RichMenu
        rds.hdel("user:%s"%user_id,"UsingRichMenu")#要換新RichMenu，把舊的使用紀錄刪除
    
    


@handler.add(PostbackEvent)# 回傳值事件在此接收
def DataReply(event):
    user_id = event.source.user_id  
    ReplyData = event.postback.data
    if rds.hexists("user:%s"%user_id,"step"):#第一次時才不會出問題
        NowStep = rds.hget("user:%s"%user_id,"step").decode("utf-8")#步數系統 
    
    #================================註冊系統==================================#
    #-----------------註冊--------------------#     
    if ReplyData[0:3] == "del":#[0:3]指第0個起到第3個前#重新註冊
        if ReplyData[4:9] == "start":
            if NowStep == "5" or (NowStep == "A" or NowStep == "a"):#完成註冊，或是(正要開始選打掃股長 或 正要開始捲打掃成員)才可用
                if rds.exists("Cleaning_Id") and bytes(user_id,"utf-8") in rds.lrange("Cleaning_Id",0,-1):#是註冊完的打掃股長，需要先交出職位才可刪除帳號(沒註冊完的可)
                    line_bot_api.reply_message(event.reply_token,TextSendMessage("請先交出打掃股長權限再刪帳號\n(先去「不幹打掃股長了」鈕)"))
                else:                   
                    word = '6.你認真要重新註冊?'
                    if bytes(user_id,"utf-8") in rds.lrange("Manager_Id", 0, -1):#是管理員需要額外提醒
                        if rds.llen("Manager_Id") == 1:#只剩一個管理員，不行移除
                            word = word + "\n。只剩您是管理員，權力不移除\n。打掃股長也會留著"
                        else:
                            word = word + "\n。管理員身分會被一起移除\n。打掃股長仍會留著"
                    
                        word = word + "\n。打掃股長身分不會被移除\n(如果)"
                    actList = [PostbackTemplateAction(label='認真的',data='del&do&YES') , PostbackTemplateAction(label='後悔了',data='del&do&NO')] 
                    line_bot_api.reply_message(event.reply_token,TemplateSendMessage(alt_text='快跟我說要不要重新註冊!!',template=ConfirmTemplate(text=word,actions = actList)))
                    rds.hset("user:%s"%user_id,"step",6)#前進一步
                    rds.hset("user:%s"%user_id,"PreStep",NowStep) # 因為開始時可能為5 A a，要特別標記，在6回5的時候才能回到正確的開頭
            else:
                line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
        elif ReplyData[4:6] == "do":#刪除!!
            if NowStep == "6":                
                if ReplyData[7:10] == "YES":
                    if bytes(user_id,"utf-8") in rds.lrange("Manager_Id", 0, -1):#移除管理員身分
                        if rds.llen("Manager_Id") != 1:#只剩一個管理員，不行移除
                            rds.lrem("Manager_Id",0,user_id)
                    elif rds.exists("Cleaning_Id") and bytes(user_id,"utf-8") in rds.lrange("Cleaning_Id", 0, -1):#移除打掃股長身分
                        rds.lrem("Cleaning_Id",0,user_id)
                        LeadArea = rds.hget("user:%s"%user_id,"LeadSection").decode("utf-8")
                        rds.hdel("user:%s"%user_id,"LeadSection")
                        rds.delete("CleaningSection:%s"%user_id)
                        rds.delete("CleaningSection:%s"%LeadArea)
                        if rds.exists("QuittingCleaning:%s"%user_id):#有可能正在等是否要替代打掃股長，無效他！
                            DeleteAskingQuitting(user_id)
                        if rds.exists("CleaningTemporaryReplace:%s"%user_id):#有可能正在暫時委託他人做打掃股長
                            DeleteTemporaryReplacement(user_id)
                    if rds.exists("Teacher_Id") and rds.get("Teacher_Id").decode("utf-8") == user_id:#是老師
                        rds.delete("Teacher_Id")
                        rdsRpush("UnRegisterUser","師")
                    else:#同學
                        num = rds.hget("user:%s"%user_id,"number").decode("utf-8")    
                        rds.hdel("Number_Id", num)                                          
                        rdsRpush("UnRegisterUser",num)
                    rds.delete("user:%s"%user_id)
                    rds.hset("user:%s"%user_id,"step",0)#避免此時以前的步驟被亂點
                    line_bot_api.unlink_rich_menu_from_user(user_id)#刪除RichMenu
                    rds.hdel("user:%s"%user_id,"UsingRichMenu")#要換新RichMenu，把舊的使用紀錄刪除
                    
                    line_bot_api.reply_message(event.reply_token, TextSendMessage("你的資料全部刪好了。有需要就重新再註冊一次吧!"))
                    FlexMessage = json.load(open('座號選擇.json','r',encoding='utf-8'))
                    line_bot_api.push_message(user_id, FlexSendMessage('profile',FlexMessage))
                else:#No
                    word = "不用重新註冊!沒事就好 沒事就好"
                    PreStep = rds.hget("user:%s"%user_id,"PreStep").decode("utf-8")
                    if PreStep != "5":
                        word = word + "\n可以回去繼續選了~"
                    rds.hset("user:%s"%user_id,"step",PreStep)#回到做完狀態
                    line_bot_api.reply_message(event.reply_token, TextSendMessage(word))
                    
                    if rds.hexists("user:%s"%user_id,"UsingRichMenu") == True and rds.hget("user:%s"%user_id,"UsingRichMenu").decode("utf-8") == "RightDeleteAccountClicked":#使用RichMenu重新註冊紐，
                       RichMenuFunctionEnd(user_id, "Right")
                    if rds.hexists("user:%s"%user_id,"BeChoosenAsCleaning"):#可能註冊完者在思考重新註冊時觸發，導致可以避免任命
                        line_bot_api.unlink_rich_menu_from_user(user_id)#刪除RichMenu
                        rds.hdel("user:%s"%user_id,"UsingRichMenu")#要換新RichMenu，把舊的使用紀錄刪除
                        rds.hdel("user:%s"%user_id,"BeChoosenAsCleaning")#刪除暫存變數
                        FlexMessage = json.load(open('打掃成員選擇.json','r',encoding='utf-8'))
                        line_bot_api.push_message(user_id, FlexSendMessage('選擇你掃區的人!!',FlexMessage))
                        rds.hset("user:%s"%user_id,"step","a")
            else:
                line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
            
                
                
    
    elif ReplyData[0:5] == "start":#註冊
        if rds.hexists("user:%s"%user_id,"step") == False:#步數設定(才不會以前的步驟被亂點)，做一次點擊就前進一步
            rds.hset("user:%s"%user_id,"step",0)
        NowStep = rds.hget("user:%s"%user_id,"step").decode("utf-8")
        if ReplyData[6:9] == "num":#第一步，號碼註冊   
            if NowStep == "0":#步數確認(做完第0步)                
                num = ReplyData[10:]
                if num == "師" and not rds.exists("Teacher_Id"):#是沒註冊老師，發確認消息("UnRegisterUser"是最後才更改，Number_Id在較前面更改，同時在註冊時被選走機率較低)
                    actList = [PostbackTemplateAction(label='YES',data='start&ConfirmNum&YES&%s'%num) , PostbackTemplateAction(label='NO',data='start&ConfirmNum&NO&%s'%num)] 
                    line_bot_api.reply_message(event.reply_token, TemplateSendMessage(alt_text='我確認一下，你是老師嗎?',template=ConfirmTemplate(text='1.我確認一下，你是老師嗎?',actions = actList)))#alt_text不可省略
                    rds.hset("user:%s"%user_id,"step",1)#前進一步
                elif num != "師" and not rds.hexists("Number_Id",num):#是沒註冊號碼
                    actList = [PostbackTemplateAction(label='YES',data='start&ConfirmNum&YES&%s'%num) , PostbackTemplateAction(label='NO',data='start&ConfirmNum&NO&%s'%num)] 
                    line_bot_api.reply_message(event.reply_token, TemplateSendMessage(alt_text='我確認一下，你是%s號嗎?'%num,template=ConfirmTemplate(text='1.我確認一下，你是%s號嗎?'%num,actions = actList)))
                    rds.hset("user:%s"%user_id,"step",1)#前進一步
                else:#是已註冊號碼，提醒(不會前進一步)
                    if num == "師":  
                        HasGotUseid = rds.get("Teacher_Id").decode("utf-8")
                        if rds.hexists("user:%s"%HasGotUseid,"name"):#完全註冊好了                  
                            HasGotName = rds.hget("user:%s"%HasGotUseid,"name").decode("utf-8")
                            line_bot_api.reply_message(event.reply_token, TextSendMessage("老師已被%s註冊走了，如果你是老師，就請他重新註冊吧!"%HasGotName))
                        else:
                            line_bot_api.reply_message(event.reply_token, TextSendMessage("老師被「暫時」註冊走了，如果你是老師，可以等一下再按一次，可能就可以註冊or知道是誰註冊走的"))
                    else:
                        HasGotUseid = rds.hget("Number_Id",num).decode("utf-8")
                        if rds.hexists("user:%s"%HasGotUseid,"name"):#完全註冊好了  
                            HasGotName = rds.hget("user:%s"%HasGotUseid,"name").decode("utf-8")
                            line_bot_api.reply_message(event.reply_token, TextSendMessage("%s號已被%s註冊走了，如果%s是你的號碼，就請他重新註冊吧!"%(num,HasGotName,num)))   
                        else:
                            line_bot_api.reply_message(event.reply_token, TextSendMessage("%s號「暫時」註冊走了，如果你是%s號，可以等一下再按一次，可能就可以註冊or知道是誰註冊走的"%(num,num)))
            else:
                line_bot_api.push_message(user_id,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
        elif ReplyData[6:16] == "ConfirmNum":#第二步，確認號碼註冊正確+註冊好號碼，學號與名子        
            if NowStep == "1":#步數確認(做完第1步)            
                if ReplyData[17:20] == "YES":
                    num = ReplyData[21:]
                    if num == "師":
                        userProfile = line_bot_api.get_profile(user_id)
                        rds.set("Teacher_Id",user_id)
                        rds.hset("user:%s"%user_id,"name",userProfile.display_name)
                        if bytes(user_id,"utf-8") not in rds.lrange("Manager_Id",0,-1):#如果招集者 == 老師，就不用再給一次
                            rdsRpush("Manager_Id",user_id)#老師有管理員權力
                        
                        line_bot_api.reply_message(event.reply_token,TextSendMessage("2.連動Line Notify\n\n老師，請連動Line Notify！步驟:\n\t(1)點下面的連結\n\t(2)選擇「透過 1 對 1 聊天接收 LINE Notify 通知」然後按「同意並連動」即可\n\n網址:"+"https://%s.herokuapp.com/CheckNotify/%s"%(herokuApp_name,user_id)))
                    else:                   
                        userProfile = line_bot_api.get_profile(user_id)
                        rds.hset("Number_Id",num,user_id)
                        rds.hset("user:%s"%user_id,"name",userProfile.display_name)
                        rds.hset("user:%s"%user_id,"number",num)
                        
                        line_bot_api.reply_message(event.reply_token,TextSendMessage("2.連動Line Notify\n\n%s同學，請連動Line Notify！步驟:\n\t(1)點下面的連結\n\t(2)選擇「透過 1 對 1 聊天接收 LINE Notify 通知」然後按「同意並連動」即可\n\n網址:"%userProfile.display_name + "https://%s.herokuapp.com/CheckNotify/%s"%(herokuApp_name,user_id)))
                    rds.hset("user:%s"%user_id,"step",2)#前進一步
                else:#No
                    line_bot_api.reply_message(event.reply_token,TextSendMessage("好喔，取消註冊。\n記得再重頭(第0步)註冊一次喔!"))
                    rds.hset("user:%s"%user_id,"step",0)#回到第0步
            else:
                line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
       
        
        elif ReplyData[6:12] == "Notify":#第四步，LineNotify確認密碼(因為LineNotify的accessToken無規律，LineBot也看不到Notify的訊息，無法確認是否正確註冊到一對一，所以只好人工確認)
            if NowStep == "3":#步數確認(做完第3步)        
                line_bot_api.reply_message(event.reply_token,TextSendMessage("那應該是選到群組了。選「透過 1 對 1 聊天接收 LINE Notify 通知」才對！再回去點一次連結吧！"))
                rds.hset("user:%s"%user_id,"step",2)#前進一步
            else:
                line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
        elif ReplyData[6:19] == "ConfirmNotify":#第五步，註冊完成 + 確認資料正確 + 重新註冊
            if NowStep == "4":#步數確認(做完第4步)  
                if ReplyData[20:23] == "YES":
                    password = ReplyData[24:]
                    if password != rds.hget("user:%s"%user_id,"password").decode("utf-8"):
                        line_bot_api.reply_message(event.reply_token,TextSendMessage("密碼錯誤！再打一次吧！\n如果不知密碼就按 沒收到密碼... 求救"))
                        rds.hset("user:%s"%user_id,"step",3)#回到第3步
                    else:
                        if rds.exists("Teacher_Id") and user_id == rds.get("Teacher_Id").decode("utf-8"):#是老師#沒exists就不會執行get，避免出錯
                            num = "老師"
                            rds.lrem("UnRegisterUser",0,"師")
                        else:
                            num = rds.hget("user:%s"%user_id,"number").decode("utf-8")
                            rds.lrem("UnRegisterUser",0,num)
                    
                        if rds.hexists("user:%s"%user_id,"access_token"):
                            HasNotify = "已註冊"
                        else:
                            HasNotify ="未註冊"
                        actList = [PostbackTemplateAction(label='重新註冊(長存)',data='del&start')]
                        line_bot_api.push_message(user_id,TextSendMessage("密碼正確！謝謝你的配合!!最後，請確認你的資料是否正確:\n\n\t座號(老師):%s\n\tLineNotify:%s\n\n如果有錯，請點下面的重新註冊鈕，沒錯就全部註冊完了，謝謝你的配合!!"%(num,HasNotify)))
                        line_bot_api.reply_message(event.reply_token,TemplateSendMessage(alt_text='註冊完了!!',template=ButtonsTemplate(title="5.註冊完了!!",text='需要重新註冊來這~',actions = actList)))#text有字數限制，在這裡做JSON檔太麻煩了，只好push Message       
                        rds.hset("user:%s"%user_id,"step",5)#道第5步(完成步)
                        
                        time.sleep(3)
                    
                        if num == "老師":#老師要選打掃股長
                            if not rds.exists("Cleaning_Id"):#沒有人選過才需要選
                                FlexMessage = json.load(open('打掃股長選擇.json','r',encoding='utf-8'))
                                line_bot_api.push_message(user_id, FlexSendMessage('選擇打掃股長!!',FlexMessage))
                                rds.hset("user:%s"%user_id,"step","A")#到第A步
                            else:
                                line_bot_api.link_rich_menu_to_user(user_id,config.get("RM_MiddleManage","id"))#可以直接有RichMenu
                            
                        elif bytes(num,"utf-8") in rds.lrange("Cleaning_Num", 0, -1):#是打掃股長
                            FlexMessage = json.load(open('打掃成員選擇.json','r',encoding='utf-8'))
                            line_bot_api.push_message(user_id ,FlexSendMessage('選擇你掃區的人!!',FlexMessage))
                            rds.hset("user:%s"%user_id,"step","a")#到第a步
            
                        elif bytes(user_id,"utf-8") in rds.lrange("Manager_Id", 0, -1):#是管理員，可以直接有RichMenu(老師也是管理員，但已被if else語句去除，沒問題)
                            line_bot_api.link_rich_menu_to_user(user_id,config.get("RM_MiddleManage","id"))
                            
                        else:#一般人可以使用RichMenu了
                            line_bot_api.link_rich_menu_to_user(user_id,config.get("RM_MiddleNormal","id"))
                            
                        if rds.llen("UnRegisterUser") == 0:#全部人註冊完了，註冊Group時間(請先加入群組再註冊)
                            FirstManager_id = rds.lindex("Manager_Id", 0).decode("utf-8")#由第一個Manager(發設定開始者)為代表
                            group_id = rds.hget("group","group_id").decode("utf-8")
                            send_message(rds.hget("user:%s"%FirstManager_id,"access_token").decode("utf-8"),"Group_link(請先加入群組再註冊):"+create_auth_link(group_id))
                else:#No
                     line_bot_api.reply_message(event.reply_token,TextSendMessage("再打一次吧！\n如果不知密碼就按 沒收到密碼... 吧!"))
                     rds.hset("user:%s"%user_id,"step",3)#回到第3步
            else:
                line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
    #-------------------------------------------#  


    #---------------選打掃股長-------------------#
    elif ReplyData[0:11] == "GetCleaning":#老師註冊打掃股長
        NowStep = rds.hget("user:%s"%user_id,"step").decode("utf-8")    
        if ReplyData[12:15] == "num":#第A步，選號碼
            if NowStep == "A":  
                num = ReplyData[16:]
                if num == "Fin":#選完了
                    if not rds.exists("Cleaning_Num") or (rds.exists("Cleaning_Num") and rds.llen("Cleaning_Num") != 3):
                        line_bot_api.reply_message(event.reply_token,TextSendMessage("打掃股長要有也只有三個！回去再選吧！"))
                    else:
                        SortRedisList("Cleaning_Num")
                        
                        Chosen = ""
                        for i in rds.lrange("Cleaning_Num", 0, -1):
                            Chosen = Chosen + i.decode("utf-8") + ","
                        Chosen = Chosen.rstrip(",")
                        actList = [PostbackTemplateAction(label='OK!',data='GetCleaning&done&YES') , PostbackTemplateAction(label='不OK',data='GetCleaning&done&NO')] 
                        line_bot_api.reply_message(event.reply_token,TemplateSendMessage(alt_text='確定選完了嗎?',template=ConfirmTemplate(text='B.確定選:%s為打掃股長?'%Chosen,actions = actList)))
                        rds.hset("user:%s"%user_id,"step","B")#到第B步
                else:#選擇號碼
                    if rds.hexists("Number_Id",num) and rds.hget("Number_Id",num) in rds.lrange("Manager_Id",0,-1):#一個人不可以同時為管理員與打掃股長，會出問題(未註冊不會是管理員，增減管理員功能在註冊好後才開放)
                        line_bot_api.reply_message(event.reply_token,TextSendMessage("他/她是管理員，沒辦法同時當打掃股長！"))
                    else:
                        if rds.exists("Cleaning_Num") and (bytes(num,"utf-8") in rds.lrange("Cleaning_Num", 0, -1)):#是選過的，取消選取
                            rds.lrem("Cleaning_Num",0,num)
                        else:#增加
                            rdsRpush("Cleaning_Num",num)
                        Chosen = ""
                        for i in rds.lrange("Cleaning_Num", 0, -1):
                            Chosen = Chosen + i.decode("utf-8") + ","
                        Chosen = Chosen.rstrip(",")
                        line_bot_api.reply_message(event.reply_token,TextSendMessage("目前你選了 : "+Chosen))
            else:
                line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
        elif ReplyData[12:16] == "done":#第B步，確認選擇正確
            if NowStep == "B":  
                if ReplyData[17:] == "YES":  
           
                    CheckNum = ""              
                    for i in rds.lrange("Cleaning_Num", 0, -1):#完全註冊好者，發選成員的訊息                     
                        num = i.decode("utf-8")
                        CheckNum = CheckNum + num + ","
                        
                        if (not rds.exists("OriginalCleaningNum")) or (i not in rds.lrange("OriginalCleaningNum",0,-1)):#第一次選or重選，都是沒有變有(三種情況：沒註冊、沒註冊完、已註冊完平民)                                  
                             if bytes(num,"utf-8") not in rds.lrange("UnRegisterUser",0,-1):#如沒有就是未註冊，無須主動發訊(等註冊完會發)
                                ChosenId = rds.hget("Number_Id",num).decode("utf-8")
                                ChosenStep = rds.hget("user:%s"%ChosenId,"step").decode("utf-8")
                                if ChosenStep == "5":#完全註冊好者，發選成員的訊息，未註冊完全者，無須主動發訊(等註冊完會發)
                                    line_bot_api.unlink_rich_menu_from_user(ChosenId)#刪除RichMenu
                                    rds.hdel("user:%s"%ChosenId,"UsingRichMenu")#要換新RichMenu，把舊的使用紀錄刪除
                                    FlexMessage = json.load(open('打掃成員選擇.json','r',encoding='utf-8'))
                                    line_bot_api.push_message(ChosenId, FlexSendMessage('選擇你掃區的人!!',FlexMessage))
                                    rds.hset("user:%s"%ChosenId,"step","a")
                                else:
                                    if ChosenStep == "6":#可能註冊完者在思考重新註冊時觸發，導致可以避免任命
                                        rds.hset("user:%s"%ChosenId,"BeChoosenAsCleaning",1)
                                
                                    
                    CheckNum = CheckNum.rstrip(",")
                    
                    
                    if rds.exists("OriginalCleaningNum"):
                        taker = rds.hget("user:%s"%user_id, "name").decode("utf-8")
                        
                        for i in rds.lrange("OriginalCleaningNum", 0, -1):#與原本比對沒有的人                  
                            num = i.decode("utf-8")
                            
                            if i not in rds.lrange("UnRegisterUser",0,-1):#根本沒註冊就不用改
                                DisChosenId = rds.hget("Number_Id",num).decode("utf-8")                               
                                DisChosenStep = rds.hget("user:%s"%DisChosenId,"step").decode("utf-8")
                                
                                
                                if i not in rds.lrange("Cleaning_Num", 0, -1):#重選，有變沒有(四種情況：股長未選成員、股長選成員中、已註冊完股長未用RichMenu、已註冊完股長正在用RichMenu)，打掃股長RcihMenu在選完掃區才會給，所以要看如何刪除RichMenu
                                    if not rds.hexists("user:%s"%DisChosenId,"LeadSection"):#未選完成員
                                        if DisChosenStep == "a":#股長未選成員
                                            line_bot_api.push_message(DisChosenId, TextSendMessage("%s把您的打掃股長權限收回了，不用選成員了，那就全部註冊完成了~"%taker))
                                            rds.delete("CleaningSection:%s"%DisChosenId)#刪除暫存變數(可能選1個人時被換)
                                            rds.hset("user:%s"%DisChosenId,"step","5")#強制回歸完成步
                                        else:#股長選成員中
                                            rds.delete("CleaningSection:%s"%DisChosenId)#刪除暫存變數(那時是依靠ReplyData傳資料，所以暫存變數很少，其實也不算站存，這還有用處)
                                            rds.hset("user:%s"%DisChosenId,"step","5")#強制回歸完成步
                                            line_bot_api.push_message(DisChosenId, TextSendMessage("%s把您的打掃股長權限收回了，不用再選了，那就全部註冊完成了~"%taker))
                                        line_bot_api.link_rich_menu_to_user(DisChosenId,config.get("RM_MiddleNormal","id"))#給他RichMenu
                                        
                                    else:#選完成員(刪除打掃股長時只有刪Cleaning_Num(暫存變數)，其他的紀錄(選成員的變數)在此一並刪)
                                        
                                      
                                        rds.lrem("Cleaning_Id",0,DisChosenId)
                                        LeadArea = rds.hget("user:%s"%DisChosenId,"LeadSection").decode("utf-8")
                                        rds.hdel("user:%s"%DisChosenId,"LeadSection")
                                        rds.delete("CleaningSection:%s"%DisChosenId)
                                        rds.delete("CleaningSection:%s"%LeadArea)
                                        if DisChosenStep == "5":#未用RichMenu
                                            if rds.exists("QuittingCleaning:%s"%DisChosenId):#有可能正在等是否要替代打掃股長，無效他！
                                                DeleteAskingQuitting(DisChosenId)
                                                
                                            if rds.hget("user:%s"%DisChosenId,"UsingRichMenu").decode("utf-8") == "MiddleCleaning" or rds.hget("user:%s"%DisChosenId,"UsingRichMenu").decode("utf-8") == "DownCleaning":#只有這兩種需要主動切換
                                                line_bot_api.link_rich_menu_to_user(DisChosenId,config.get("RM_MiddleNormal","id"))#變回原本RichMenu
                                                rds.hdel("user:%s"%DisChosenId,"UsingRichMenu")#把使用紀錄刪除才可
                                            line_bot_api.push_message(DisChosenId, TextSendMessage("%s把您的打掃股長權限收回了，您變回普通人了，十分抱歉！"%taker))
                                        else:#正在用RichMenu
                                            UsingClickedRichMenu = rds.hget("user:%s"%DisChosenId,"UsingRichMenu").decode("utf-8")
                                            if UsingClickedRichMenu != "RightDeleteAccountClicked":#使用這個會回到Right，對RichMenu無影響
                                                line_bot_api.link_rich_menu_to_user(DisChosenId,config.get("RM_MiddleNormal","id"))#強制變回原本RichMenu
                                                rds.hdel("user:%s"%DisChosenId,"UsingRichMenu")#把使用紀錄刪除才可
                                            if bytes(UsingClickedRichMenu,"utf-8") in rds.hkeys("APersonCanUsingRichMenu"):#正在用的是只能一個人用的RcihMenu，要讓別人可以用
                                                rds.hdel("APersonCanUsingRichMenu",UsingClickedRichMenu)#讓其他人可用
                                            rds.hset("user:%s"%DisChosenId,"step","5")#強制回歸完成步
                                            rds.delete("CleaningChangedNums")#要刪除所有可能的暫存變數
                                            rds.delete("QuittingCleaning:%s"%DisChosenId)#要刪除所有可能的暫存變數
                                            line_bot_api.push_message(DisChosenId, TextSendMessage("%s把您的打掃股長權限收回了，十分抱歉！\n\n如果您正在使用刪除帳號功能，會等到您用完再收回，其他功能已被強制停止"%taker))
                                       
                                        if rds.exists("CleaningTemporaryReplace:%s"%DisChosenId):#有可能正在暫時委託他人做打掃股長(可能有or沒有在用RichMenu)
                                            DeleteTemporaryReplacement(DisChosenId)
              
                    
                    rds.delete("OriginalCleaningNum")#刪除暫存變數
                    actList = [PostbackTemplateAction(label='重新選擇(長存)',data='DelCleaning&start')]
                    line_bot_api.push_message(user_id,TextSendMessage("謝謝配合!!最後，請確認你選的是否正確:\n\n\t打掃股長:%s\n\n如果有錯，請點下面的重新選擇鈕，沒錯就真的全部完成了，謝謝你的配合!!"%CheckNum))
                    line_bot_api.reply_message(event.reply_token,TemplateSendMessage(alt_text='選完了!!',template=ButtonsTemplate(title="C.選完了!!",text='需要重新選擇來這~',actions = actList)))#text有字數限制，在這裡做JSON檔太麻煩了，只好push Message       
                    rds.hset("user:%s"%user_id,"step","5")#到完成步
                    
                    if rds.hexists("user:%s"%user_id,"UsingRichMenu") == True and rds.hget("user:%s"%user_id,"UsingRichMenu").decode("utf-8") == "DownManageCleaningReportSettingClicked":#使用RichMenu重新許股長，要讓RichMenu回復
                        RichMenuFunctionEnd(user_id, "DownManage")
                        rds.hdel("APersonCanUsingRichMenu","DownManageCleaningReportSettingClicked")#讓其他人可用
                    else:#第一次選(在註冊完後)，沒有RichMenu，老師謝在可以有了
                        line_bot_api.link_rich_menu_to_user(user_id,config.get("RM_MiddleManage","id"))#老師可以用RichMenu了
                        
                    
                else:#NO
                    rds.hset("user:%s"%user_id,"step","A")#回到第A步
                    line_bot_api.reply_message(event.reply_token,TextSendMessage("好，那請繼續選吧~(第A步)"))
            else:
                line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
    
    
    elif ReplyData[0:11] == "DelCleaning":#老師刪除打掃股長
        if (not rds.exists("Teacher_Id") or bytes(user_id,"utf-8") != rds.get("Teacher_Id")) and (bytes(user_id,"utf-8") not in rds.lrange("Manager_Id", 0, -1)): #只有老師能操作(可能同學不小心註冊成老師，就可能用的到)
            line_bot_api.reply_message(event.reply_token,TextSendMessage("很抱歉，你現在沒有權限使用這些功能了喔!!"))
        else:
            NowStep = rds.hget("user:%s"%user_id,"step").decode("utf-8")        
            if ReplyData[12:] == "start":#確認真的要重選
                if NowStep == "5" :#確認在完成步
                     actList = [PostbackTemplateAction(label='沒錯。',data='DelCleaning&sure&YES') , PostbackTemplateAction(label='按錯而已啦',data='DelCleaning&sure&NO')] 
                     line_bot_api.reply_message(event.reply_token,TemplateSendMessage(alt_text='認真要重選?',template=ConfirmTemplate(text='D.認真要重選打掃股長?',actions = actList)))
                     rds.hset("user:%s"%user_id,"step","D")#到第D步
                else:
                    line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
            elif ReplyData[12:16] == "sure":#刪除+重新選擇打掃股長
                if NowStep == "D":#確認在第D步
                    if ReplyData[17:20] == "YES":
                        for i in rds.lrange("Cleaning_Num",0,-1):
                            rdsRpush("OriginalCleaningNum", i.decode("utf-8"))#紀錄原有股長，有改動就要通知+改RichMenu
                        rds.delete("Cleaning_Num")
                        line_bot_api.reply_message(event.reply_token,TextSendMessage("打掃股長全部刪除好了!重新選吧!!"))                   
                        rds.hset("user:%s"%user_id,"step","A")
                        FlexMessage = json.load(open('打掃股長選擇.json','r',encoding='utf-8'))
                        line_bot_api.push_message(user_id, FlexSendMessage('選擇打掃股長!!',FlexMessage))
                    else:#NO
                        rds.hset("user:%s"%user_id,"step","5")#到完成步
                        line_bot_api.reply_message(event.reply_token,TextSendMessage("沒關係，這樣我也省事"))
                        
                        if rds.hexists("user:%s"%user_id,"UsingRichMenu") == True and rds.hget("user:%s"%user_id,"UsingRichMenu").decode("utf-8") == "DownManageCleaningReportSettingClicked":#使用RichMenu重新許股長，要讓RichMenu回復#此時必有RichMenunp，
                            RichMenuFunctionEnd(user_id, "DownManage")
                            rds.hdel("APersonCanUsingRichMenu","DownManageCleaningReportSettingClicked")#讓其他人可用
                else:
                    line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
     #-----------------------------------------#
                    
                    
    #----------------股長選成員---------------#
    elif ReplyData[0:7] == "GetCrew":#股長選成員
        NowStep = rds.hget("user:%s"%user_id,"step").decode("utf-8")    
        if ReplyData[8:11] == "num":#第a步，選號碼
            if NowStep == "a":  
                num = ReplyData[12:]
                if num == "Fin":#選完了
                    if not rds.exists("CleaningSection:%s"%user_id) or (rds.exists("CleaningSection:%s"%user_id) and rds.llen("CleaningSection:%s"%user_id) == 0):#沒選人
                        line_bot_api.reply_message(event.reply_token,TextSendMessage("怎麼可能沒有人！去選人啦！"))
                    else:
                        SortRedisList("CleaningSection:%s"%user_id)
                        
                        Chosen = ""
                        for i in rds.lrange("CleaningSection:%s"%user_id, 0, -1):
                            Chosen = Chosen + i.decode("utf-8") + ","
                        Chosen = Chosen.rstrip(",")
                        actList = [PostbackTemplateAction(label='Wright!',data='GetCrew&DoneNum&YES') , PostbackTemplateAction(label='Wrong',data='GetCrew&DoneNum&NO')] 
                        line_bot_api.reply_message(event.reply_token,TemplateSendMessage(alt_text='確定選完人了嗎?',template=ConfirmTemplate(text='b.確定你的人是:%s?'%Chosen,actions = actList)))
                        rds.hset("user:%s"%user_id,"step","b")#到第b步
                else:#選擇號碼
                    if rds.hexists("Number_Id",num) and rds.hget("Number_Id",num).decode("utf-8") == user_id:#選到自己
                        line_bot_api.reply_message(event.reply_token,TextSendMessage("不用選自己喔！再去選其他人吧！"))
                    else:                            
                        if rds.exists("CleaningSection:%s"%user_id) and (bytes(num,"utf-8") in rds.lrange("CleaningSection:%s"%user_id, 0, -1)):#是選過的，取消選取
                            rds.lrem("CleaningSection:%s"%user_id,0,num)
                        else:#增加
                            rdsRpush("CleaningSection:%s"%user_id,num)
                            
                        Chosen = ""                 
                        for i in rds.lrange("CleaningSection:%s"%user_id, 0, -1):
                            Chosen = Chosen + i.decode("utf-8") + ","
                        Chosen = Chosen.rstrip(",")
                        
                        line_bot_api.reply_message(event.reply_token,TextSendMessage("目前你選了 : " + Chosen))
            else:
                line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
        elif ReplyData[8:15] == "DoneNum":#第b步，確認選擇正確
            if NowStep == "b":  
                if ReplyData[16:] == "YES":
                    actList = [PostbackTemplateAction(label='外掃',data='GetCrew&Area&外掃') , PostbackTemplateAction(label='內掃',data='GetCrew&Area&內掃'),PostbackTemplateAction(label='倒垃圾',data='GetCrew&Area&倒垃圾') ] 
                    line_bot_api.reply_message(event.reply_token,TemplateSendMessage(alt_text='選區域!!',template=ButtonsTemplate(text='c.那你管的是哪個區域?',actions = actList)))                 
                    rds.hset("user:%s"%user_id,"step","c")#到第c步
                else:#NO
                    rds.hset("user:%s"%user_id,"step","a")#回到第a步
                    line_bot_api.reply_message(event.reply_token,TextSendMessage("好，那請繼續選人吧~(第a步)"))
            else:
                line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
        elif ReplyData[8:12] == "Area":#第c步，選擇區域
            if NowStep == "c":  
                area = ReplyData[13:]#很神奇的，中英文可以一起切割字串    
                if rds.exists("CleaningSection:%s"%area):#是被選過的區域，退貨(只要兩個人同時在c步就可以閃過審核，出bug，但機率太低，不要因此複雜化程式碼)
                    getter = ""
                    for i in rds.lrange("Cleaning_Id",0,-1):
                        CleaningId = i.decode("utf-8")
                        if rds.hget("user:%s"%CleaningId,"LeadSection").decode("utf-8") == area:
                            getter = rds.hget("user:%s"%CleaningId,"name").decode("utf-8")
                    line_bot_api.reply_message(event.reply_token,TextSendMessage("%s已管理此區域了，換個區域，在選一次吧！"%getter))
                else:               
                    actList = [PostbackTemplateAction(label='是的',data='GetCrew&DoneArea&YES&%s'%area) , PostbackTemplateAction(label='不是的',data='GetCrew&DoneArea&NO')] 
                    line_bot_api.reply_message(event.reply_token,TemplateSendMessage(alt_text='確定選完區域了嗎?',template=ConfirmTemplate(text='d.確定你是管%s的?'%area,actions = actList)))
                    rds.hset("user:%s"%user_id,"step","d")#到第d步
            else:
                line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
        elif ReplyData[8:16] == "DoneArea":#第d步，確認選區域擇正確 + 製作JSON + 重新選擇鈕
            if NowStep == "d":  
                if ReplyData[17:20] == "YES":
                    if rds.exists("CleaningReporting"):#可能在打掃時間註冊完，會出錯
                        line_bot_api.reply_message(event.reply_token,TextSendMessage("抱歉，在打掃股長們回報時註冊完成，會出錯，所以請等打掃時節結束再來，很抱歉！"))
                    else:
                        LeadArea = ReplyData[21:]
                        rdsRpush("Cleaning_Id",user_id)#傳訊用
                        rds.hset("user:%s"%user_id,"LeadSection",LeadArea)#傳特定JSON用
                        CheckNum = ""
                        for i in rds.lrange("CleaningSection:%s"%user_id,0,-1):
                            num = i.decode("utf-8")
                            rdsRpush("CleaningSection:%s"%LeadArea,num)#製作JSON會用上
                            CheckNum = CheckNum + num + ","
                        CheckNum = CheckNum.rstrip(",")
                        
                        
                        changer = rds.hget("user:%s"%user_id,"name").decode("utf-8")
                        for i in rds.lrange("Manager_Id",0,-1):#跟管理員說一下，不然會被濫用
                            ManagerId = i.decode("utf-8")
                            ManagerAccessToken = rds.hget("user:%s"%ManagerId,"access_token").decode("utf-8")          
                            send_message(ManagerAccessToken, "打掃股長 %s 將\n\n自己的掃區設為:%s\n自己館的人設為:\n%s\n\n跟您報備一下，避免這個功能被濫用"%(changer,LeadArea,CheckNum))
                        
                        actList = [PostbackTemplateAction(label='重新選擇(長存)',data='DelCrew&start')]
                        line_bot_api.push_message(user_id,TextSendMessage("謝謝你的配合!!最後，請確認你選的是否正確:\n\n\t你管的人:%s\n\t你管的區域:%s\n\n如果有錯，請點下面的重新選擇鈕。沒錯了話你從現在起，就是打掃股長!之後合作愉快啦!!"%(CheckNum,LeadArea)))
                        line_bot_api.reply_message(event.reply_token,TemplateSendMessage(alt_text='選完了!!',template=ButtonsTemplate(title="e.選完了!!",text='需要重新選擇來這~',actions = actList)))#text有字數限制，在這裡做JSON檔太麻煩了，只好push Message       
                        rds.hset("user:%s"%user_id,"step","5")#到完成步
                        
                        if rds.hexists("user:%s"%user_id,"UsingRichMenu") == True and rds.hget("user:%s"%user_id,"UsingRichMenu").decode("utf-8") == "DownCleaningCleaningRechooseFellowsClicked":#使用RichMenu重新選成員，要讓RichMenu回復
                            RichMenuFunctionEnd(user_id, "DownCleaning")
                        else:
                            line_bot_api.link_rich_menu_to_user(user_id,config.get("RM_MiddleCleaning","id"))#打掃股長選完成員就可以有RichMenu了
                else:#NO
                    rds.hset("user:%s"%user_id,"step","c")#回到第c步
                    line_bot_api.reply_message(event.reply_token,TextSendMessage("那再選一次你的區域吧(第c步)!"))
            else:
                line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
    
        
    elif ReplyData[0:7] == "DelCrew":#股長刪除成員
        if (rds.exists("Cleaning_Id") and bytes(user_id,"utf-8") not in rds.lrange("Cleaning_Id",0,-1)) and (bytes(user_id,"utf-8") not in rds.lrange("Manager_Id", 0, -1)): #只有打掃股長能操作(可能老師不小心選錯，就可能用的到)
            line_bot_api.reply_message(event.reply_token,TextSendMessage("很抱歉，你現在沒有權限使用這些功能了喔!!可能是因為老師拔除了你的權限，問問老師吧!"))
        else:
            NowStep = rds.hget("user:%s"%user_id,"step").decode("utf-8")        
            if ReplyData[8:] == "start":#確認真的要重選
                if NowStep == "5":#確認在完成步
                     actList = [PostbackTemplateAction(label='沒錯。',data='DelCrew&sure&YES') , PostbackTemplateAction(label='按錯而已啦',data='DelCrew&sure&NO')] 
                     line_bot_api.reply_message(event.reply_token,TemplateSendMessage(alt_text='認真要重選?',template=ConfirmTemplate(text='f.認真要重選你管的人和區域?\n (作者:把人與區域分開好麻煩~)',actions = actList)))
                     rds.hset("user:%s"%user_id,"step","f")#到第D步
                else:
                    line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
            elif ReplyData[8:12] == "sure":#刪除+重新選擇成員
                if NowStep == "f":#確認在第f步
                    if ReplyData[13:] == "YES":
                        LeadArea = rds.hget("user:%s"%user_id,"LeadSection").decode("utf-8")
                        rds.lrem("Cleaning_Id",0,user_id)
                        rds.hdel("user:%s"%user_id,"LeadSection")
                        rds.delete("CleaningSection:%s"%user_id)
                        rds.delete("CleaningSection:%s"%LeadArea)
                        line_bot_api.reply_message(event.reply_token,TextSendMessage("你管的人和區域全部刪除好了!重新選吧!!"))                   
                        FlexMessage = json.load(open('打掃成員選擇.json','r',encoding='utf-8'))
                        line_bot_api.push_message(user_id, FlexSendMessage('選擇你掃區的人!!',FlexMessage))
                        rds.hset("user:%s"%user_id,"step","a")
                    else:#NO
                        rds.hset("user:%s"%user_id,"step","5")#到完成步
                        line_bot_api.reply_message(event.reply_token,TextSendMessage("沒關係，這樣我也省事"))
                        
                        if rds.hexists("user:%s"%user_id,"UsingRichMenu") == True and rds.hget("user:%s"%user_id,"UsingRichMenu").decode("utf-8") == "DownCleaningCleaningRechooseFellowsClicked":#使用RichMenu重新選成員，要讓RichMenu回復
                            RichMenuFunctionEnd(user_id, "DownCleaning")
                else:
                    line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
    #--------------------------------------#

    #============================================================================#

    

    #==================================RichMenu系統=======================================#
    
    #---------------Right(AboutYou)-----------------#
    elif ReplyData[0:8] == "AboutYou":#RichMenu關於使用者，切換至Right
        if bytes(user_id,"utf-8") in rds.lrange("Manager_Id", 0, -1):#管理者
            ChangeRichMenu(user_id, "MiddleManage","MiddleManageAboutYouClicked", "Right")
        elif (rds.exists("Cleaning_Id") and bytes(user_id,"utf-8") in rds.lrange("Cleaning_Id", 0, -1)):#打掃股長
            ChangeRichMenu(user_id, "MiddleCleaning","MiddleCleaningAboutYouClicked", "Right")
        else:
            ChangeRichMenu(user_id, "MiddleNormal","MiddleNormalAboutYouClicked", "Right")
            
    elif ReplyData[0:8] == "YourData":#顯示使用者資料
        if CanStartFunction(user_id,"Right",True,"null","null"):#避免還沒切換又被要求第二次  
            RichMenuFunctionStart(user_id,"RightYourDataClicked")
        

            data = ""
            name = rds.hget("user:%s"%user_id,"name").decode("utf-8")
            data = data + "名字 : " + name + "\n"
            if rds.exists("Teacher_Id") and rds.get("Teacher_Id").decode("utf-8") == user_id or bytes(user_id,"utf-8") in rds.lrange("Manager_Id", 0, -1):#是老師
                if bytes(user_id,"utf-8") in rds.lrange("Manager_Id", 0, -1):
                    Authority = "管理員"
                else:
                    Authority = "老師"
                data = data + "職位 : " + Authority + "\n"
                Cleanings = ""#需要知道打掃股長是誰
                if not rds.exists("Cleaning_Id"):#沒有任何打掃股長有註冊(只要有人註冊就不會有空缺)
                    Cleanings = "您選的人都沒完成註冊~\n此處只顯示註冊完的人~\n"
                else:
                    for i in rds.lrange("Cleaning_Id",0,-1):
                        CleaningId = i.decode("utf-8")
                        CleaningNum = rds.hget("user:%s"%CleaningId,"number").decode("utf-8")
                        CleaningName = rds.hget("user:%s"%CleaningId,"name").decode("utf-8")
                        CleaningScore = worksheet.get("B%i"%(int(CleaningNum)+1)).first()#是字串
                        Cleanings = Cleanings + "\t" + "%s(%s號) : %s分"%(CleaningName,CleaningNum,CleaningScore) + "\n"
                data = data + "打掃股長 :\n" + Cleanings.rstrip()
            else:#是學生
                number = rds.hget("user:%s"%user_id,"number").decode("utf-8")    
                data = data + "座號 : " + number + "\n"
                if rds.exists("ChangedNums"):#有人在編輯分數，不能用sheet的分數，藥用暫存的原始分數
                    score = rds.hget("ChangedNums",number).decode("utf-8")
                elif rds.exists("CleaningChangedNums"):#有人在編輯分數，不能用sheet的分數，藥用暫存的原始分數(已設定一次只能有一人改分數)
                    score = rds.hget("CleaningChangedNums",number).decode("utf-8")
                else:
                    score = worksheet.get("B%i"%(int(number) + 1)).first()#分數存在googlr sheet中
                data = data + "分數 : " + score + "\n"
                if rds.exists("Cleaning_Id") and bytes(user_id,"utf-8") in rds.lrange("Cleaning_Id",0,-1):#是打掃股長
                    Authority = "打掃股長"    
                    data = data + "職位 : " + Authority + "\n"
                    Section = rds.hget("user:%s"%user_id,"LeadSection").decode("utf-8")
                    data = data + "管理區域 : " + Section + "\n"
                    people = ""#需要知道每個管理到的人的資料
                    for i in rds.lrange("CleaningSection:%s"%user_id,0,-1):
                        personNum = i.decode("utf-8")
                        personScore = worksheet.get("B%i"%(int(personNum)+1)).first()#是字串
                        if rds.hexists("Number_Id",personNum):#是註冊完的
                            personId = rds.hget("Number_Id",personNum).decode("utf-8")
                            personName = rds.hget("user:%s"%personId,"name").decode("utf-8")                          
                            people = people + "\t" + "%s(%s號) : %s分"%(personName,personNum,personScore) + "\n"
                        else:
                            people = people + "\t" + "%s號(未註冊) : %s分"%(personNum,personScore) + "\n"
                    data = data + "旗下人類 :\n" + people.rstrip()
                else:
                    Authority = "普通人類"
                    data = data + "職位 : " + Authority
            line_bot_api.reply_message(event.reply_token,TextSendMessage(data))
            
            RichMenuFunctionEnd(user_id, "Right")
        
    elif ReplyData[0:13] == "DeleteAccount":#刪除帳號(就是銜接到重新註冊系統)，注意!!可能打掃股長在未被選上時正使用此功能，所以必須等他用完功能再刪除RichMenu
        if CanStartFunction(user_id,"Right",True,"null","null"):#避免還沒切換又被要求第二次  
            RichMenuFunctionStart(user_id, "RightDeleteAccountClicked")
                            
            if NowStep == "5" or NowStep == "a":#完成註冊，或是(正要開始捲打掃成員)才可用
                if rds.exists("Cleaning_Id") and bytes(user_id,"utf-8") in rds.lrange("Cleaning_Id",0,-1):#是註冊完的打掃股長，需要先交出職位才可刪除帳號(沒註冊完的可)
                    line_bot_api.reply_message(event.reply_token,TextSendMessage("請先交出打掃股長權限再刪帳\n(先去「不幹打掃股長了」鈕)"))
                    time.sleep(3)#end比reply速度快太多
                    RichMenuFunctionEnd(user_id, "Right")
                else:                   
                    word = '你認真要重新註冊?'
                    if bytes(user_id,"utf-8") in rds.lrange("Manager_Id", 0, -1):#是管理員需要額外提醒
                        if rds.llen("Manager_Id") == 1:#只剩一個管理員，不行移除
                            word = word + "\n。只剩您是管理員，權力不移除\n。打掃股長也會留著"
                        else:
                            word = word + "\n。管理員身分會被一起移除\n。打掃股長仍會留著"

                    actList = [PostbackTemplateAction(label='認真的',data='del&do&YES') , PostbackTemplateAction(label='後悔了',data='del&do&NO')] 
                    line_bot_api.reply_message(event.reply_token,TemplateSendMessage(alt_text='快跟我說要不要重新註冊!!',template=ConfirmTemplate(text=word,actions = actList)))
                    rds.hset("user:%s"%user_id,"step",6)#前進一步
                    rds.hset("user:%s"%user_id,"PreStep",NowStep) # 因為開始時可能為5 A a，要特別標記，在6回5的時候才能回到正確的開頭
            
                #要確認不要刪除才可回復RichMenu，所以寫在重新註冊系統處
            else:#仍要顧慮步數才可(步數不對，退回)
                line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
                RichMenuFunctionEnd(user_id, "Right")
                             
    elif ReplyData[0:9] == "RightBack":#Right切換回中間RichMenu
        if (bytes(user_id,"utf-8") in rds.lrange("Manager_Id", 0, -1)):#管理者
            ChangeRichMenu(user_id, "Right","RightRightBackClicked", "MiddleManage")
        elif (rds.exists("Cleaning_Id") and bytes(user_id,"utf-8") in rds.lrange("Cleaning_Id", 0, -1)):#打掃股長
            ChangeRichMenu(user_id, "Right","RightRightBackClicked", "MiddleCleaning")
        else:
            ChangeRichMenu(user_id, "Right","RightRightBackClicked", "MiddleNormal")
    #-----------------------------------------#
        
    
    #--------------Left(AboutMe)---------------#
    elif ReplyData[0:7] == "AboutMe":#RichMenu關於我，切換至Left
        if(bytes(user_id,"utf-8") in rds.lrange("Manager_Id", 0, -1)):#管理者
            ChangeRichMenu(user_id, "MiddleManage","MiddleManageAboutMeClicked", "Left")
        elif (rds.exists("Cleaning_Id") and bytes(user_id,"utf-8") in rds.lrange("Cleaning_Id", 0, -1)):#打掃股長
            ChangeRichMenu(user_id, "MiddleCleaning","MiddleCleaningAboutMeClicked", "Left")
        else:
            ChangeRichMenu(user_id, "MiddleNormal","MiddleNormalAboutMeClicked", "Left") 
            
            
    elif ReplyData[0:6] == "MyData":#顯視我的資料
        if CanStartFunction(user_id,"Left",True,"null","null"):#避免還沒切換又被要求第二次  
            RichMenuFunctionStart(user_id, "LeftMyDataClicked")      
        
            FlexMessage = json.load(open('介紹LineBot.json','r',encoding='utf-8'))
            line_bot_api.reply_message(event.reply_token, FlexSendMessage('工作內容 : ',FlexMessage))
                
            RichMenuFunctionEnd(user_id,"Left")
                    
            
    elif ReplyData[0:9] == "MakerList":#顯視開發者名單
        if CanStartFunction(user_id,"Left",True,"null","null"):#避免還沒切換又被要求第二次  
            RichMenuFunctionStart(user_id, "LeftMakerListClicked") 
                
            FlexMessage = json.load(open('製作者名單.json','r',encoding='utf-8'))
            line_bot_api.reply_message(event.reply_token, FlexSendMessage('使用語言 : ',FlexMessage))
                
            RichMenuFunctionEnd(user_id,"Left")
    
    
    elif ReplyData[0:8] == "LeftBack":#Left切換回中間RichMenu
        if (bytes(user_id,"utf-8") in rds.lrange("Manager_Id", 0, -1)):#管理者
            ChangeRichMenu(user_id, "Left","LeftLeftBackClicked", "MiddleManage")
        elif (rds.exists("Cleaning_Id") and bytes(user_id,"utf-8") in rds.lrange("Cleaning_Id", 0, -1)):#打掃股長
            ChangeRichMenu(user_id, "Left","LeftLeftBackClicked", "MiddleCleaning")
        else:
            ChangeRichMenu(user_id, "Left","LeftLeftBackClicked", "MiddleNormal")
    #---------------------------------------#
    
    
    #------------一些實用功能功能------------#
    elif ReplyData[0:14] == "UsefulFunction":
        if (bytes(user_id,"utf-8") in rds.lrange("Manager_Id", 0, -1)):#管理者
            if CanStartFunction(user_id,"DownManage",True,"null","null"):#避免還沒切換又被要求第二次  
                RichMenuFunctionStart(user_id, "DownManageUsefulFunctionClicked") 
                line_bot_api.reply_message(event.reply_token,TextSendMessage("未完成，也不知何時會有空完成，不用敬請期待了..."))
                RichMenuFunctionEnd(user_id,"DownManage")#未完成，先頂著(之後用ChangeRichMenu才可)
        elif (rds.exists("Cleaning_Id") and bytes(user_id,"utf-8") in rds.lrange("Cleaning_Id", 0, -1)):#打掃股長
            if CanStartFunction(user_id,"DownCleaning",True,"null","null"):#避免還沒切換又被要求第二次  
                RichMenuFunctionStart(user_id, "DownCleaningUsefulFunctionClicked") 
                line_bot_api.reply_message(event.reply_token,TextSendMessage("未完成，也不知何時會有空完成，不用敬請期待了..."))
                RichMenuFunctionEnd(user_id,"DownCleaning")#未完成，先頂著(之後用ChangeRichMenu才可)
        else:
            if CanStartFunction(user_id,"MiddleNormal",True,"null","null"):#避免還沒切換又被要求第二次  
                RichMenuFunctionStart(user_id, "MiddleNormalUsefulFunctionClicked") 
                line_bot_api.reply_message(event.reply_token,TextSendMessage("未完成，也不知何時會有空完成，不用敬請期待了..."))
                RichMenuFunctionEnd(user_id,"MiddleNormal")#未完成，先頂著(之後用ChangeRichMenu才可)
    #---------------------------------------#

    
    #---------------管理者功能---------------#
    elif ReplyData[0:15] == "ManagerFunction":#管理者功能
        ChangeRichMenu(user_id, "MiddleManage","MiddleManageManagerFunctionClicked", "DownManage")
    
    
    #- - - - -廣播設定- - - - #
    elif ReplyData[0:16] == "BroadcastSetting":#廣播設定
        if CanStartFunction(user_id,"DownManage",False,event.reply_token,"DownManageBroadcastSettingClicked"):             
            RichMenuFunctionStart(user_id, "DownManageBroadcastSettingClicked")   
            rds.hset("APersonCanUsingRichMenu","DownManageBroadcastSettingClicked",user_id)
            
            if NowStep == "5":#其他時間不會發生
                actList = [PostbackTemplateAction(label='編輯文字',data='BroadcastWordEdit&Start'),PostbackTemplateAction(label='開啟/關閉廣播',data='BroadcastPowerEdit'),PostbackTemplateAction(label='結束設定',data='BroadcastEditEnd')]
                line_bot_api.reply_message(event.reply_token,TemplateSendMessage(alt_text='ㄅ.定時廣播設定',template=ButtonsTemplate(title="ㄅ.定時廣播設定",text='除了廣播時間請找作者處理\n，你可以做這些事喔 !',actions = actList)))
                rds.hset("user:%s"%user_id,"step","ㄅ")#前進一步
            else:
                RichMenuFunctionEnd(user_id, "DownManage")#有關步數的系統需檢查步數(因可用重新註冊Template來改變步數，所以須限制)
                rds.hset("APersonCanUsingRichMenu","DownManageBroadcastSettingClicked",user_id)
                line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
   
    #編輯文字部分
    elif ReplyData[0:23] == "BroadcastWordEdit&Start":#選擇廣播編輯文字區
        if NowStep == "ㄅ": 
            actList = [PostbackTemplateAction(label='打掃的',data='BroadcastWordEdit&List&打掃') , PostbackTemplateAction(label='午休的',data='BroadcastWordEdit&List&午休')] 
            line_bot_api.reply_message(event.reply_token,TemplateSendMessage(alt_text='ㄆ(1).選要改文字的部分',template=ConfirmTemplate(text='ㄆ(1).選要改文字的部分',actions = actList)))
            rds.hset("user:%s"%user_id,"step","ㄆ(1)")#前進一步
        else:
            line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
    elif ReplyData[0:22] == "BroadcastWordEdit&List":#文字按鈕List
        if NowStep == "ㄆ(1)" or NowStep == "ㄈ(1)":#ㄈ-1有返回步
            Area = ReplyData[23:]
            BroadcastWordJSONMaking(Area)#製作JSON
            FlexMessage = json.load(open('廣播文字編輯器.json','r',encoding='utf-8'))
            line_bot_api.reply_message(event.reply_token, FlexSendMessage('ㄇ(1).文字編輯',FlexMessage))
            rds.hset("user:%s"%user_id,"step","ㄇ(1)")#前進一步
        else:
            line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
    elif ReplyData[0:22] == "BroadcastWordEdit&Edit":#文字按鈕List
        if NowStep == "ㄇ(1)":
            Area = ReplyData[23:]
            wordNum = ReplyData[-1]
            if ("打掃" in Area):
                Area = "打掃"
            if ("午休" in Area):
                Area = "午休"
            rds.set("ReceiveBroadcastEditText",1)#開啟收文字
            rds.set("BroadcastEditArea",Area)
            rds.set("BroadcastEditNum",wordNum)
            originWord = rds.lindex("BroadcastWord:%s"%Area, int(wordNum)).decode("utf-8")
            actList = [PostbackTemplateAction(label='不改，返回編輯列表',data='BroadcastWordEdit&List&%s'%Area)]
            line_bot_api.reply_message(event.reply_token,TemplateSendMessage(alt_text='ㄈ(1).輸入更改文字',template=ButtonsTemplate(title="ㄈ(1).輸入更改文字",text='原文 : %s\n要更改就直接傳想改的文字給我吧!'%originWord,actions = actList)))
            rds.hset("user:%s"%user_id,"step","ㄈ(1)")#前進一步
        else:
            line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
   
    #開關部分    
    elif ReplyData[0:18] == "BroadcastPowerEdit":#廣播開關召喚
        if NowStep == "ㄅ":
            SwitchJSONMaking("Broadcast")#暫時的改變不會被洗掉，但太久就會，所以要船隻賢就要調整
            FlexMessage = json.load(open('開關.json','r',encoding='utf-8'))
            line_bot_api.reply_message(event.reply_token, FlexSendMessage('ㄆ(2).廣播開關',FlexMessage))
            rds.hset("user:%s"%user_id,"step","ㄆ(2)")#前進一步
        else:
            line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
    elif ReplyData[0:20] == "BroadcastPowerSwitch":#廣播開關使用
        if NowStep == "ㄆ(2)":
            if rds.get("DoBroadcast").decode("utf-8") == "0":#關閉，要開啟
                rds.set("DoBroadcast",1)
            else:#開啟，要關閉
                rds.set("DoBroadcast",0)
            SwitchJSONMaking("Broadcast")#調好再製作
            FlexMessage = json.load(open('開關.json','r',encoding='utf-8'))
            line_bot_api.reply_message(event.reply_token, FlexSendMessage('ㄆ(2).廣播開關',FlexMessage))
        else:
            line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
    
    #結束部分
    elif ReplyData[0:16] == "BroadcastEditEnd":#廣播設定結束
        if NowStep == "ㄅ" or (NowStep == "ㄇ(1)" or NowStep == "ㄆ(2)"):#每個步驟都有結束設定
            line_bot_api.reply_message(event.reply_token,TextSendMessage("設定結束啦~"))
            rds.hset("user:%s"%user_id,"step","5")#回完成步
            
            RichMenuFunctionEnd(user_id, "DownManage")  
            rds.hdel("APersonCanUsingRichMenu","DownManageBroadcastSettingClicked")#讓其他人可用
        else:
            line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
    #- - - - - - - - - - - #
        
        
    #- - - - 打掃功能 - - - #
    #開始部分
    elif ReplyData[0:21] == "CleaningReportSetting":#打掃功能設定     
        if CanStartFunction(user_id,"DownManage",False,event.reply_token,"DownManageCleaningReportSettingClicked"): 
            RichMenuFunctionStart(user_id, "DownManageCleaningReportSettingClicked")   
            rds.hset("APersonCanUsingRichMenu","DownManageCleaningReportSettingClicked",user_id)#不能重複使用
            
            if rds.exists("CleaningReporting"):#回報時休想改
                RichMenuFunctionEnd(user_id, "DownManage")
                line_bot_api.reply_message(event.reply_token,TextSendMessage("在打掃股長回報時沒辦法使用！等打掃時間結束再來吧！"))
                rds.hdel("APersonCanUsingRichMenu","DownManageCleaningReportSettingClicked")#讓其他人可用                                                          
            else:
                if NowStep == "5":#其他時間不會發生
                    actList = [PostbackTemplateAction(label='重選股長',data='CleaningReoprtRechoosePeople'),PostbackTemplateAction(label='開啟/關閉要求回報',data='CleaningReportAskEdit'),PostbackTemplateAction(label='結束設定',data='CleaningReportEditEnd')]
                    line_bot_api.reply_message(event.reply_token,TemplateSendMessage(alt_text='I.打掃功能設定',template=ButtonsTemplate(title="I.打掃功能設定",text='除了要求回報時間請找作者處理\n，你可以做這些事喔 !',actions = actList)))
                    rds.hset("user:%s"%user_id,"step","I")#前進一步
                else:
                    RichMenuFunctionEnd(user_id, "DownManage")#有關步數的系統需檢查步數(因可用重新註冊Template來改變步數，所以須限制)
                    rds.hdel("APersonCanUsingRichMenu","DownManageCleaningReportSettingClicked")#讓其他人可用
                    line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
    
    #重選股長(有嘗試過直接銜接重選股長第D步，但是會牽扯到改字與步數重疊，用RichMenu已用完的就可以啟用，要修正行數度>重寫行數，執行應該不會比較快)
    elif ReplyData[0:28] == "CleaningReoprtRechoosePeople":#重選股長確認
        if NowStep == "I":
            actList = [PostbackTemplateAction(label='沒錯。',data='DelCleaning&sure&YES') , PostbackTemplateAction(label='按錯而已啦',data='DelCleaning&sure&NO')] 
            line_bot_api.reply_message(event.reply_token,TemplateSendMessage(alt_text='認真要重選?',template=ConfirmTemplate(text='認真要重選打掃股長?',actions = actList)))
            rds.hset("user:%s"%user_id,"step","D")#導向到第D步
        else:
            line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
    
    #開關部分    
    elif ReplyData[0:21] == "CleaningReportAskEdit":#打掃回報開關召喚
        if NowStep == "I":
            SwitchJSONMaking("Cleaning")#暫時的改變不會被洗掉，但太久就會，所以要船隻賢就要調整
            FlexMessage = json.load(open('開關.json','r',encoding='utf-8'))
            line_bot_api.reply_message(event.reply_token, FlexSendMessage('II(2).打掃回報開關',FlexMessage))
            rds.hset("user:%s"%user_id,"step","II(2)")#前進一步
        else:
            line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
    elif ReplyData[0:23] == "CleaningReportAskSwitch":#打掃開關使用
        if NowStep == "II(2)":
            if rds.get("DoReport").decode("utf-8") == "0":#關閉，要開啟
                rds.set("DoReport",1)
            else:#開啟，要關閉
                rds.set("DoReport",0)
            SwitchJSONMaking("Cleaning")#調好再製作
            FlexMessage = json.load(open('開關.json','r',encoding='utf-8'))
            line_bot_api.reply_message(event.reply_token, FlexSendMessage('II(2).打掃回報開關',FlexMessage))
        else:
            line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
    
    #結束部分
    elif ReplyData[0:21] == "CleaningReportEditEnd":#打掃功能設定結束
        if NowStep == "I" or NowStep == "II(2)":#每個步驟都有結束設定
            line_bot_api.reply_message(event.reply_token,TextSendMessage("設定結束哩~"))
            rds.hset("user:%s"%user_id,"step","5")#回完成步
            
            RichMenuFunctionEnd(user_id, "DownManage") 
            rds.hdel("APersonCanUsingRichMenu","DownManageCleaningReportSettingClicked")#讓其他人可用
        else:
            line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
    #- - - - - - - - - - - #
    
    #- - - 重新開始- - - - #
    #開始
    elif ReplyData[0:7] == "Restart":  
        if CanStartFunction(user_id,"DownManage",False,event.reply_token,"DownManageRestartClicked"): 
            RichMenuFunctionStart(user_id, "DownManageRestartClicked")  
            rds.hset("APersonCanUsingRichMenu","DownManageRestartClicked",user_id)#不能重複使用
            
            if NowStep == "5":#其他時間不會發生
                if rds.llen("UnRegisterUser") == 0:#全部人註冊完才能用(這兩個功能都是)
                    actList = [PostbackTemplateAction(label='重設管理員',data='REsettingManager&start'),PostbackTemplateAction(label='全部重新開始',data='REsettingALL&start'),PostbackTemplateAction(label='不需要了',data='REsettingEnd')]
                    line_bot_api.reply_message(event.reply_token,TemplateSendMessage(alt_text='壹.重新開始相關功能',template=ButtonsTemplate(title="壹.重新開始相關功能",text='想感受賦予他人權力的感覺?\n還是想結束一切?\n這邊的強大功能任您使用~',actions = actList)))
                    rds.hset("user:%s"%user_id,"step","壹")#前進一步
                else:
                    NotFinishRegister = ""
                    for i in rds.lrange("UnRegisterUser",0,-1):
                        NotFinishRegister = NotFinishRegister + i.decode("utf-8") + " "
                    line_bot_api.reply_message(event.reply_token,TextSendMessage("還有人沒註冊完不能使用這個喔！以下為未註冊的人，拜託他們註冊!\n\n%s"%NotFinishRegister))
                    RichMenuFunctionEnd(user_id, "DownManage") 
                    rds.hdel("APersonCanUsingRichMenu","DownManageRestartClicked")#讓其他人可用
            else:
                RichMenuFunctionEnd(user_id, "DownManage")#有關步數的系統需檢查步數(因可用重新註冊Template來改變步數，所以須限制)
                rds.hdel("APersonCanUsingRichMenu","DownManageRestartClicked")#讓其他人可用
                line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
        
    #重設管理員部分
    elif ReplyData[0:16] == "REsettingManager":
        if NowStep == "壹":#召喚JSON
            if ReplyData[17:22] == "start":
                REsettingManagerJSONMaking()#把字變紅色用
                FlexMessage = json.load(open('重選管理員.json','r',encoding='utf-8'))
                line_bot_api.reply_message(event.reply_token, FlexSendMessage('貳(1).增加/減少管理員',FlexMessage))
                rds.hset("user:%s"%user_id,"step","貳(1)")#前進一步
        elif NowStep == "貳(1)":#操作JSON
            if ReplyData[17:20] == "num":#選號碼中
                num = ReplyData[21:]
                if rds.hget("Number_Id",num) in rds.lrange("Cleaning_Id",0,-1):#一個人不可以同時為管理員與打掃股長，會出問題
                    line_bot_api.reply_message(event.reply_token,TextSendMessage("他/她已經是打掃股長了，不能再當管理員！"))
                else:
                    handleWay = ""
                    if rds.hget("Number_Id",num) in rds.lrange("Manager_Id", 0, -1) or (num == "師" and rds.get("Teacher_Id") in rds.lrange("Manager_Id", 0, -1)):#是原本的管理員(記得換成user_id!)
                        handleWay = "Deleteing"
                    else:#不是原本的管理員
                        handleWay = "Adding"
                        
                    if rds.exists("%sManager"%handleWay) and (bytes(num,"utf-8") in rds.lrange("%sManager"%handleWay, 0, -1)):#是選過的，取消選取
                        rds.lrem("%sManager"%handleWay,0,num)
                    else:#增加
                        rdsRpush("%sManager"%handleWay,num)
                        
                    line_bot_api.reply_message(event.reply_token,TextSendMessage(ChoosingManagerAddHasChoosenNumersTextToReplyWords("")))#函式名就是功能名
            elif ReplyData[17:20] == "Fin":#決定結束
                estimateManagerNLen = rds.llen("Manager_Id")
                if rds.exists("DeleteingManager") and rds.llen("DeleteingManager") != 0:
                    estimateManagerNLen = estimateManagerNLen - rds.llen("DeleteingManager")#扣掉
                if rds.exists("AddingManager") and rds.llen("AddingManager") != 0:#加上增加的數量
                    estimateManagerNLen = estimateManagerNLen + rds.llen("AddingManager")
                    
                if estimateManagerNLen <= 0:#代表會沒有管理員，不行
                    line_bot_api.reply_message(event.reply_token,TextSendMessage("這樣會沒有管理員 ! 我不予許 !\n再繼續挑挑看，至少要一個管理員"))
                else:
                    replyWords = "參(1).請確認選擇是否正確 : \n\n"
                    replyWords = ChoosingManagerAddHasChoosenNumersTextToReplyWords(replyWords) + "\n\n"
                    if rds.exists("DeleteingManager") and rds.llen("DeleteingManager") != 0:#有要刪除原本管理員，要提醒
                        replyWords = replyWords + "！！！！！！！！！！！！！！\n管理員被刪除將收回所有權限，將不能使用管理員選單中的大部分功能(只剩「一些實用功能」)\n！！！！！！！！！！！！！！" + "\n\n"
                    replyWords = replyWords + "選對就按下確定吧 !"
                    actList = [PostbackTemplateAction(label='確定',data='REsettingManager&Assurance1&YES') , PostbackTemplateAction(label='回上一步',data='REsettingManager&Assurance1&NO')] 
                    line_bot_api.reply_message(event.reply_token,TemplateSendMessage(alt_text='參(1).請確認選擇是否正確 :',template=ConfirmTemplate(text=replyWords,actions = actList)))#alt_text也會出現在跳出的視窗，所以必須改
                    rds.hset("user:%s"%user_id,"step","參(1)")#前進一步
        elif NowStep == "參(1)":#確認選擇正確1
            if ReplyData[17:27] == "Assurance1":#確認選擇正確1
                if ReplyData[28:31] == "YES":
                    replyWords = "肆(1).最終確認 : \n\n"
                    if rds.hget("user:%s"%user_id,"number") in rds.lrange("DeleteingManager", 0, -1):#要刪除自己的管理員特權，要提醒
                        replyWords = replyWords + "!!刪除自己的管理員權限不可逆!!" + "\n\n"
                    replyWords = replyWords + "這很重要，真的確定要改了嗎?"
                    actList = [PostbackTemplateAction(label='我確定',data='REsettingManager&Assurance2&YES') , PostbackTemplateAction(label='我再想一下',data='REsettingManager&Assurance2&NO')] 
                    line_bot_api.reply_message(event.reply_token,TemplateSendMessage(alt_text='肆(1).最終確認 :',template=ConfirmTemplate(text=replyWords,actions = actList)))#alt_text也會出現在跳出的視窗，所以必須改
                    rds.hset("user:%s"%user_id,"step","肆(1)")#前進一步
                else:#No
                    rds.hset("user:%s"%user_id,"step","貳(1)")#回貳(1)步
                    line_bot_api.reply_message(event.reply_token,TextSendMessage("您的選擇沒刪，可以回去繼續選摟~"))
        elif NowStep == "肆(1)":#確認選擇正確2
            if ReplyData[17:27] == "Assurance2":#確認選擇正確2
                if ReplyData[28:31] == "YES":
                    canBack = True
                    Changer = rds.hget("user:%s"%user_id,"name").decode("utf-8")
                    if rds.exists("DeleteingManager") and rds.llen("DeleteingManager") != 0:#在選擇時已確定是Manager，直接刪OK
                        for i in rds.lrange("DeleteingManager",0,-1):
                            DeletedId = rds.hget("Number_Id",i.decode("utf-8")).decode("utf-8")
                            rds.lrem("Manager_Id",0,DeletedId)#除名單
                            
                            if line_bot_api.get_rich_menu_id_of_user(DeletedId) == config.get("RM_DownManage","id") or line_bot_api.get_rich_menu_id_of_user(DeletedId) == config.get("RM_MiddleManage","id"):                                
                                line_bot_api.link_rich_menu_to_user(DeletedId, config.get("RM_MiddleNormal","id"))#停用管理員RichMenu
                                rds.hdel("user:%s"%DeletedId,"UsingRichMenu")#把使用紀錄刪除才可
                            else:
                                UsingClickedRichMenu = rds.hget("user:%s"%DeletedId,"UsingRichMenu").decode("utf-8")
                                if "Clicked" in UsingClickedRichMenu and UsingClickedRichMenu != "RightDeleteAccountClicked":#不是使用刪除帳號RichMenu，但使用RichMenu中(刪除帳號RichMenu用完會回歸Right，不影響RichMenu放置)
                                    if bytes(UsingClickedRichMenu,"utf-8") in rds.hkeys("APersonCanUsingRichMenu"):#正在用的是只能一個人用的RcihMenu，要讓別人可以用
                                        rds.hdel("APersonCanUsingRichMenu",UsingClickedRichMenu)#讓其他人可用
                                    line_bot_api.link_rich_menu_to_user(DeletedId, config.get("RM_MiddleNormal","id"))#停用管理員RichMenu
                                    rds.hdel("user:%s"%DeletedId,"UsingRichMenu")#把使用紀錄刪除才可
                                    rds.hset("user:%s"%DeletedId,"step","5")#強制回歸完成步
                                    rds.delete("ChangedNums")#刪除所有可能暫存變數(因不會有人使用重新開始功能，暫存變數只可能有這一個)
                                    
                            if user_id == DeletedId:#刪除自己的管理員特權
                                line_bot_api.push_message(DeletedId,TextSendMessage("你的管理員權限已被自已去除惹"))#提醒被停用
                                canBack = False
                            else:
                                line_bot_api.push_message(DeletedId,TextSendMessage("你被 %s 去除管理員權限了，很抱歉！\n\n如果您正在使用刪除帳號功能，會等您用完再去除\n\n使用其他者已強制結束使用"%Changer))#提醒被停用
                    
                        rds.delete("DeleteingManager")#這些只是暫時的變數，必須除掉
                    if rds.exists("AddingManager") and rds.llen("AddingManager") != 0:#加上增加的數量
                        for i in rds.lrange("AddingManager",0,-1):
                            AddId = rds.hget("Number_Id",i.decode("utf-8")).decode("utf-8")
                            rdsRpush("Manager_Id",AddId)#加名單
                            if line_bot_api.get_rich_menu_id_of_user(AddId) == config.get("RM_MiddleNormal","id"):
                                line_bot_api.link_rich_menu_to_user(AddId, config.get("RM_MiddleManage","id"))#變為管理員RichMenu
                                rds.hdel("user:%s"%AddId,"UsingRichMenu")#把使用紀錄刪除才可
                            line_bot_api.push_message(AddId,TextSendMessage("恭喜！你被 %s 選為管理員了！"%Changer))#提醒有權限
                            
                        rds.delete("AddingManager")#這些只是暫時的變數，必須除掉
                        
                    rds.hset("user:%s"%user_id,"step","5")#回貳(1)步
                    line_bot_api.reply_message(event.reply_token,TextSendMessage("Ok，管理員全部變更完成啦！"))  
                    if canBack:#刪除自己的管理員特權就不用了
                        RichMenuFunctionEnd(user_id, "DownManage") 
                    rds.hdel("APersonCanUsingRichMenu","DownManageRestartClicked")#讓其他人可用
                else:#No
                    rds.hset("user:%s"%user_id,"step","貳(1)")#回完成步
                    line_bot_api.reply_message(event.reply_token,TextSendMessage("您的選擇沒刪，可以回去 選人的地方(貳(1)步) 繼續選摟~")) 
        else:
            line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
            
    #全部重新開始
    elif ReplyData[0:12] == "REsettingALL":
        if NowStep == "壹":#確認1
            if ReplyData[13:18] == "start":
                actList = [PostbackTemplateAction(label='對',data='REsettingALL&Assured1') , PostbackTemplateAction(label='不',data='REsettingEnd')] 
                line_bot_api.reply_message(event.reply_token,TemplateSendMessage(alt_text='貳(2).重置確認 :',template=ConfirmTemplate(text="貳(2).重置確認 :\n\n除了已更改的廣播文字，會清除「全部」資料，也就是全部重來\n\n確定要醬嗎？",actions = actList)))
                rds.hset("user:%s"%user_id,"step","貳(2)")#前進一步
        elif NowStep == "貳(2)":#確認2
            if ReplyData[13:21] == "Assured1":
                actList = [PostbackTemplateAction(label='對對',data='REsettingALL&Assured2') , PostbackTemplateAction(label='不不',data='REsettingEnd')] 
                line_bot_api.reply_message(event.reply_token,TemplateSendMessage(alt_text='參(2).重置再確認 :',template=ConfirmTemplate(text="參(2).重置再確認 :\n\n分數 與 註冊的所有資料都會消失\n\n真確定要醬嗎？",actions = actList)))
                rds.hset("user:%s"%user_id,"step","參(2)")#前進一步
        elif NowStep == "參(2)":#確認3
            if ReplyData[13:21] == "Assured2":
                actList = [PostbackTemplateAction(label='對對對',data='REsettingALL&Assured3') , PostbackTemplateAction(label='不不不',data='REsettingEnd')] 
                line_bot_api.reply_message(event.reply_token,TemplateSendMessage(alt_text='肆(2).重置最終確認 :',template=ConfirmTemplate(text="肆(2).重置最終確認 :\n\n接下來就真的會重置了，無法復原，不需要重新開始請不要確定，請認真想清楚\n\n認真確定要醬嗎？",actions = actList)))
                rds.hset("user:%s"%user_id,"step","肆(2)")#前進一步
        elif NowStep == "肆(2)":#重置開始
            if ReplyData[13:21] == "Assured3":
                for i in rds.hkeys("Number_Id"):#已不會再未註冊完成時做，所以OK
                    Id = rds.hget("Number_Id",i.decode("utf-8")).decode("utf-8")
                    Token = rds.hget("user:%s"%Id,"access_token").decode("utf-8")
                    send_message(Token, "重製作業已啟動，所有服務都會中止")
                    send_message(Token, "真的")
                    send_message(Token, "極其")
                    send_message(Token, "高度")
                    send_message(Token, "非常")
                    send_message(Token, "超級")
                    send_message(Token, "宇宙")
                    send_message(Token, "世紀")
                    send_message(Token, "無敵")              
                    send_message(Token, "萬分")                  
                    send_message(Token, "深深")
                    send_message(Token, "地感謝您的使用。")#要提醒  
                    send_message(Token, "如果真的結束了，請封鎖或退好友Line Bot，才不會收到更多訊息")
                    line_bot_api.unlink_rich_menu_from_user(Id)#刪除RichMenu
                    
                SleepBroadcastList = rds.lrange("BroadcastWord:午休", 0, -1)
                CleaningBroadcastList = rds.lrange("BroadcastWord:打掃", 0, -1)
                TotalStudentNum = int(rds.get("TotalStudentNum").decode("utf-8"))
                rds.flushall()#把所有rds刪除
                rds.set("TotalStudentNum",TotalStudentNum)#把學生總數弄回來
                setData()#一開始的rds要弄回來              
                for i in SleepBroadcastList:
                    rdsRpush("BroadcastWord:午休", i.decode("utf-8"))#廣播文字的rds要弄回來 
                for i in CleaningBroadcastList:
                    rdsRpush("BroadcastWord:打掃", i.decode("utf-8"))#廣播文字的rds要弄回來 
                    
                for i in range(1,TotalStudentNum+1):
                    ExcelNum = i + 1#1號在B2格
                    worksheet.update("B%i"%ExcelNum, 80)#改回原分數

                line_bot_api.reply_message(event.reply_token,TextSendMessage("重置完成了。\n\n發送 註冊開始!! 到群組從頭開始\n\n感謝您的使用"))
        else:
            line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
            
            
    #結束
    elif ReplyData[0:12] == "REsettingEnd":
        if NowStep == "壹" or (NowStep == "貳(1)" or "(2)" in NowStep):#每個步驟都有結束設定
            if NowStep == "貳(1)":
                if rds.exists("DeleteingManager"):
                    rds.delete("DeleteingManager")#這些只是暫時的變數，必須除掉
                if rds.exists("AddingManager"):
                    rds.delete("AddingManager")#這些只是暫時的變數，必須除掉
                    
            line_bot_api.reply_message(event.reply_token,TextSendMessage("OK，慎重決定是好事 !"))
            rds.hset("user:%s"%user_id,"step","5")#回完成步
            
            RichMenuFunctionEnd(user_id, "DownManage") 
            rds.hdel("APersonCanUsingRichMenu","DownManageRestartClicked")#讓其他人可用
        else:
            line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
    #- - - - - - - - - - -#
    
    #- - 編輯全員分數- - - #
    #開始，查看全員分數
    elif ReplyData[0:15] == "ManageEditPoint":
        if CanStartFunction(user_id,"DownManage",False,event.reply_token,"DownManageManageEditPointClicked"):#避免還沒切換又被要求第二次              
            RichMenuFunctionStart(user_id, "DownManageManageEditPointClicked")   
            rds.hset("APersonCanUsingRichMenu","DownManageManageEditPointClicked",user_id)#不能重複使用
            
            
            if rds.exists("CleaningReporting"):#回報時休想改             
                RichMenuFunctionEnd(user_id, "DownManage")
                line_bot_api.reply_message(event.reply_token,TextSendMessage("在打掃股長回報時沒辦法使用！等打掃時間結束再來吧！"))
                rds.hdel("APersonCanUsingRichMenu","DownManageCleaningReportSettingClicked")#讓其他人可用                                                          
            else:
                if NowStep == "5":#其他時間不會發生     
                    send_message(rds.hget("user:%s"%user_id,"access_token").decode("utf-8"), "訊息製作中，請稍候...")#這真的要一段時間
                    CheckingScoreJSONMaking("Manage","null")#改變JSON成有目前分數版本
                    FlexMessage = json.load(open('查看分數.json','r',encoding='utf-8'))
                    line_bot_api.reply_message(event.reply_token, FlexSendMessage('一.查看原始分數',FlexMessage))
                    rds.hset("user:%s"%user_id,"step","一")#前進一步
                else:
                    RichMenuFunctionEnd(user_id, "DownManage")#有關步數的系統需檢查步數(因可用重新註冊Template來改變步數，所以須限制)
                    rds.hdel("APersonCanUsingRichMenu","DownManageManageEditPointClicked")#讓其他人可用
                    line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
                
    #召喚加扣分表
    elif ReplyData[0:23] == "ManageStartEditingPoint":
        if NowStep == "一":
            FlexMessage = json.load(open('管理員加扣分.json','r',encoding='utf-8'))
            line_bot_api.reply_message(event.reply_token, FlexSendMessage('T.加扣分',FlexMessage))
            rds.hset("user:%s"%user_id,"step","T")#前進一步
        else:
            line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
            
    #使用加扣分表
    elif ReplyData[0:18] == "ManageEditingPoint":
        if NowStep == "T":
            #加扣分中
            if ReplyData[19:22] == "Num":
                changedNum = int(ReplyData[28:])
                ExcelNum = changedNum + 1#1號在B2格
                OriginalScore = int(worksheet.get("B%i"%ExcelNum).first())#拿到分數
                if ReplyData[23:27] == "Plus":          
                    newScore = OriginalScore + 1#算分          
                    line_bot_api.reply_message(event.reply_token,TextSendMessage("%i號 的分數從 %i 加為 %i"%(changedNum, OriginalScore, newScore)))
                else:#minus
                    newScore = OriginalScore - 1#算分          
                    line_bot_api.reply_message(event.reply_token,TextSendMessage("%i號 的分數從 %i 減為 %i"%(changedNum, OriginalScore, newScore)))
                worksheet.update("B%i"%ExcelNum,newScore)#改分數
                
                if not rds.exists("ChangedNums") or (rds.exists("ChangedNums") and bytes(str(changedNum), "utf-8") not in rds.hkeys("ChangedNums")):#在ChangedNums裡的所有key沒有這個號碼
                    rds.hset("ChangedNums", str(changedNum), OriginalScore)#記錄誰被改和原始分數(只記錄第一次改動)
                if bytes(str(newScore), "utf-8") == rds.hget("ChangedNums", str(changedNum)):#redis裡的資料都是string的byte，所以換成bytes的東西也要是string才能比較
                    if rds.hlen("ChangedNums") == 1:
                        rds.delete("ChangedNums")#實驗結果，似乎只剩一個key-value時不給刪，所以刪全部
                    else:
                        rds.hdel("ChangedNums", str(changedNum))#分數被改回原本的值，刪掉
                    
            #結束編輯
            elif ReplyData[19:22] == "Fin":
                ChangeScoreAccureJSONMaking("Manage","null")
                FlexMessage = json.load(open('編輯分數確認.json','r',encoding='utf-8'))#這裡不用confirmTemplate因為她有字數限制，Flex沒有
                line_bot_api.reply_message(event.reply_token, FlexSendMessage('下.確認是否更改',FlexMessage))
                rds.hset("user:%s"%user_id,"step","下")#前進一步        
        else:
            line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
    
    #確認是否加扣分 + 改動結束
    elif ReplyData[0:20] == "ManageCheckEditPoint":
        if NowStep == "下":
            if ReplyData[21:23] == "OK":#改！因為直接在sheet上運算，只要提醒被改的人就完事
                Changer = rds.hget("user:%s"%user_id,"name").decode("utf-8")
                for i in rds.hkeys("ChangedNums"):#提醒被改分數了
                    num = i .decode("utf-8")
                    OriginalScore = rds.hget("ChangedNums",num).decode("utf-8")#拿到原始分數
                    newScore = worksheet.get("B%i"%(int(num) + 1)).first()
                    if bytes(num,"utf-8") in rds.lrange("UnRegisterUser",0,-1):#有註冊的才提醒，醬沒註冊完也可用
                        NumbersId = rds.hget("Number_Id",num).decode("utf-8")
                        send_message(rds.hget("user:%s"%NumbersId,"access_token").decode("utf-8"), "你的分數被 %s 從 %s分 變為 %s分 了！"%(Changer,OriginalScore,newScore))            
                rds.delete("ChangedNums")#暫存變數要刪掉
                
                line_bot_api.reply_message(event.reply_token,TextSendMessage("全部更改完成！醬就全部OK了！"))
                rds.hset("user:%s"%user_id,"step","5")#回完成步   
                RichMenuFunctionEnd(user_id, "DownManage") 
                rds.hdel("APersonCanUsingRichMenu","DownManageManageEditPointClicked")#讓其他人可用
            else:#Not OK
                line_bot_api.reply_message(event.reply_token, TextSendMessage("更改的分數都沒動，可以回去繼續改了"))
                rds.hset("user:%s"%user_id,"step","T")#回到T步
        else:
            line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
            
    #結束
    elif ReplyData[0:18] == "ManageEndEditPoint":
        if NowStep == "一" or NowStep == "T":        
            if NowStep == "T":
                for i in rds.hkeys("ChangedNums"):
                   number = i.decode("utf-8")
                   OriginalScore = int(rds.hget("ChangedNums",number))#拿到原始分數(變成int了，應該不用decode)
                   worksheet.update("B%i"%(int(number)+1),OriginalScore)#因直接在sheet上運算，要改回分數                 
                rds.delete("ChangedNums")#暫存變數要刪掉
                
            line_bot_api.reply_message(event.reply_token,TextSendMessage("編輯功能結束！"))
            rds.hset("user:%s"%user_id,"step","5")#回完成步   
            RichMenuFunctionEnd(user_id, "DownManage") 
            rds.hdel("APersonCanUsingRichMenu","DownManageManageEditPointClicked")#讓其他人可用
        else:
            line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
    #- - - - - - - - - - -#
        
    elif ReplyData[0:8] == "DownBack":#切換回中間RichMenu(有兩個!要注意)
        if (bytes(user_id,"utf-8") in rds.lrange("Manager_Id", 0, -1)):#管理者
            ChangeRichMenu(user_id, "DownManage","DownManageDownBackClicked", "MiddleManage")
        elif (rds.exists("Cleaning_Id") and bytes(user_id,"utf-8") in rds.lrange("Cleaning_Id", 0, -1)):#打掃股長
            ChangeRichMenu(user_id, "DownCleaning", "DownCleaningDownBackClicked", "MiddleCleaning")
    #------------------------------------------#
    
    
    #--------------打掃股長功能-----------------#
    elif ReplyData[0:17] == "CleaningFunction":#打掃股長功能
        ChangeRichMenu(user_id, "MiddleCleaning","MiddleCleaningCleaningFunctionClicked", "DownCleaning")
        
    #- - 不幹打掃股長- - - #
    #開始，問是暫時還是永遠不當
    elif ReplyData[0:14] == "DeleteCleaning":
        if CanStartFunction(user_id,"DownCleaning",False,event.reply_token,"DownCleaningDeleteCleaningClicked"):#避免還沒切換又被要求第二次              
            RichMenuFunctionStart(user_id, "DownCleaningDeleteCleaningClicked")  
            rds.hset("APersonCanUsingRichMenu","DownCleaningDeleteCleaningClicked",user_id)#不能重複使用
            
            if NowStep == "5":#其他時間不會發生
                if rds.exists("QuittingCleaning:%s"%user_id):#正在要求同意
                    receiverNum = rds.hget("QuittingCleaning:%s"%user_id,"Replacement").decode("utf-8")
                    if rds.hexists("QuittingCleaning:%s"%user_id,"CanAsking") == False:
                        line_bot_api.reply_message(event.reply_token,TextSendMessage("您在徵求 %s號 的同意接手工作，在他/她決定前無法使用這個按鈕\n\n但！您之後只要點一次按鈕，我就發訊提醒(騷擾)他/她，幫您催回覆"%receiverNum))
                        rds.hset("QuittingCleaning:%s"%user_id,"CanAsking","1")
                    else:#催回覆                   
                        receiverId = rds.hget("Number_Id",receiverNum).decode("utf-8")
                        send_message(rds.hget("user:%s"%receiverId,"access_token").decode("utf-8"), "快回幫不幫打掃股長！(在催了！)")
                        line_bot_api.reply_message(event.reply_token,TextSendMessage("您在徵求 %s號 的同意接手工作，在他/她決定前無法使用這個按鈕\n\n已幫您催回覆"%receiverNum))
                        
                    RichMenuFunctionEnd(user_id, "DownCleaning")  
                    rds.hdel("APersonCanUsingRichMenu","DownCleaningDeleteCleaningClicked")#讓其他人可用
                elif rds.exists("CleaningTemporaryReplace:%s"%user_id):#已經暫時委託別人
                    StartWorkingDay = rds.hget("CleaningTemporaryReplace:%s"%user_id,"StartWorkingDay").decode("utf-8")
                    line_bot_api.reply_message(event.reply_token,TextSendMessage("您已經暫時不用回報，委託他人期間無法使用此功能，直到 %s 您才可再次使用"%StartWorkingDay))
                    RichMenuFunctionEnd(user_id, "DownCleaning") 
                    rds.hdel("APersonCanUsingRichMenu","DownCleaningDeleteCleaningClicked")#讓其他人可用
                else:
                    actList = [PostbackTemplateAction(label='暫時不幹',data='DeleteingCleaningStart&temporary'),PostbackTemplateAction(label='完全不幹',data='DeleteingCleaningStart&enternally'),PostbackTemplateAction(label='只是看看',data='EndDeleteingCleaning')]
                    line_bot_api.reply_message(event.reply_token,TemplateSendMessage(alt_text='H.選擇時間',template=ButtonsTemplate(title="H.選擇時間",text='要請假暫時不能回報？\n還是真的不想幹了？\n這邊可以提供幫助！',actions = actList)))
                    rds.hset("user:%s"%user_id,"step","H")#前進一步
            else:
                RichMenuFunctionEnd(user_id, "DownCleaning")#有關步數的系統需檢查步數(因可用重新註冊Template來改變步數，所以須限制)
                rds.hdel("APersonCanUsingRichMenu","DownCleaningDeleteCleaningClicked")#讓其他人可用
                line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
                
    #選號碼(代替者
    elif ReplyData[0:22] == "DeleteingCleaningStart":
        if NowStep == "H":        
            quittingTime = ReplyData[23:]
            rds.hset("QuittingCleaning:%s"%user_id, "Time", quittingTime)#把不幹的時間存起來(可能有多人同時不幹，用user_id分辨)
            
            FlexMessage = json.load(open('替代打掃股長選擇.json','r',encoding='utf-8'))#這裡不用confirmTemplate因為她有字數限制，Flex沒有
            line_bot_api.reply_message(event.reply_token, FlexSendMessage('He.選擇替代工作的人',FlexMessage))
            rds.hset("user:%s"%user_id,"step","He")#前進一步        
        else:
            line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
            
    #暫時->選時間；永遠->確認1
    elif ReplyData[0:34] == "DeleteingCleaningChooseReplacement":
        if NowStep == "He":        
            num = ReplyData[35:]
            quittingTime = rds.hget("QuittingCleaning:%s"%user_id, "Time").decode("utf-8")
            if bytes(num,"utf-8") in rds.lrange("UnRegisterUser",0,-1):#沒註冊的人不能寄訊息，無法同意，不能拜託
                line_bot_api.reply_message(event.reply_token,TextSendMessage("他/她沒有註冊完成，沒辦法幫您的忙，再回去選其他人吧！"))
            elif rds.hget("Number_Id",num) in rds.lrange("Manager_Id",0,-1) and quittingTime == "enternally":#一個人不可以同時為管理員與打掃股長，會出問題(未註冊不會是管理員，增減管理員功能在註冊好後才開放) ps:暫時代理只是代理回報，不影響RichMenu，因此不受此限
                line_bot_api.reply_message(event.reply_token,TextSendMessage("他/她是管理員，沒辦法同時成為全職打掃股長，再回去選其他人吧！"))
            elif rds.exists("Cleaning_Id") and rds.hget("Number_Id",num) in rds.lrange("Cleaning_Id",0,-1):#不可以是打掃股長
                line_bot_api.reply_message(event.reply_token,TextSendMessage("他/她也是打掃股長，不能管兩個掃區，再回去選其他人吧！")) 
            else:
                isSpare = True
                for i in rds.lrange("Cleaning_Id",0,-1):
                    cleaningId = i.decode("utf-8")
                    if cleaningId != user_id:#是其他打掃股長
                        if rds.exists("QuittingCleaning:%s"%cleaningId) and rds.hget("QuittingCleaning:%s"%cleaningId,"Replacement").decode("utf-8") == num:#已有委託
                            isSpare = False
                            line_bot_api.reply_message(event.reply_token,TextSendMessage("他/她已經被其他打掃股長委託了，再回去選其他人吧！")) 
                        elif rds.exists("CleaningTemporaryReplace:%s"%cleaningId) and rds.hget("CleaningTemporaryReplace:%s"%cleaningId,"ReplacerId") == rds.hget("Number_Id",num):#已接受委託
                            isSpare = False
                            line_bot_api.reply_message(event.reply_token,TextSendMessage("他/她已經接受其他打掃股長委託了，再回去選其他人吧！")) 
                
                if isSpare:#經過重重篩選後真的沒事的人
                    rds.hset("QuittingCleaning:%s"%user_id, "Replacement", num)#把替換的人存起來
                                   
                    if quittingTime == "temporary":#暫時->選時間
                        FlexMessage = json.load(open('打掃股長不幹天數選擇.json','r',encoding='utf-8'))#這裡不用confirmTemplate因為她有字數限制，Flex沒有
                        line_bot_api.reply_message(event.reply_token, FlexSendMessage('Li(1).選擇不幹的天數',FlexMessage))
                        rds.hset("user:%s"%user_id,"step","Li(1)")#前進一步        
                    elif quittingTime == "enternally":#永遠->確認1
                        actList = [PostbackTemplateAction(label='幹不下去',data='DeleteingCleaningFinChooseAll') , PostbackTemplateAction(label='繼續為民服務',data='EndDeleteingCleaning')] 
                        line_bot_api.reply_message(event.reply_token,TemplateSendMessage(alt_text='Li(2).確認是否放棄 :',template=ConfirmTemplate(text="Li(2).確認是否放棄 :\n\n您將不用回報，但也會失去打掃股長權限，無法使用相關功能\n\n確定要 %s號 代替您工作？"%num,actions = actList)))
                        rds.hset("user:%s"%user_id,"step","Li(2)")#前進一步
        else:
            line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
            
    #最終確認
    elif ReplyData[0:29] == "DeleteingCleaningFinChooseAll":
        if NowStep[0:2] == "Li":    
            word = "Be.最終確認 :\n\n"
            quittingTime = rds.hget("QuittingCleaning:%s"%user_id, "Time").decode("utf-8")
            Replacement = rds.hget("QuittingCleaning:%s"%user_id, "Replacement").decode("utf-8")

            if quittingTime == "temporary":#暫時
                quittingDays = ReplyData[30:]
                NowTime = datetime.datetime.now()
                NowDate = "%i月%i日"%(NowTime.month, NowTime.day)          
                EndDate = CalculateStartWorkingDate(NowTime.year, NowTime.month, NowTime.day, int(quittingDays))
                rds.hset("QuittingCleaning:%s"%user_id, "StartWorkingDay", EndDate)#把開工日期存起來
                word = word + "你確定從 %s 開始休息，到 %s 才重新開工，期間監督與回報工作交給 %s號？\n\n(期間您仍可用打掃股長選單)"%(NowDate, EndDate, Replacement)
            elif quittingTime == "enternally":#永遠
                word = word + "真的確定要 %s號 代替您工作？\n\n要求訊息無法收回，一言既出四馬難追，請認真想過才下決定"%Replacement

            actList = [PostbackTemplateAction(label='確定不幹！',data='DeleteingCleaningDone') , PostbackTemplateAction(label='繼續貢獻社會',data='EndDeleteingCleaning')] 
            line_bot_api.reply_message(event.reply_token,TemplateSendMessage(alt_text='Be.最終確認 :',template=ConfirmTemplate(text=word,actions = actList)))
            rds.hset("user:%s"%user_id,"step","Be")#前進一步             
        else:
            line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
            
    #發送要求
    elif ReplyData[0:21] == "DeleteingCleaningDone":
        if NowStep == "Be": 
            asker = rds.hget("user:%s"%user_id,"name").decode("utf-8")
            receiverNum = rds.hget("QuittingCleaning:%s"%user_id, "Replacement").decode("utf-8") 
            receiverId = rds.hget("Number_Id",receiverNum).decode("utf-8") 
            
            receiverStep = rds.hget("user:%s"%receiverId,"step").decode("utf-8")
            rds.hset("QuittingCleaning:%s"%user_id, "ReplacementStep", receiverStep)#要記住原本在第幾步(需要優先處理這個事件)
            rds.hset("user:%s"%receiverId,"step", "！！重要訊息！！")
            
            word = "！！重要訊息！！ :\n\n"     
            quittingTime = rds.hget("QuittingCleaning:%s"%user_id, "Time").decode("utf-8")
            if quittingTime == "temporary":#暫時
                EndDate = rds.hget("QuittingCleaning:%s"%user_id, "StartWorkingDay").decode("utf-8") 
                word = word + "%s希望您可以暫時幫他/她 監督與回報打掃情形 ，到 %s 他/她就會回來工作，總之就是在打掃時回應我就好~，要不要幫幫忙？\n\n！這就是最終決定，無法反悔！"%(asker, EndDate)
            elif quittingTime == "enternally":#永遠
                word = word + "%s希望您可以 代替他/她的打掃股長身分(含掃區與手下) ，您將可以使用特殊打掃股長功能，但須在打掃時回應我(回報)，要不要幫幫忙？\n\n！這就是最終決定，無法反悔！"%asker
                
            actList = [PostbackTemplateAction(label='我要幫！',data="DeleteingCleaningAsking&Agree&%s"%user_id) , PostbackTemplateAction(label='委婉拒絕',data="DeleteingCleaningAsking&Disagree&%s"%user_id)] 
            line_bot_api.push_message(receiverId,TemplateSendMessage(alt_text='！！重要訊息！！ :',template=ConfirmTemplate(text=word,actions = actList)))
            
            line_bot_api.reply_message(event.reply_token,TextSendMessage("要求訊息已送出，等對方同意後會通知您，在這之前還是麻煩您了!"))
            rds.hset("user:%s"%user_id,"step","5")#回完成步
            RichMenuFunctionEnd(user_id, "DownCleaning") 
            rds.hdel("APersonCanUsingRichMenu","DownCleaningDeleteCleaningClicked")#讓其他人可用
        else:
            line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
            
    #對方是否同意，同意就真執行
    elif ReplyData[0:23] == "DeleteingCleaningAsking":  
        if NowStep == "！！重要訊息！！": 
            if rds.exists("CleaningReporting"):
                line_bot_api.reply_message(event.reply_token,TextSendMessage("抱歉！打掃股長鄭在回報，在這時候回覆會出問題，等打掃時間結束就可以回了，真的很抱歉！"))
            else:
                if ReplyData[24:29] == "Agree":#接手！
                    askerId = ReplyData[30:]
                    quittingTime = rds.hget("QuittingCleaning:%s"%askerId, "Time").decode("utf-8")
                    if quittingTime == "temporary":#暫時，把資料轉換到另一個永遠變數
                        endDate = rds.hget("QuittingCleaning:%s"%askerId, "StartWorkingDay").decode("utf-8")
                        rds.hset("CleaningTemporaryReplace:%s"%askerId,"ReplacerId",user_id)
                        rds.hset("CleaningTemporaryReplace:%s"%askerId,"StartWorkingDay",endDate)
                        
                        line_bot_api.push_message(askerId,TextSendMessage("對方已同意幫忙！那在 %s 之前都不用回報搂！"%endDate))
                        line_bot_api.reply_message(event.reply_token,TextSendMessage("更改完成！等打掃時就知道要做甚麼了~"))
                    elif quittingTime == "enternally":#永遠，轉換打掃股長工作
                        rds.lrem("Cleaning_Id",0,askerId)
                        rdsRpush("Cleaning_Id",user_id)   #Id
                        LeadArea = rds.hget("user:%s"%askerId,"LeadSection").decode("utf-8")
                        rds.hdel("user:%s"%askerId,"LeadSection")
                        rds.hset("user:%s"%user_id,"LeadSection",LeadArea)#領導區域
                        for i in rds.lrange("CleaningSection:%s"%askerId,0,-1):
                            if i != rds.hget("user:%s"%user_id,"number"):#不能管理自己
                                rdsRpush("CleaningSection:%s"%user_id, i.decode("utf-8"))#領導的人
                        rds.delete("CleaningSection:%s"%askerId)
                        #rds.delete("CleaningSection:%s"%LeadArea)#不用刪除掃區內的人
                        
                        line_bot_api.push_message(askerId,TextSendMessage("已同意接手！那您的打掃股長權限權被收回了\n\n除了正在使用刪除帳號功能會等您用完再收回，如果在使用任何功能都會強制中斷，造成驚嚇非常抱歉"))
                        line_bot_api.reply_message(event.reply_token,TextSendMessage("更改完成！您就是新的打掃股長了，合作愉快~"))
                        
                        if rds.hget("user:%s"%askerId,"step").decode("utf-8") == "5":#未用RichMenu
                            if rds.hget("user:%s"%askerId,"UsingRichMenu").decode("utf-8") == "MiddleCleaning" or rds.hget("user:%s"%askerId,"UsingRichMenu").decode("utf-8") == "DownCleaning":#只有這兩種需要主動切換
                                line_bot_api.link_rich_menu_to_user(askerId, config.get("RM_MiddleNormal","id"))#Cleaning換NoemalRichMenu
                                rds.hdel("user:%s"%askerId,"UsingRichMenu")#把使用紀錄刪除才可
                        else:#正在用RichMenu，強制停止功能
                            UsingClickedRichMenu = rds.hget("user:%s"%askerId,"UsingRichMenu").decode("utf-8")
                            if bytes(UsingClickedRichMenu,"utf-8") in rds.hkeys("APersonCanUsingRichMenu"):#正在用的是只能一個人用的RcihMenu，要讓別人可以用
                                rds.hdel("APersonCanUsingRichMenu",UsingClickedRichMenu)#讓其他人可用
                            if UsingClickedRichMenu != "RightDeleteAccountClicked":#使用這個會回到Right，對RichMenu無影響
                                line_bot_api.link_rich_menu_to_user(askerId,config.get("RM_MiddleNormal","id"))#Cleaning換NoemalRichMenu
                                rds.hdel("user:%s"%askerId,"UsingRichMenu")#把使用紀錄刪除才可
                            rds.hset("user:%s"%askerId,"step","5")#強制回歸完成步
                            rds.delete("CleaningChangedNums")#要刪除所有可能的暫存變數
                            #rds.delete("QuittingCleaning:%s"%askerId)#發送拜託後就不能用此功能，所以不會有 #要刪除所有可能的暫存變數
                        if line_bot_api.get_rich_menu_id_of_user(user_id) == config.get("RM_MiddleNormal","id"):#能接打掃股長的人只有平民
                            line_bot_api.link_rich_menu_to_user(user_id, config.get("RM_MiddleCleaning","id"))#Noemal換Cleaning的RichMenu   
                            rds.hdel("user:%s"%user_id,"UsingRichMenu")#把使用紀錄刪除才可
                            
                        
                elif ReplyData[24:32] == "Disagree":     
                    askerId = ReplyData[33:]      
                    send_message(rds.hget("user:%s"%askerId,"access_token").decode("utf-8"), "很抱歉，您要求幫忙的委託人不願意幫忙，麻煩您繼續當打掃股長了！")
                    line_bot_api.reply_message(event.reply_token,TextSendMessage("回絕成功！可以繼續做您要做的事了"))
                     
                OriginalStep = rds.hget("QuittingCleaning:%s"%askerId,"ReplacementStep").decode("utf-8")
                rds.hset("user:%s"%user_id,"step", OriginalStep)#把接收者步數變回來
                rds.delete("QuittingCleaning:%s"%askerId)#把暫存變數刪除
        else:
            line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
            
    #結束
    elif ReplyData[0:20] == "EndDeleteingCleaning":
        if (NowStep == "H" or NowStep == "He") or (NowStep == "Li(2)" or NowStep == "Be"):        
            line_bot_api.reply_message(event.reply_token,TextSendMessage("OK！那就繼續麻煩您了！"))
            rds.delete("QuittingCleaning:%s"%user_id)#把暫存變數刪除
            rds.hset("user:%s"%user_id,"step","5")#回完成步   
            RichMenuFunctionEnd(user_id, "DownCleaning") 
            rds.hdel("APersonCanUsingRichMenu","DownCleaningDeleteCleaningClicked")#讓其他人可用
        else:
            line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
    #- - - - - - - - - - -#
        
    #- - -重選管理的人- - -#
    elif ReplyData[0:23] == "CleaningRechooseFellows":#直接連接第步即可
        if CanStartFunction(user_id,"DownCleaning",True,"null","null"):#避免還沒切換又被要求第二次  
            RichMenuFunctionStart(user_id, "DownCleaningCleaningRechooseFellowsClicked")
                 
            if NowStep == "5":#完成註冊才可用
                actList = [PostbackTemplateAction(label='沒錯。',data='DelCrew&sure&YES') , PostbackTemplateAction(label='按錯而已啦',data='DelCrew&sure&NO')] 
                line_bot_api.reply_message(event.reply_token,TemplateSendMessage(alt_text='認真要重選?',template=ConfirmTemplate(text='認真要重選你管的人和區域?\n (作者:把人與區域分開好麻煩~)',actions = actList)))
                rds.hset("user:%s"%user_id,"step","f")#到第f步
        
            else:#仍要顧慮步數才可(步數不對，退回)
                line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
                RichMenuFunctionEnd(user_id, "DownCleaning")
    #- - - - - - - - - - -#
    
    #- - -股長應做事項- - -#
    elif ReplyData[0:16] == "CleaningToDoList":#顯視股長應做事項
        if CanStartFunction(user_id,"DownCleaning",True,"null","null"):#避免還沒切換又被要求第二次  
            RichMenuFunctionStart(user_id, "DownCleaningCleaningToDoListClicked")      
        
            FlexMessage = json.load(open('股長應做事項.json','r',encoding='utf-8'))
            line_bot_api.reply_message(event.reply_token, FlexSendMessage('工作內容 : ',FlexMessage))
                
            RichMenuFunctionEnd(user_id,"DownCleaning")
    #- - - - - - - - - - -#
    
    #- - -編輯組員分數- - -#
    #開始，查看全員分數
    elif ReplyData[0:18] == "CleaningEditPoint":
        if CanStartFunction(user_id,"DownCleaning",False,event.reply_token,"DownCleaningCleaningEditPointClicked"):#避免還沒切換又被要求第二次              
            RichMenuFunctionStart(user_id, "DownCleaningCleaningEditPointClicked")   
            rds.hset("APersonCanUsingRichMenu","DownCleaningCleaningEditPointClicked",user_id)#不能重複使用
            
            if NowStep == "5":#其他時間不會發生     
                CleaningSection = rds.hget("user:%s"%user_id,"LeadSection").decode("utf-8")
                CheckingScoreJSONMaking("Cleaning",CleaningSection)#改變JSON成有目前分數版本
                FlexMessage = json.load(open('查看分數.json','r',encoding='utf-8'))
                line_bot_api.reply_message(event.reply_token, FlexSendMessage('001.查看原始分數(%s)'%CleaningSection,FlexMessage))
                rds.hset("user:%s"%user_id,"step","001")#前進一步
            else:
                RichMenuFunctionEnd(user_id, "DownCleaning")#有關步數的系統需檢查步數(因可用重新註冊Template來改變步數，所以須限制)
                rds.hdel("APersonCanUsingRichMenu","DownCleaningCleaningEditPointClicked")#讓其他人可用
                line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
                
    #召喚加扣分表
    elif ReplyData[0:25] == "CleaningStartEditingPoint":
        if NowStep == "001":
            CleaningSection = rds.hget("user:%s"%user_id,"LeadSection").decode("utf-8")
            CleaningEditScoreJSONMaking(CleaningSection)
            FlexMessage = json.load(open('打掃股長加扣分.json','r',encoding='utf-8'))
            line_bot_api.reply_message(event.reply_token, FlexSendMessage('010.加扣分(%s)'%CleaningSection,FlexMessage))
            rds.hset("user:%s"%user_id,"step","010")#前進一步
        else:
            line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
          
    #使用加扣分表
    elif ReplyData[0:20] == "CleaningEditingPoint":
        if NowStep == "010":
            #加扣分中
            if ReplyData[21:24] == "Num":
                changedNum = int(ReplyData[30:])
                ExcelNum = changedNum + 1#1號在B2格
                OriginalScore = int(worksheet.get("B%i"%ExcelNum).first())#拿到分數
                if ReplyData[25:29] == "Plus":          
                    newScore = OriginalScore + 1#算分          
                    line_bot_api.reply_message(event.reply_token,TextSendMessage("%i號 的分數從 %i 加為 %i"%(changedNum, OriginalScore, newScore)))
                else:#minus
                    newScore = OriginalScore - 1#算分          
                    line_bot_api.reply_message(event.reply_token,TextSendMessage("%i號 的分數從 %i 減為 %i"%(changedNum, OriginalScore, newScore)))
                worksheet.update("B%i"%ExcelNum,newScore)#改分數
                
                if not rds.exists("CleaningChangedNums") or (rds.exists("CleaningChangedNums") and bytes(str(changedNum), "utf-8") not in rds.hkeys("CleaningChangedNums")):#在CleaningChangedNums裡的所有key沒有這個號碼
                    rds.hset("CleaningChangedNums", str(changedNum), OriginalScore)#記錄誰被改和原始分數(只記錄第一次改動)
                if bytes(str(newScore), "utf-8") == rds.hget("CleaningChangedNums", str(changedNum)):#redis裡的資料都是string的byte，所以換成bytes的東西也要是string才能比較
                    if rds.hlen("CleaningChangedNums") == 1:
                        rds.delete("CleaningChangedNums")#實驗結果，似乎只剩一個key-value時不給刪，所以刪全部
                    else:
                        rds.hdel("CleaningChangedNums", str(changedNum))#分數被改回原本的值，刪掉
                    
            #結束編輯
            elif ReplyData[21:24] == "Fin":
                CleaningSection = rds.hget("user:%s"%user_id,"LeadSection").decode("utf-8")
                ChangeScoreAccureJSONMaking("Cleaning",CleaningSection)
                FlexMessage = json.load(open('編輯分數確認.json','r',encoding='utf-8'))#這裡不用confirmTemplate因為她有字數限制，Flex沒有
                line_bot_api.reply_message(event.reply_token, FlexSendMessage('011.確認是否更改(%s)'%CleaningSection,FlexMessage))
                rds.hset("user:%s"%user_id,"step","011")#前進一步        
        else:
            line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))

    #確認是否加扣分 + 改動結束
    elif ReplyData[0:22] == "CleaningCheckEditPoint":
        if NowStep == "011":
            if ReplyData[23:25] == "OK":#改！因為直接在sheet上運算，只要提醒被改的人就完事
                Changer = rds.hget("user:%s"%user_id,"name").decode("utf-8")
                for i in rds.hkeys("CleaningChangedNums"):#提醒被改分數了
                    num = i .decode("utf-8")
                    OriginalScore = rds.hget("CleaningChangedNums",num).decode("utf-8")#拿到原始分數
                    newScore = worksheet.get("B%i"%(int(num) + 1)).first()
                    if bytes(num,"utf-8") not in rds.lrange("UnRegisterUser",0,-1):#有註冊的才提醒，醬沒註冊完也可用
                        NumbersId = rds.hget("Number_Id",num).decode("utf-8")
                        send_message(rds.hget("user:%s"%NumbersId,"access_token").decode("utf-8"), "你的分數被 %s 從 %s分 變為 %s分 了！"%(Changer,OriginalScore,newScore))            
                rds.delete("CleaningChangedNums")#暫存變數要刪掉
                
                line_bot_api.reply_message(event.reply_token,TextSendMessage("全部更改完成！醬就全部OK了！"))
                rds.hset("user:%s"%user_id,"step","5")#回完成步   
                RichMenuFunctionEnd(user_id, "DownCleaning") 
                rds.hdel("APersonCanUsingRichMenu","DownCleaningCleaningEditPointClicked")#讓其他人可用
            else:#Not OK
                line_bot_api.reply_message(event.reply_token, TextSendMessage("更改的分數都沒動，可以回去繼續改了"))
                rds.hset("user:%s"%user_id,"step","010")#回到T步
        else:
            line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
   
    #結束
    elif ReplyData[0:20] == "CleaningEndEditPoint":
        if NowStep == "001" or NowStep == "010":        
            if NowStep == "010":
                for i in rds.hkeys("CleaningChangedNums"):
                   number = i.decode("utf-8")
                   OriginalScore = int(rds.hget("CleaningChangedNums",number))#拿到原始分數(變成int了，應該不用decode)
                   worksheet.update("B%i"%(int(number)+1),OriginalScore)#因直接在sheet上運算，要改回分數        
                   
                rds.delete("CleaningChangedNums")#暫存變數要刪掉
                
            line_bot_api.reply_message(event.reply_token,TextSendMessage("編輯功能結束！"))
            rds.hset("user:%s"%user_id,"step","5")#回完成步   
            RichMenuFunctionEnd(user_id, "DownCleaning") 
            rds.hdel("APersonCanUsingRichMenu","DownCleaningCleaningEditPointClicked")#讓其他人可用
        else:
            line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
    #- - - - - - - - - - -#
    
    #elif ReplyData[0:8] == "DownBack":#切換回中間RichMenu(已寫在Manage的DownBack)
        #ChangeRichMenu(user_id, "DownCleaning","DownCleaningDownBackClicked", "MiddleCleaning")
    #------------------------------------------#
    
    elif ReplyData == "0":#萬一RichMenu真的卡住了，人類會下意識猛按，空白RichMenu是會回傳0(做RichMenu設的)，所以猛按就傳到Right，Right回去時就會校正身分
        if rds.hget("user:%s"%user_id,"UsingRichMenu").decode("utf-8")[-7:] != "Clicked":#最後幾個字不能是Clicked(代表這是功能RichMenu，是故意要卡住的，不能讓他逃脫) PS.測試結果，如果字串<7字元不會Out of bound，python很神奇
            if rds.hexists("user:%s"%user_id,"Escape") != True:
                rds.hset("user:%s"%user_id,"Escape",3)
            newNum = int(rds.hget("user:%s"%user_id,"Escape").decode("utf-8")) - 1    
            rds.hset("user:%s"%user_id,"Escape",newNum)
            time.sleep(2)#間格2s，在2s內連按3次就觸發
            if int(rds.hget("user:%s"%user_id,"Escape").decode("utf-8")) <= 0:
                line_bot_api.link_rich_menu_to_user(user_id, config.get("RM_Right","id"))  
                rds.hset("user:%s"%user_id,"UsingRichMenu","Right")    
            rds.hset("user:%s"%user_id,"Escape",3)     
    #===========================================================================#
    
    
    #================================打掃回報系統====================================#
    #開始，得到誰沒打掃(已將可能把打掃股長職位刪除的功能封鎖，可以安心使用戰存變數)
    elif ReplyData[0:13] == "GettingReport":
        if NowStep == "回":
            if ReplyData[14:17] == "num":#選號碼
                num = ReplyData[18:]
                if rds.exists("UnCleanNum:%s"%user_id) and (bytes(num,"utf-8") in rds.lrange("UnCleanNum:%s"%user_id, 0, -1)):#是選過的，取消選取
                    rds.lrem("UnCleanNum:%s"%user_id,0,num)#有三個打掃股長，所以要用user_id區別暫存變數
                else:#增加
                    rdsRpush("UnCleanNum:%s"%user_id,num)
                Chosen = ""
                for i in rds.lrange("UnCleanNum:%s"%user_id, 0, -1):
                    Chosen = Chosen + i.decode("utf-8") + ","
                Chosen = Chosen.rstrip(",")
                line_bot_api.reply_message(event.reply_token,TextSendMessage("目前你選了 : "+Chosen))
            elif ReplyData[14:17] == "fin":
                Chosen = ""
                if rds.llen("UnCleanNum:%s"%user_id) != 0:
                    SortRedisList("UnCleanNum:%s"%user_id)
                    for i in rds.lrange("UnCleanNum:%s"%user_id, 0, -1):
                        Chosen = Chosen + i.decode("utf-8") + ","
                    Chosen = Chosen.rstrip(",")
                    
                    actList = [PostbackTemplateAction(label='選對！',data='GetReportEnsure&YES') , PostbackTemplateAction(label='手殘選錯',data='GetReportEnsure&NO')] 
                    line_bot_api.reply_message(event.reply_token,TemplateSendMessage(alt_text='報.確認有無手殘',template=ConfirmTemplate(text="報.確認有無手殘\n\n\t沒打掃的人如下：\n\t%s\n\n有沒有選錯？"%Chosen,actions = actList)))
                else:#都有打掃
                    actList = [PostbackTemplateAction(label='沒在騙',data='GetReportEnsure&YES') , PostbackTemplateAction(label='被發現了..',data='GetReportEnsure&NO')] 
                    line_bot_api.reply_message(event.reply_token,TemplateSendMessage(alt_text='報.測謊',template=ConfirmTemplate(text="報.測謊\n\n是真的都有打掃...\n還是只是懶了監督??",actions = actList)))
                rds.hset("user:%s"%user_id,"step","報")        
            elif ReplyData[14:21] == "goodBoi":#都有打掃
                actList = [PostbackTemplateAction(label='沒在騙',data='GetReportEnsure&YES') , PostbackTemplateAction(label='被發現了..',data='GetReportEnsure&NO')] 
                line_bot_api.reply_message(event.reply_token,TemplateSendMessage(alt_text='報.測謊',template=ConfirmTemplate(text="報.測謊\n\n是真的都有打掃...\n還是只是懶了監督??",actions = actList)))
                rds.hset("user:%s"%user_id,"step","報")     
        else:
            line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
    
    
    #結束，確認是否正確
    elif ReplyData[0:15] == "GetReportEnsure":
        if NowStep == "報":
            if ReplyData[16:19] == "YES":
                word = ""
                CleaningName = rds.hget("user:%s"%user_id,"name").decode("utf-8")
                if not rds.exists("UnCleanNum:%s"%user_id) or rds.llen("UnCleanNum:%s"%user_id) == 0:               
                    word = "好吧！那回報結束了！辛苦了！"
                else:                    
                    for i in rds.lrange("UnCleanNum:%s"%user_id,0,-1):
                        AbsentNum = int(i.decode("utf-8"))
                        NewScore = int(worksheet.get("B%i"%(AbsentNum+1)).first()) - 1
                        worksheet.update("B%i"%(AbsentNum+1),NewScore)#改分數
                        
                        if i not in rds.lrange("UnRegisterUser",0,-1):#有註冊才發通知
                            AbsentId = rds.hget("Number_Id", AbsentNum).decode("utf-8")
                            send_message(rds.hget("user:%s"%AbsentId,"access_token").decode("utf-8"), "您好像沒打掃，被%s扣1分了，剩%i分\n下次要打掃喔！"%(CleaningName,NewScore))
                            
                        word = "改完分數了！那回報結束了！辛苦了！"
                    
                for i in rds.lrange("Manager_Id",0,-1):
                    ManagerId = i.decode("utf-8")
                    ManagerAccessToken = rds.hget("user:%s"%ManagerId,"access_token").decode("utf-8")
                    send_message(ManagerAccessToken, "%s完成回報！"%CleaningName)
    
                if rds.exists("UnCleanNum:%s"%user_id):
                    rds.delete("UnCleanNum:%s"%user_id)#刪暫存變數
                OriginalStep = rds.hget("CleaningOriginalStep",user_id).decode("utf-8")
                rds.hset("user:%s"%user_id,"step", OriginalStep)#搞回來遠本的步驟
                rds.hdel("CleaningOriginalStep",user_id)
                
                if OriginalStep != "5":
                    word = word + "\n您可以繼續回去做被打斷的事了！"
                line_bot_api.reply_message(event.reply_token,TextSendMessage(word))
            else:#No
                line_bot_api.reply_message(event.reply_token,TextSendMessage("沒關係，回去繼續選吧！\n(第回步)"))
                rds.hset("user:%s"%user_id,"step","回")     
        else:
            line_bot_api.reply_message(event.reply_token,TextSendMessage("%s"%ReplyWrongStep(NowStep)))
    #==============================================================================#
    
    
    
@app.route("/CheckNotify/<user_id>")#因為網址是傳出去就固定，在Line方面用Button或函式分類，最後仍要傳網址，就可能被重複點擊，所以只能在網路連結後做分類，符合者再重新導向
def CheckNotify(user_id):
    step = rds.hget("user:%s"%user_id,"step").decode("utf-8")
    if  step == "2":#步數確認(做完第2步)，等註冊好Notify才可以前進一步
        return redirect(create_auth_link(user_id))#LineNotify註冊
    else:
        return "<h1>%s</h1>"%ReplyWrongStep(step)
    
def ReplyWrongStep(step):
    if step != "5":#5就是完成步
        if step == "！！重要訊息！！":
            return "請優先回答要不要接手打掃股長！"
        elif step in "回報":#在回報
            return "請優先回報！"
        else:
            return "你應該做第%s步!!請照順序回答!!\n(第%s步 = 「%s.」開頭的訊息)"%(step,step,step)
    else:
        return "這個按鈕已經沒用了喔~"


def ChangeRichMenu(user_id,Origin,FromClicked,To):#重複太多次了，很適合寫函式(換選單)
    if  rds.hexists("user:%s"%user_id,"UsingRichMenu") != True or rds.hget("user:%s"%user_id,"UsingRichMenu").decode("utf-8") == Origin:#避免還沒切換又被要求第二次(切換到目的RichMenu後之後的切換要求(在Original的RichMenu要求)都無效)
        rds.hset("user:%s"%user_id,"UsingRichMenu",To)    
        while line_bot_api.get_rich_menu_id_of_user(user_id) != config.get("RM_%s"%FromClicked,"id"):    
            line_bot_api.link_rich_menu_to_user(user_id, config.get("RM_%s"%FromClicked,"id"))       
        while line_bot_api.get_rich_menu_id_of_user(user_id) != config.get("RM_FinishTo%s"%To,"id"): 
            line_bot_api.link_rich_menu_to_user(user_id, config.get("RM_FinishTo%s"%To,"id"))
        while line_bot_api.get_rich_menu_id_of_user(user_id) != config.get("RM_%s"%To,"id"):
            line_bot_api.link_rich_menu_to_user(user_id, config.get("RM_%s"%To,"id"))#切換完成
        line_bot_api.link_rich_menu_to_user(user_id, config.get("RM_%s"%To,"id"))#有時候仍會失敗，多做幾次以防萬一(不知解決法)

def RichMenuFunctionStart(user_id,Clicked):#重複太多次了，很適合寫函式(工能開始)    
    rds.hset("user:%s"%user_id,"UsingRichMenu",Clicked)    
    while line_bot_api.get_rich_menu_id_of_user(user_id) != config.get("RM_%s"%Clicked,"id"):    
        line_bot_api.link_rich_menu_to_user(user_id, config.get("RM_%s"%Clicked,"id"))      
    
def RichMenuFunctionEnd(user_id,Original):#重複太多次了，很適合寫函式(工能結束)
    while line_bot_api.get_rich_menu_id_of_user(user_id) != config.get("RM_%s"%Original,"id"):
       line_bot_api.link_rich_menu_to_user(user_id, config.get("RM_%s"%Original,"id"))#使用完成   
    line_bot_api.link_rich_menu_to_user(user_id, config.get("RM_%s"%Original,"id"))#有時候仍會失敗，多做幾次以防萬一(不知解決法)        
    time.sleep(2.5)#有包含馬上結束的功能很有可結束後又再次有先前的要求，導致重複觸發，需冷卻時間來避免如此(用完後2.5秒內不能再用同一個RichMenu，但可以馬上用其他的，不影響用戶體驗)
    rds.hset("user:%s"%user_id,"UsingRichMenu",Original)
    
def CanStartFunction(user_id,OriginalRichMenu,CanMutiPeopleUse,reply_token,ClickedRichMenu):#有可多人與不可多人#重複很多次，函式佳
    CanStart = False
    if rds.hexists("user:%s"%user_id,"UsingRichMenu") == False or rds.hget("user:%s"%user_id,"UsingRichMenu").decode("utf-8") == OriginalRichMenu:#避免還沒切換又被要求第二次(間隔很短，很難察覺吧，懶了做提醒)
        if not CanMutiPeopleUse:
            if rds.hexists("APersonCanUsingRichMenu",ClickedRichMenu):#不能重複使用#用Clicked，才可以在強制停止時找到是在用哪個RichMenu並刪除"APersonCanUsingRichMenu"
                RichMenuFunctionStart(user_id, ClickedRichMenu)  #到這裡需要反饋
                
                occupierId = rds.hget("APersonCanUsingRichMenu",ClickedRichMenu).decode("utf-8")
                occupierName = rds.hget("user:%s"%occupierId,"name").decode("utf-8")
                RichMenuFunctionEnd(user_id, OriginalRichMenu)
                line_bot_api.reply_message(reply_token,TextSendMessage("這個功能一次只能一個人用， %s正在使用這個功能，等等再用吧！"%occupierName))
                
                time.sleep(3)#這的功能執行太快，字還沒出來就結束，需要停移下
                RichMenuFunctionEnd(user_id, OriginalRichMenu)
            else:                  
                CanStart = True
        else:
            CanStart = True

    return CanStart


def DeleteAskingQuitting(Askerid):#很長+重複3次，函式較佳
    askerName = rds.hget("user:%s"%Askerid,"name").decode("utf-8")
    ReplacementNum = rds.hget("QuittingCleaning:%s"%Askerid,"Replacement").decode("utf-8")
    ReplacementId = rds.hget("Number_Id",ReplacementNum).decode("utf-8")
    line_bot_api.push_message(ReplacementId, TextSendMessage("等等！ %s 失去打掃權限了！所以不用煩惱要不要幫他/她工作了！那就沒事了~"%askerName))#通知不用回覆
    line_bot_api.push_message(Askerid, TextSendMessage("對了，要求幫忙回報的事已被取消了，可以放心！"))                                          
    rds.hset("user:%s"%ReplacementId,"step", rds.hget("QuittingCleaning:%s"%Askerid,"ReplacementStep").decode("utf-8"))#把接收者步數變回來
    rds.delete("QuittingCleaning:%s"%Askerid)#把暫存變數刪除

def DeleteTemporaryReplacement(AskerId):#很長+重複3次，函式較佳
    askerName = rds.hget("user:%s"%AskerId,"name").decode("utf-8")
    ReplacementId = rds.hget("CleaningTemporaryReplace:%s"%AskerId,"ReplacerId").decode("utf-8")
    line_bot_api.push_message(ReplacementId, TextSendMessage("快訊！ %s 失去打掃權限了！所以不用再幫他/她回報了！謝謝您這段時間的幫助！"%askerName))#通知不用回覆
    line_bot_api.push_message(AskerId, TextSendMessage("對了，暫時拜託幫忙回報的事也被取消了，可以放心！"))
    rds.delete("CleaningTemporaryReplace:%s"%AskerId)#把這個刪除就oK了
    
    
def ChoosingManagerAddHasChoosenNumersTextToReplyWords(replyWords):#很長+重複兩次，函式較佳
    AddingNum = ""
    DeleteingNum = ""
    if rds.exists("AddingManager") and rds.llen("AddingManager") != 0:
        for i in rds.lrange("AddingManager", 0, -1):
            AddingNum = AddingNum + i.decode("utf-8") + ","
        AddingNum = AddingNum.rstrip(",")
    replyWords = replyWords + "要增加的人 : " + AddingNum    
    if rds.exists("DeleteingManager") and rds.llen("DeleteingManager") != 0:               
        for i in rds.lrange("DeleteingManager", 0, -1):
            DeleteingNum = DeleteingNum + i.decode("utf-8") + ","
        DeleteingNum = DeleteingNum.rstrip(",")
    replyWords = replyWords + "\n要減少的人 : " + DeleteingNum 
    return replyWords
    
def CalculateStartWorkingDate(NowYear,NowMonth,NowDay,QuittingDays):#寫函式比較不亂
    EndDay = NowDay + QuittingDays
    if EndDay > 28:
        DaysOfThisMonth = 0
        if NowMonth == 2:
            if NowYear%4 != 0:#不整除4非閏年
                DaysOfThisMonth = 28
            else:
                if NowYear%100 == 0 and NowYear%400 != 0:#整除100不能整除400非閏年
                    DaysOfThisMonth = 28
                else:
                    DaysOfThisMonth = 29   
        elif NowMonth <= 7:           
            if NowMonth%2 == 0:
                DaysOfThisMonth = 30
            else:
                DaysOfThisMonth = 31
        else:#8-12月
            if NowMonth%2 == 0:
                DaysOfThisMonth = 31
            else:
                DaysOfThisMonth = 30
                
        if DaysOfThisMonth >= EndDay:
            return "%i月%i日"%(NowMonth, EndDay)
        else:
            if NowMonth == 12:
                return "%i月%i日"%(1, EndDay-DaysOfThisMonth)
            else:
                return "%i月%i日"%(NowMonth+1, EndDay-DaysOfThisMonth)
    else:#不會有超過問題
        return "%i月%i日"%(NowMonth, EndDay)
    

def CleaningCheckOn():
    rds.set("CleaningReporting",1)#避免在打掃回報時使用功能(規範接受委託時間與管理員亂搞)
    for i in rds.lrange("Cleaning_Id", 0, -1):
        cleanId = i.decode("utf-8")
        CleanSection = rds.hget("user:%s"%cleanId,"LeadSection").decode("utf-8")
        if rds.exists("CleaningTemporaryReplace:%s"%cleanId):#有人代替
            cleanId = rds.hget("CleaningTemporaryReplace:%s"%cleanId,"ReplacerId").decode("utf-8")
            
        OriginalStep = rds.hget("user:%s"%cleanId,"step").decode("utf-8")
        rds.hset("CleaningOriginalStep",cleanId, OriginalStep)
        rds.hset("user:%s"%cleanId,"step", "回")#用步數系統限制佳(因打掃股長and代理股長不能被要求代理，所以兩個替換步驟功能不會重疊)
        
        
        CleaningReportJSONMaking(CleanSection)
        FlexMessage = json.load(open('回報選號碼.json','r',encoding='utf-8'))        
        line_bot_api.push_message(cleanId,FlexSendMessage('回.回報時間到！',FlexMessage))#只有LineBot會讀訊息


def CleaningCheckOff():
    rds.delete("CleaningReporting")#可以使用了
     
    ManagerAccessToken = []
    for i in rds.lrange("Manager_Id",0,-1):
        ManagerId = i.decode("utf-8")
        ManagerAccessToken.append(rds.hget("user:%s"%ManagerId,"access_token").decode("utf-8"))
    count = 0#慧英heroku特性回復。用完不用刪
    for i in rds.lrange("Cleaning_Id", 0, -1):
        cleanId = i.decode("utf-8")
        rds.delete("UnCleanNum:%s"%cleanId)#刪除可能的暫存變數
        
        if rds.exists("CleaningTemporaryReplace:%s"%cleanId):#有人代替
            cleanId = rds.hget("CleaningTemporaryReplace:%s"%cleanId,"ReplacerId").decode("utf-8")
        
        if rds.hget("user:%s"%cleanId,"step").decode("utf-8") in "回報" :
            word = "截止時間到！下次請在打掃時間結束前回報好！"
                      
            OriginalStep = rds.hget("CleaningOriginalStep",cleanId).decode("utf-8")
            rds.hset("user:%s"%cleanId,"step", OriginalStep)#搞回來遠本的步驟
            if OriginalStep != "5":
                word = word + "\n您可以繼續回去做被打斷的事了！"
            rds.hdel("CleaningOriginalStep",cleanId)
            
            line_bot_api.push_message(cleanId,TextSendMessage(word))
            
            for i in ManagerAccessToken:
                CleaningName = rds.hget("user:%s"%cleanId,"name").decode("utf-8")
                send_message(i, "%s 未完成回報！"%CleaningName)
            count = count + 1
        
    if count == 0:#都有回報
       for i in ManagerAccessToken:
            send_message(i, "全部打掃股長完成回報！")

def SortRedisList(ListName):#排序才舒服(氣泡排序)
    numList = []
    for i in rds.lrange(ListName,0,-1):
        num = int(i.decode("utf-8"))
        numList.append(num)
    
    numListLen = len(numList)
    for i in range(0,numListLen-1):
        for m in range(0,numListLen-1-i):
            if numList[m] > numList[m+1]:
                temporaryPlace = numList[m]
                numList[m] = numList[m+1]
                numList[m+1] = temporaryPlace
                
    rds.delete(ListName)
    for i in numList:
        rdsRpush(ListName,i)

#每一秒呼叫Wonwon()
def Wonwon(user_id): 
    access_token = rds.hmget("user:%s"%user_id,"access_token")[0].decode('utf-8')#hmget出的是列表的byte，要編譯回utf-8 + 取第0個才可
    
    i = 0
    startTime = datetime.datetime.now()
    
    while i<= 2:
        NowTime = datetime.datetime.now()
        CalCulTime = NowTime.second - startTime.second
        if CalCulTime>=1 or CalCulTime<=-59:
            send_message(access_token, "wonwon!")
            line_bot_api.push_message(user_id,TextSendMessage("won"))
            i = i+1
            startTime = datetime.datetime.now()
        else:
             continue
         
    send_message(access_token, "finish!")
    line_bot_api.push_message(user_id,TextSendMessage("fin"))






@app.route("/broadcast", methods=['GET'])
def Send():   
    NowTime = datetime.datetime.now()
    if int(rds.get("DoBroadcast")) and rds.llen("UnRegisterUser") == 0:#要換成int才有bool作用(註冊完才有group access_token)
        access_token = rds.hget("group","access_token").decode('utf-8')
    
        if (NowTime.hour == 7 and NowTime.minute == 55) or (NowTime.hour == 15 and NowTime.minute == 50):#打掃時間
            sendWord = rds.lindex("BroadcastWord:打掃",random.randint(0,9)).decode("utf-8")          
            send_message(access_token, "%s"%sendWord)      
        elif NowTime.hour == 12 and NowTime.minute == 30  :#午休時間
            sendWord = rds.lindex("BroadcastWord:午休",random.randint(0,9)).decode("utf-8")             
            send_message(access_token, "%s"%sendWord)   
       
    
        
    if int(rds.get("DoReport")) and rds.llen("Cleaning_Id") != 0:#沒有打掃股長註冊完不會啟    
        #打掃回報
        if NowTime.hour == 8 and NowTime.minute == 5 :
            CleaningCheckOn()
        elif NowTime.hour == 8 and NowTime.minute == 10 :
            CleaningCheckOff()
        elif NowTime.hour == 16 and NowTime.minute == 0 :
            CleaningCheckOn()
        elif NowTime.hour == 16 and NowTime.minute == 5 :
            CleaningCheckOff()
    return "sucess"

#叫醒Heroku用
@app.route("/awake", methods=['GET'])
def awake():
    NowTime = datetime.datetime.now()
    if NowTime.hour == 7 and NowTime.minute == 0 :#檢查暫時委託時限到了沒(因可能結束時間在假日，需在awake中每天呼叫)
        for i in rds.lrange("Cleaning_Id", 0, -1):
            cleanId = i.decode("utf-8")
            if rds.exists("CleaningTemporaryReplace:%s"%cleanId):#有暫時委託
                if rds.hget("CleaningTemporaryReplace:%s"%cleanId,"StartWorkingDay").decode("utf-8") == "%i月%i日"%(NowTime.month,NowTime.day):#是開工日
                    askerName = rds.hget("user:%s"%cleanId,"name").decode("utf-8")
                    ReplacementId = rds.hget("CleaningTemporaryReplace:%s"%cleanId,"ReplacerId").decode("utf-8")
                    line_bot_api.push_message(ReplacementId, TextSendMessage("%s的委託結束了！不用回報了！這段時間辛苦了！"%askerName))#通知不用回覆
                    line_bot_api.push_message(cleanId, TextSendMessage("今天是開工日！之後就要回報了喔！"))
                    rds.delete("CleaningTemporaryReplace:%s"%cleanId)#把這個刪除就oK了
        
        
        if rds.llen("UnRegisterUser") != 0:#沒註冊提醒
            group_id = rds.hget("group","group_id").decode("utf-8")
            word = "以下的人還沒註冊喔!快點註冊啦!!\n["
            for i in rds.lrange("UnRegisterUser", 0, -1):
                try:
                    word = word + str(int(i.decode('utf-8'))) +","
                except:
                    Chinese = "老" + i.decode('utf-8') + ","
                    word  = word + Chinese
            word = word.rstrip(",") + "]"
            line_bot_api.push_message(group_id, TextSendMessage(word))
    return "OK I am Up"
    

if __name__ == "__main__":
    app.run()
    
    





def SwitchJSONMaking(BroadcastOrCleaning):
    if BroadcastOrCleaning == "Broadcast":
        Title = "ㄆ(2).廣播開關"
        SwitchData = "BroadcastPowerSwitch"
        EndData = "BroadcastEditEnd"
        GetIsONPlace = "DoBroadcast"
    else:#Cleaning
        Title = "II(2).打掃回報開關"
        SwitchData = "CleaningReportAskSwitch"
        EndData = "CleaningReportEditEnd"
        GetIsONPlace = "DoReport"
        
    
    with open('開關.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    data["body"]["contents"][0]["text"] = Title#標題
    data["body"]["contents"][1]["contents"][1]["action"]["data"] = SwitchData#Switch紐ReplyData
    data["body"]["contents"][3]["action"]["data"] = EndData#結束按鈕ReplyData    
    if rds.get("%s"%GetIsONPlace).decode("utf-8") == "0":#關閉
        data["body"]["contents"][1]["contents"][0]["text"] = "現狀 : 關閉"
        data["body"]["contents"][1]["contents"][0]["color"] = "#ff0000"
    else:#開啟
        data["body"]["contents"][1]["contents"][0]["text"] = "現狀 : 開啟"
        data["body"]["contents"][1]["contents"][0]["color"] = "#0000ff"
        
    with open('開關.json', 'w', encoding='utf-8') as f:
        json.dump(data, f)

def BroadcastWordJSONMaking(Area):
    with open('廣播文字編輯器.json', 'r', encoding='utf-8') as f:
        data = json.load(f) 
    data["body"]["contents"][0]["text"] = "ㄇ(1).文字編輯 (" + Area + ")"#顯示為打掃字or午休字
    for i in range(0,10):
        nowWord = rds.lindex("BroadcastWord:%s"%Area,i).decode("utf-8")#lindex是[i]的概念
        data["body"]["contents"][i+1]["action"]["label"] = nowWord#弟2->弟11
        data["body"]["contents"][i+1]["action"]["data"] = "BroadcastWordEdit&Edit&" + Area + str(i)
    with open('廣播文字編輯器.json', 'w', encoding='utf-8') as f:
        json.dump(data, f)
        
def REsettingManagerJSONMaking():
    with open('重選管理員.json', 'r', encoding='utf-8') as f:
        data = json.load(f)   
    for i in rds.lrange("Manager_Id", 0, -1):
        Id = i.decode("utf-8")
        if bytes(Id,"utf-8") == rds.get("Teacher_Id"): 
            TotalStudentNum = int(rds.get("TotalStudentNum").decode("utf-8"))
            CalculatedNum = TotalStudentNum#用0-45比較好計算
        else:
            num = rds.hget("user:%s"%Id,"number").decode("utf-8")
            CalculatedNum = int(num) - 1
        layerNum = 4 + CalculatedNum//5 #//會無條件捨去到整數，很棒 #3是標題與3行字，從第4行加起
        xNum = CalculatedNum%5#找到行後找列(x)
        data["body"]["contents"][layerNum]["contents"][xNum]["color"] = "#ff0000"#把字變紅色
    with open('重選管理員.json', 'w', encoding='utf-8') as f:
        json.dump(data, f)
        
def CheckingScoreJSONMaking(CleaningOrManage,CleaningSection):#Cleaning,Manage共用
    if CleaningOrManage == "Manage":
        Title = "一.查看原始分數"
        TotalStudentNum = int(rds.get("TotalStudentNum").decode("utf-8"))
        numList = range(1,TotalStudentNum+1)
        StartData = "ManageStartEditingPoint"
        EndData = "ManageEndEditPoint"
    elif CleaningOrManage == "Cleaning":     
        Title = "001.查看原始分數(%s)"%CleaningSection
        numList = rds.lrange("CleaningSection:%s"%CleaningSection,0,-1)
        StartData = "CleaningStartEditingPoint"
        EndData = "CleaningEndEditPoint"
        
    #get 所有分數，變成文字
    everyFellowScore = ""
    num = 0
    for i in numList:
        if CleaningOrManage == "Manage":     
            num = i
        elif CleaningOrManage == "Cleaning":     
            num = int(i.decode("utf-8"))
            
        ExcelNum = num + 1#1號在B2格
        Score = worksheet.get("B%i"%ExcelNum).first()

        if num < 10:
            everyFellowScore = everyFellowScore + "0%i號 ： "%num + Score +" 分\n"
        else:
            everyFellowScore = everyFellowScore + "%i號 ： "%num + Score +" 分\n"

    everyFellowScore = everyFellowScore.rstrip()#附贈的網址沒有功能，要用button實現

    with open('查看分數.json', 'r', encoding='utf-8') as f:
        data = json.load(f) 
    data["body"]["contents"][0]["text"] = Title
    data["body"]["contents"][3]["text"] = everyFellowScore
    data["body"]["contents"][5]["contents"][0]["action"]["data"] = StartData
    data["body"]["contents"][5]["contents"][2]["action"]["data"] = EndData
    with open('查看分數.json', 'w', encoding='utf-8') as f:
        json.dump(data, f)
        
def ChangeScoreAccureJSONMaking(CleaningOrManage,CleaningSection):#Cleaning,Manage共用
    if CleaningOrManage == "Manage":
        title = "下.確認是否更改"
        storeNumsPlace = "ChangedNums"
        OkData = "ManageCheckEditPoint&OK"
        RejectData = "ManageCheckEditPoint&notOK"
    elif CleaningOrManage == "Cleaning":      
        title = "011.確認是否更改(%s)"%CleaningSection
        storeNumsPlace = "CleaningChangedNums"
        OkData = "CleaningCheckEditPoint&OK"
        RejectData = "CleaningCheckEditPoint&notOK"
        
    word = ""
    if rds.exists(storeNumsPlace):#已設定沒有改動就刪掉ChangesNums，所以直接醬ok
        for i in rds.hkeys(storeNumsPlace):
            number = i.decode("utf-8")
            OriginalScore = rds.hget(storeNumsPlace,number).decode("utf-8")
            newScore = worksheet.get("B%i"%(int(number) + 1)).first()
            word = word + "%s號 由 %s分 變為 %s分\n"%(number, OriginalScore, newScore)
        word = word.rstrip()#去換行
    else:#根本沒變
        word = "~沒有變動~"
    
    with open('編輯分數確認.json', 'r', encoding='utf-8') as f:
        data = json.load(f) 
    data["body"]["contents"][0]["text"] = title
    data["body"]["contents"][3]["text"] = word#text是必備的，所以用空字串測試當然不型
    data["footer"]["contents"][1]["contents"][0]["action"]["data"] = OkData
    data["footer"]["contents"][1]["contents"][2]["action"]["data"] = RejectData
    with open('編輯分數確認.json', 'w', encoding='utf-8') as f:
        json.dump(data, f)
        
def CleaningEditScoreJSONMaking(CleaningSection):
    with open('打掃股長加扣分.json', 'r', encoding='utf-8') as f:
        data = json.load(f) 
    data["body"]["contents"][0]["text"] = "010.加扣分(%s)"%CleaningSection
        
    for i in rds.lrange("CleaningSection:%s"%CleaningSection,0,-1):#CleaningSection內是號碼，把按鈕與加減分直接Append上去(剩下的兩個按鈕在footer非body，所以不影響)
        num = i.decode("utf-8")
        data["body"]["contents"].append( {
        "type": "box",
        "layout": "horizontal",
        "contents": [
          {
            "type": "text",
            "text": "%s號"%num,
            "gravity": "center",
            "align": "center"
          },
          {
            "type": "button",
            "action": {
              "type": "postback",
              "label": "十",
              "data": "CleaningEditingPoint&Num&Plus&%s"%num
            },
            "height": "sm"
          },
          {
            "type": "button",
            "action": {
              "type": "postback",
              "label": "一",
              "data": "CleaningEditingPoint&Num&down&%s"%num
            },
            "height": "sm"
          }
        ]
      })
    
    with open('打掃股長加扣分.json', 'w', encoding='utf-8') as f:
        json.dump(data, f)
        
def CleaningReportJSONMaking(CleaningSection):
    with open('回報選號碼.json', 'r', encoding='utf-8') as f:
        data = json.load(f) 
    
    count = 0   #在heroku中，變數會被重置(短時間內不會)，所以不用重設
    totalCount = 0
    buttonBox = []     
    for i in rds.lrange("CleaningSection:%s"%CleaningSection,0,-1):#CleaningSection內是號碼，把按鈕與加減分直接Append上去(剩下的兩個按鈕在footer非body，所以不影響)
        num = i.decode("utf-8")
        
        buttonBox.append( {
            "type": "button",
            "action": {
              "type": "postback",
              "label": "%s"%num,
              "data": "GettingReport&num&%s"%num
            }
          })
        count = count +1
        totalCount = totalCount + 1
        
        if count == 5 or totalCount == rds.llen("CleaningSection:%s"%CleaningSection):
            data["body"]["contents"].append( {
                                              "type": "box",
                                              "layout": "horizontal",
                                              "contents": buttonBox
                                            })
            count = 0
            buttonBox = [] 
    
    with open('回報選號碼.json', 'w', encoding='utf-8') as f:
        json.dump(data, f)