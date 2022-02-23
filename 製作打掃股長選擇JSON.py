import json

def make(TotalStudentNum):
    FirstLayerBoxContents = [
          {
            "type": "text",
            "text": "A.老師，工作還沒完!!",
            "size": "xl",
            "weight": "bold"
          },
          {
            "type": "text",
            "text": "選打掃股長!!",
            "size": "md",
            "weight": "bold"
          },
          {
            "type": "text",
            "text": "按一次選取   再按一次取消選取",
            "size": "xs"
          },
          {
            "type": "text",
            "text": "全選完再按選完鈕",
            "size": "xs"
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
                  "data": "GetCleaning&num&%i"%i
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
            
            SecondLayerBoxContent = []
            
            SecondLayerBoxContent.append({
                "type": "button",
                "action": {
                  "type": "postback",
                  "label": "全部選完鈕",#老師字太多了
                  "data": "GetCleaning&num&Fin"
                },
                "style": "secondary",
                "gravity": "bottom"
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
    os.system("echo fin 打掃股長選擇.json")
    
    with open('打掃股長選擇.json', 'w', encoding='utf-8') as f:
        json.dump(data, f)