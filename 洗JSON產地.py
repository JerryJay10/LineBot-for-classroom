import json

#記得改名子!!!
#記得改名子!!!
#記得改名子!!!
data ={
  "type": "bubble",
  "body": {
    "type": "box",
    "layout": "vertical",
    "contents": [
      {
        "type": "button",
        "action": {
          "type": "postback",
          "label": "TEST2",
          "data": "test",
          "displayText": "Did"
        }
      }
    ]
  }
}
with open('test.json', 'w', encoding='utf-8') as f:
    json.dump(data, f)
print("OK")
#記得改名子!!!