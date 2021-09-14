from glob import glob
from os.path import splitext
from PIL import Image,ImageDraw

IconList = glob( "要合成的Icon/*.png" )#get路徑中所有png(*為萬用字元)
BGList = glob( "被合成的Icon背景/*.png" )

for png in IconList:
    Icon = Image.open(png)
    IconName = Icon.filename.lstrip("要合成的Icon\\Icon").lstrip("_")
    for BGpath in BGList:
        BG = Image.open(BGpath)
        BGname = BG.filename.lstrip("被合成的Icon背景\\")#get BG名字
             
        
        if BGname == "UnClickDemo.png":
            newImage = BG.copy()#複製新的BG圖片，在新的圖片編輯
            newImage.paste(Icon,(49,36))
            newImage.save("UnClick_%s"%IconName,quality=100)
            print("fin UnClick_%s"%IconName)
        elif BGname == "CantClickDemo.png":
            newImage = BG.copy()#複製新的BG圖片，在新的圖片編輯
            
            newIcon = Icon.copy()#用新的圖片，才不會之後Icon再使用會出問題
            for x in range(0,newIcon.width):
                for y in range(0,newIcon.height):
                    PixelColor = newIcon.getpixel((x,y))
                    newIcon.putpixel((x, y), (int(PixelColor[0]*0.85), int(PixelColor[1]*0.85), int(PixelColor[2]*0.85)))#把所有pixel改深0.15倍
            newImage.paste(newIcon,(49,36))#改身好的圖片貼上
            newImage.save("CantClick_%s"%IconName,quality=100)
            print("fin CantClick_%s"%IconName)
         
        elif BGname == "ClickedDemo.png":
            newImage = BG.copy()#複製新的BG圖片，在新的圖片編輯
            
            newIcon = Icon.copy()#用新的圖片，才不會之後Icon再使用會出問題
            for x in range(0,newIcon.width):
                for y in range(0,newIcon.height):
                    PixelColor = newIcon.getpixel((x,y))
                    newIcon.putpixel((x, y), (int(PixelColor[0]*0.5), int(PixelColor[1]*0.5), int(PixelColor[2]*0.5)))#把所有pixel改深0.5倍
            newImage.paste(newIcon,(74,61))#改身好的圖片貼上
                        
            RightCorner = Image.open("RightCorner.png")
            newImage.paste(RightCorner,(701,675),RightCorner)#右下角在paste時會不見，要補回來(記得設定mask參數，不然透明處會黑掉)
            
            newImage.save("Clicked_%s"%IconName,quality=100)
            print("fin Clicked_%s"%IconName)
