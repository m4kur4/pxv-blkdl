import json
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
import time

options = webdriver.ChromeOptions()
options.add_experimental_option("excludeSwitches", ["enable-logging"])

##################################################
# 設定の読み込み
##################################################
settings = json.load(open('./settings.json', 'r'))
setting_user = settings['user']
setting_driver = settings['driver']
setting_pixiv = settings['pixiv']
setting_pixiv_login = setting_pixiv['login']

##################################################
# ログイン操作
##################################################
driver_path = setting_driver['chrome']
driver = webdriver.Chrome(executable_path=driver_path)

driver.get(setting_pixiv_login['url'])
xpathes = setting_pixiv_login['xpath']

inp_mail = driver.find_element_by_xpath(xpathes['inp_mail'])
inp_pass = driver.find_element_by_xpath(xpathes['inp_pass'])
inp_mail.send_keys(setting_user['email'])
inp_pass.send_keys(setting_user['password'])

btn_login = driver.find_element_by_xpath(xpathes['btn_login'])
btn_login.click()