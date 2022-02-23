import json

def make(TotalStudentNum):
    FirstLayerBoxContents = [
          {
            "type": "text",
            "text": "He.選擇替代工作的人",
            "size": "xl",
            "weight": "bold"
          },
          {
            "type": "text",
            "text": "監督程度與白單數量呈現正相關",
            "size": "md"
          },
          {
            "type": "text",
            "text": "所以必須有人代替你",
            "size": "md"
          },
          {
            "type": "text",
            "text": "他/她同意接手後才能不幹",
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
                  "data": "DeleteingCleaningChooseReplacement&%i"%i
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
        
        if i ==TotalStudentNum:
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
    os.system("echo fin 替代打掃股長選擇.json")
    
    with open('替代打掃股長選擇.json', 'w', encoding='utf-8') as f:
        json.dump(data, f)