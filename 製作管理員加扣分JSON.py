import json


def make(TotalStudentNum):
    FirstLayerBoxContents = [ {
                            "type": "box",
                            "layout": "vertical",
                            "contents": [
                                          {
                              "type": "text",
                              "text": "T.加扣分",
                              "weight": "bold",
                              "size": "xl"
                            },
                            {
                              "type": "text",
                              "text": "編輯結束請按編輯完成鈕"
                            }, 
                            {
                              "type": "separator",
                              "margin": "md"
                            },]
                            }]
    
    
    for i in range(1,TotalStudentNum+1):
          FirstLayerBoxContents.append( {
            "type": "box",
            "layout": "horizontal",
            "contents": [         
                {
                "type": "text",
                "text": "%i號"%i,
                "gravity": "center",
                "align": "center"
              },
               {
                "type": "button",
                "action": {
                  "type": "postback",
                  "label": "十",
                  "data": "ManageEditingPoint&Num&Plus&%i"%i
                }
                ,
                "height": "sm"
              },
              {
                "type": "button",
                "action": {
                  "type": "postback",
                  "label": "一",
                  "data": "ManageEditingPoint&Num&down&%i"%i#不用minus因為醬+-都可以直接取得號碼，不用分開寫(down字數與Plus同)
                }
                ,
                "height": "sm"
              }
            ]
          })
            
        
      
    data = {
      "type": "bubble",
      "body": {
        "type": "box",
        "layout": "vertical",
        "contents": FirstLayerBoxContents,
        "spacing": "xs",
        "margin": "none"
      }
      ,
      "footer": {
        "type": "box",
        "layout": "vertical",
        "contents": [
          {
            "type": "button",
            "action": {
              "type": "postback",
              "label": "編輯完成鈕",
              "data": "ManageEditingPoint&Fin"
            },
            "style": "secondary",
            "height": "sm"
          },
          {
            "type": "button",
            "action": {
              "type": "postback",
              "label": "不用改了",
              "data": "ManageEndEditPoint"
            },
            "height": "sm"
          }
        ]
      }
    }
    
    import os
    os.system("echo fin 管理員加扣分.json")
    
    with open('管理員加扣分.json', 'w', encoding='utf-8') as f:
        json.dump(data, f)