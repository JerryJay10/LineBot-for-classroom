import os
#他會直接在此資料夾執行，所以不用cd ..
os.system("git add .")
os.system("git commit -m \"update\"")
os.system("git push heroku Head:master")
