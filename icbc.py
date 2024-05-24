import requests
import logging
import time
import datetime
import os
import pytz
import telepot
import certifi

prevResult = ""

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36"

# 姓
LAST_NAME = ""
# 驾照号码
LICENSE_NUM = ""
# 登陆用的keyword
KEYWORD = ""

# Coordinate of burnaby claim centre
LNG = -122.9989
LAT = 49.2446

# 5-R-1: Class 5 Road Test, 7-R-1: Class 7 Road Test
EXAM_TYPE = "5-R-1" 

# 返回考试中心的数量
MAX_CENTER_WANT_TO_CHECK = 1

# 每个考试中心返回日期数量
MAX_DATE_PER_CENTER_TO_DISPLAY = 24

# Telegram API Token
TELEGRAM_TOKEN = ""
# Telegram ID
TELEGRAM_ID = ""

def now():
  return datetime.datetime.now(pytz.timezone("America/Vancouver"))

def tomorrow():
  return now() + datetime.timedelta(days=1)

def getTomorrowYYYYMMDD():
  return tomorrow().strftime('%Y-%m-%d')

def getToken():
    LOGIN_URL = "https://onlinebusiness.icbc.com/deas-api/v1/webLogin/webLogin"
    params = {
        "drvrLastName": LAST_NAME,
        "licenceNumber": LICENSE_NUM,
        "keyword": KEYWORD
    }
    rsp = requests.put(LOGIN_URL, json=params, headers={'User-Agent': USER_AGENT})
    if rsp.status_code == 200:
        logging.info("Login Success! Return Auth Token")
        return rsp.headers["Authorization"]
    else:
        logging.error("Login Failure: %s, %s", rsp.status_code, rsp.content)
        bot.sendMessage(TELEGRAM_ID, "Login Failure")
        return None

def getNearestExamCenters(token):
    logging.info("Start getting Nearest Exam Centers")
    URL = "https://onlinebusiness.icbc.com/deas-api/v1/web/getNearestPos"
    params = {
        "lng": LNG,
        "lat": LAT,
        "examType": EXAM_TYPE,
        "startDate": getTomorrowYYYYMMDD()
    }
    rsp = requests.put(
        URL,
        json=params,
        headers={'User-Agent': USER_AGENT, 'Authorization': token}
    )
    if rsp.status_code == 200:
        logging.info("Getting Nearest Exam Centers Success! Returning Results")
        return rsp.json()
    else:
        logging.error("Getting Nearest Exam Centers Failure: %s, %s", rsp.status_code, rsp.content)
        bot.sendMessage(TELEGRAM_ID, "Getting Nearest Exam Centers Failure")
        return None

def getAvailableAppointments(token, posId, centerAgency):
    logging.info("Getting Appointment Info from Agency: %s, posId: %s", centerAgency, posId)
    URL = "https://onlinebusiness.icbc.com/deas-api/v1/web/getAvailableAppointments"
    params = {
        "aPosID": posId,
        "examType": EXAM_TYPE,
        "examDate": getTomorrowYYYYMMDD(),
        "ignoreReserveTime": False,
        "prfDaysOfWeek": "[0,1,2,3,4,5,6]",
        "prfPartsOfDay": "[0,1]",
        "lastName": LAST_NAME,
        "licenseNumber": LICENSE_NUM
    }
    rsp = requests.post(
        URL,
        json=params,
        headers={'User-Agent': USER_AGENT, 'Authorization': token}
    )
    if rsp.status_code == 200:
        logging.info("Getting Appointments Success! Returning Results")
        if len(rsp.json()) == 0:
            logging.info("No appointments available for this center")
        return rsp.json()
    else:
        logging.error("Getting Appointments Failure: %s, %s", rsp.status_code, rsp.content)
        bot.sendMessage(TELEGRAM_ID, "Getting Appointments Failure")
        return None

def formatAppointments(appointments):
    # Sort by date
    res = dict()
    for appointment in appointments:
        value = {
            "startTm": appointment["startTm"],
            "dayOfWeek": appointment["appointmentDt"]["dayOfWeek"]
        }
        res.setdefault(appointment["appointmentDt"]["date"], []).append(value)
    return res

def getFormattedMessageAgency(agency):
    return f"""
    <u><b>{agency}</b></u>
    """

def getFormattedMessageDate(date, dayOfWeek, timeList):
    return f"""
    <i>Date:</i>
    {date}, {dayOfWeek}\n
    <i>Available Time:</i>
    {timeList}
    """

def run():
    token = getToken()
    time.sleep(1)
    centers = getNearestExamCenters(token)
    time.sleep(1)
    result = "" 
    for idx in range(min(MAX_CENTER_WANT_TO_CHECK, len(centers))):
        center = centers[idx]
        appointments = getAvailableAppointments(token, center["pos"]["posId"], center["pos"]["agency"])
        if len(appointments) == 0:
            logging.info("Skipping..,")
            continue
        formattedAppointments = formatAppointments(appointments)

        formattedAppointmentItems = list(formattedAppointments.items())

        formattedMessage = getFormattedMessageAgency(center["pos"]["agency"])
        result += formattedMessage

        for dateIdx in range(min(MAX_DATE_PER_CENTER_TO_DISPLAY, len(formattedAppointmentItems))):
            appointment = formattedAppointmentItems[dateIdx]
            dateStr = appointment[0]
            timeList = [d['startTm'] for d in appointment[1]]
            dayOfWeek = appointment[1][0]['dayOfWeek']
            formattedMessage = getFormattedMessageDate(dateStr, dayOfWeek, timeList)
            result += formattedMessage

    currentTime = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    global prevResult
    if result != prevResult:
        logging.warning("Timeslots Changed at " + currentTime + "!!")
        prevResult = result
        bot.sendMessage(TELEGRAM_ID, result, parse_mode="HTML")
    else:
        logging.info("Timeslots Stay the Same at " + currentTime + "!!")
    
    # Sleep for 60 seconds
    time.sleep(60)

if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    os.environ['SSL_CERT_FILE'] = certifi.where()
    bot = telepot.Bot(TELEGRAM_TOKEN)
    bot.sendMessage(TELEGRAM_ID, "Started")
    while True:
        try :
            run()
        except Exception as e:
            # Sleep for 60 seconds
            time.sleep(60)