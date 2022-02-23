import json

def make(TotalStudentNum):
    FirstLayerBoxContents = [
          {
            "type": "text",
            "text": "貳(1).增加/減少管理員",
            "size": "xl",
            "weight": "bold"
          },   
          {
            "type": "text",
            "text": "紅字者是目前管理員(不是現在選的)",
            "size": "md",
            "weight": "bold",
            "color": "#ff0000"
          },
          {
            "type": "text",
            "text": "按一次選取   再按一次取消選取",
            "size": "md"
          },
          {
            "type": "text",
            "text": "全選完再按選完鈕",
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
                  "data": "REsettingManager&num&%i"%i
                },
                "margin": "none",
                "height": "sm",
                "color": "#42659a"
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
            SecondLayerBoxContent.append({
                "type": "button",
                "action": {
                  "type": "postback",
                  "label": "師",#老師字太多了
                  "data": "REsettingManager&num&師"
                },
                "margin": "none",
                "height": "sm",
                "color": "#42659a"
              })
            
            FirstLayerBoxContents.append( {
            "type": "box",
            "layout": "horizontal",
            "contents": SecondLayerBoxContent
          })
        
        
    SecondLayerBoxContent = []
    SecondLayerBoxContent.append({
              "type": "button",
              "action": {
                "type": "postback",
                "label": "全部選完鈕",
                "data": "REsettingManager&Fin"
              },
              "style": "secondary",
              "height": "sm"
            })
    SecondLayerBoxContent.append({
              "type": "button",
              "action": {
                "type": "postback",
                "label": "不需要了",
                "data": "REsettingEnd"
              },
              "height": "sm",
            })
    FirstLayerBoxContents.append( {
      "type": "box",
      "layout": "vertical",
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
    os.system("echo fin 重選管理員.json")
    
    with open('重選管理員.json', 'w', encoding='utf-8') as f:
        json.dump(data, f)