import json

def make(TotalStudentNum):
    FirstLayerBoxContents = [
          {
            "type": "text",
            "text": "0.註冊開始!!",
            "size": "xl",
            "weight": "bold"
          },
          {
            "type": "text",
            "text": "你是誰?點座號跟我說!!",
            "size": "md"
          }
        ]
    
    count = 0
    SecondLayerBoxContent = []
    for i in range(1,TotalStudentNum+1):
        SecondLayerBoxContent.append({
                "type": "button",
                "action": {
                  "type": "postback",
                  "label": "%i"%i,
                  "data": "start&num&%i"%i
                },
                "margin": "none",
                "height": "sm"
              })
        
        count = count+1
        if count == 5:
            FirstLayerBoxContents.append( {
            "type": "box",
            "layout": "horizontal",
            "contents": SecondLayerBoxContent
          })
            
            count = 0
            SecondLayerBoxContent = []
            
        if i == TotalStudentNum:
            SecondLayerBoxContent.append({
                "type": "button",
                "action": {
                  "type": "postback",
                  "label": "師",#老師字太多了
                  "data": "start&num&師"
                },
                "margin": "none",
                "height": "sm"
              })
            
            FirstLayerBoxContents.append( {
            "type": "box",
            "layout": "horizontal",
            "contents": SecondLayerBoxContent
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
    }
    
    import os
    os.system("echo fin 座號選擇.json")
    
    with open('座號選擇.json', 'w', encoding='utf-8') as f:
        json.dump(data, f)