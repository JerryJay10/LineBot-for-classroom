from linebot import (
    LineBotApi, WebhookHandler
)
import configparser
import os


line_bot_api = LineBotApi('Y1LzBKoQn1WIslXTVLvfku5NiET/BVnwbgmrapIitiQ67UGJziyQuj4ZJqs24SMrQodeJO6cqVqKxZ43pfebDgzuQ0KkOtM/Oyp5E9BytIJqTZNbpNXNB6rODPyYhfXFcyO2Q1rnhZTp5jhhVpvo0gdB04t89/1O/w1cDnyilFU=')
config = configparser.ConfigParser()
config.read('C:/LineBot/config.ini',encoding="utf-8")#要用在上一層的config

rich_menu_list = line_bot_api.get_rich_menu_list()

for rich_menu in rich_menu_list:
    print(rich_menu.rich_menu_id)
    #刪除LineBot有，config沒有的
    '''
    have = 0
    for i in config.sections():
        if "RM" in i:            
            if rich_menu.rich_menu_id == config.get(i,"id"):
                have = 1
    
    if have == 0:
        print("del")
        line_bot_api.delete_rich_menu(rich_menu.rich_menu_id)
'''



#只刪部分RichMenu

name = input("delete(place + name)?")
for i in config.sections():
    if name in i:#有符合，刪    
    
        line_bot_api.delete_rich_menu(config.get(i,"id"))#刪linebot上的
        config.remove_section(i)#刪config裡的

            
        config.write(open("C:/LineBot/config.ini", "w"))#要write才會改變config
        config.read('C:/LineBot/config.ini',encoding="utf-8")#要在打開一次才能消除
           
        file_path = "C:/LineBot/製作RichMenu相關/RM_" + i.lstrip("RM").lstrip("_") + ".png"
        os.remove(file_path)#刪圖片
        
        print("fin del %s"%i)



print("fin delete")



