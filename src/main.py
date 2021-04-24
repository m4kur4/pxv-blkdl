from pixivpy3 import *
import json

if __name__ == '__main__':
  json_file = open('./settings.json', 'r')
  json_data = json.load(json_file)

  login_email = json_data['email']
  login_password = json_data['password']

  aapi = AppPixivAPI()
  aapi.login(login_email, login_password)

  json_result = aapi.illust_ranking()
  for illust in json_result.illusts[:3]:
    aapi.download(illust_urls.large)