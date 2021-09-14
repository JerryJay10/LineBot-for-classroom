import json


FirstLayerBoxContents = [
      {
        "type": "text",
        "text": "Li(1).選擇不幹的天數",
        "size": "xl",
        "weight": "bold"
      },
      {
        "type": "text",
        "text": "選從今天算起幾天不做",
        "size": "md"
      },
      {
        "type": "text",
        "text": "例：8/24選好不幹5天，8/29就要開工",
        "size": "xs"
      },
      {
        "type": "text",
        "text": "#在委託人同意前仍要工作",
        "size": "md"
      }
    ]

count = 0
SecondLayerBoxContent = []
for i in range(1,15):
    SecondLayerBoxContent.append({
            "type": "button",
            "action": {
              "type": "postback",
              "label": "%i"%i,
              "data": "DeleteingCleaningFinChooseAll&%i"%i
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
    
    if i ==14:
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


print(data)

with open('打掃股長不幹天數選擇.json', 'w', encoding='utf-8') as f:
    json.dump(data, f)