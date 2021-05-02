import time
import json
import os
import re
import requests

from base64 import urlsafe_b64encode
from hashlib import sha256
from pixivpy3 import *
from secrets import token_urlsafe
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from typing import Callable
from urllib.parse import urlencode

class Manipulator:
	def __init__(self):
		# クラス変数の設定
		self.token = None
		self.settings = json.load(open(f'{os.path.dirname(__file__)}/settings.json'))
	
	def xpath(self, page_name: str):
		"""設定ファイルからxpath情報をロードする"""
		return self.settings['page'][page_name]['xpath']

	def url(self, page_name: str):
		"""設定ファイルからurl情報をロードする"""
		return self.settings['page'][page_name]['url']

	def user(self):
		"""設定ファイルからユーザー情報をロードする"""
		return self.settings['user']

	def auth(self):
		"""設定ファイルから認証用情報をロードする"""
		return self.settings['auth']

	def elm(self, page_name, xpath_key):
		"""指定したxpathの要素を取得する"""
		xpath = self.xpath(page_name)
		return self.driver.find_element_by_xpath(xpath[xpath_key])


class RefTokenManipulator(Manipulator):
	"""リフレッシュトークン操作機能
		APIコール用のリフレッシュトークンを取得する。
	"""

	def __init__(self):
		Manipulator.__init__(self)

		# chromedriverの設定
		driver_path = f'{os.path.dirname(__file__)}/chromedriver.exe'
		# - option
		options = Options()
		options.add_argument('--headless')	# ヘッドレス
		options.add_argument('--incognito')	# シークレットモード
		# - desire_capabilities
		caps = DesiredCapabilities.CHROME.copy()
		caps['goog:loggingPrefs'] = {'performance': 'ALL'}

		# クラス変数の設定
		self.driver = webdriver.Chrome(
			desired_capabilities=caps,
			executable_path=driver_path,
			options=options
		)
		self.token = None

	def __del__(self):
		self.driver.close()

	def fetch_ref_token(self) -> str:
		"""リフレッシュトークンを取得・返却する	
		"""
		# ログインする
		code_verifier, code_challenge = self.oauth_pkce(self.transform_sha256)
		login_params = {
			'code_challenge': code_challenge,
			'code_challenge_method': 'S256',
			'client': 'pixiv-android',
		}
		self.login(login_params)
		while True:
			if self.driver.current_url[:40] == 'https://accounts.pixiv.net/post-redirect':
				break
			time.sleep(1)

		# ログイン完了後、chromedriverのログから認可コードを抽出する
		auth_code = self.extract_auth_code()
		print(f'[INFO]AUTH_CODE ==> {auth_code}')

		# 認可コードを用いてリフレッシュトークンを取得する
		tokens = self.fetch_tokens(auth_code, code_verifier)
		return tokens['refresh_token']

	def extract_auth_code(self) -> str:
		"""chromedriverのログから認可コードを抽出する
		"""
		auth_code = None
		for row in self.driver.get_log('performance'):
			data = json.loads(row.get('message', {}))
			message = data.get('message', {})
			if message.get('method') == 'Network.requestWillBeSent':
				url = message.get('params', {}).get('documentURL')
				if url[:8] == 'pixiv://':
					auth_code = re.search(r'code=([^&]*)', url).groups()[0]
					break
		return auth_code

	def fetch_tokens(self, auth_code: str, code_verifier: str) -> dict:
		"""トークンを取得する

			Args:
				auth_code (str): 認可コード
				code_verifire (str): code_verifire
			Returns:
				(dict) トークン
					- access_token
					- refresh_token
		"""
		response = requests.post(
			self.auth()['auth_token_url'],
			data={
				"client_id": self.auth()['client_id'],
				"client_secret": self.auth()['client_secret'],
				"code": auth_code,
				"code_verifier": code_verifier,
				"grant_type": "authorization_code",
				"include_policy": "true",
				"redirect_uri": self.auth()['redirect_uri'],
			},
			headers={"User-Agent": self.auth()['user_agent']}
		)
		return response.json()

	def login(self, login_params: dict) -> None:
		"""指定したログイン情報でブラウザからログインする。
			Params:
				login_params (dict): ログインURLに付与するクエリパラメータ群
		"""
		# ページの読み込み
		url = f'{self.url("login")}?{urlencode(login_params)}'
		print(url)
		self.driver.get(url)

		btn_submit = self.elm('login', 'btn_submit')
		input_email = self.elm('login', 'inp_mail')
		input_password = self.elm('login', 'inp_pass')

		# ログイン操作を実行
		# TODO: 例外操作＠ログイン失敗／DOM取得失敗
		input_email.send_keys(self.user()['email'])
		input_password.send_keys(self.user()['password'])
		btn_submit.click()

	def transform_sha256(self, data: str) -> str:
		"""指定したデータをsha256でハッシュ化した値を返却する。
			Args:
				data: ハッシュ化対象のデータ
			Returns:
				(str): ハッシュ化後の文字列
		"""
		# sha256のハッシュ値を取得
		result = sha256(data).digest()
		# URLセーフなbase64のascii文字列として返却
		result_safe_b64 = urlsafe_b64encode(result).rstrip(b'=').decode('ascii')
		return result_safe_b64

	def oauth_pkce(self, transform_func: Callable) -> str:
		"""PKCEで使用するcode_verifierとcode_challengeを指定した関数でハッシュ化して返却する
			Args:
				data (Callable): ハッシュ関数
			Returns:
				(tuple): code_verifier, code_challenge
		"""
		code_verifier = token_urlsafe(32)
		code_challenge = transform_func(code_verifier.encode('ascii'))
		return code_verifier, code_challenge


class ImageDownloader:
	"""画像ファイル保存機能
	"""
	def __init__(self):
		# リフレッシュトークンを取得
		rtm = RefTokenManipulator()
		ref_token = rtm.fetch_ref_token()
		# 認証
		print(f'[DEBUG]REF_TOKEN ==> {ref_token}')
		self.app = AppPixivAPI()
		self.app.auth(refresh_token=ref_token)
	
	def fetch_image_all_by_userid(self, user_id: str) -> None:
		"""指定したユーザーIDの全イラストをダウンロードする。
			Args:
				user_id (str): ユーザーID
		"""
		json_result = self.app.illust_ranking()
		for illust in json_result.illusts[:3]:
			self.app.download(illust.image_urls.large)


if __name__ == '__main__':
	img_dl = ImageDownloader()
	img_dl.fetch_image_all_by_userid('')
	pass