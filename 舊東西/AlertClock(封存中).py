from apscheduler.schedulers.blocking import BlockingScheduler
import urllib

sched = BlockingScheduler()


@sched.scheduled_job('cron', hour = 7-23, minute='*/25')#在特定時間執行(*/25代表每25min執行一次)
                                                                               #此為 7-24(0)時每25min執行一次
def scheduled_job():
    url = "https://linebot21310.herokuapp.com/"
    connect = urllib.request.urlopen(url)

sched.start()