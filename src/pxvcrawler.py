import json
import os
import re
import requests
import shutil
import time

from base64 import urlsafe_b64encode
from hashlib import sha256
from pixivpy3 import *
from secrets import token_urlsafe
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from shutil import move
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
			Returns:
				(str) 認可コード
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
	def __init__(self, ref_token: str):
		"""初期化
			Args:
				ref_token (str): リフレッシュトークン
		"""
		# 認証
		print(f'[DEBUG]REF_TOKEN ==> {ref_token}')
		self.api = PixivAPI()
		self.api.auth(refresh_token=ref_token)
		time.sleep(2) # !!!XXX: APIの呼び出し後はsleep必須!!!
		self.aapi = AppPixivAPI()
		self.aapi.auth(refresh_token=ref_token)
		time.sleep(2) # !!!XXX: APIの呼び出し後はsleep必須!!!
	
	def fetch_image_all_by_userid(self, user_id: str) -> None:
		"""指定したユーザーIDの全イラストをダウンロードする。
			Args:
				user_id (str): ユーザーID
		"""
		user_info = self.fetch_user_info(user_id)

		# 画像の保存先を作っておく(作家さんの名前)
		save_dir_base = self.make_image_save_dir(user_info)

		# 全作品をループしてダウンロード
		json_result = self.api.users_works(user_id, per_page=300)
		time.sleep(2) # !!!XXX: APIの呼び出し後はsleep必須!!!
		works = json_result['response']
		debug_count = 0
		for work in works:
			self.fetch_image(work, save_dir_base)
			debug_count += 1
			if debug_count == 5:
				break

	def fetch_image(self, work: dict, save_dir_base: str) -> None:
		"""画像を保存する
		"""
		image_id = work['id']
		image_title = work['title']
		image_page_count = work['page_count']

		if image_page_count == 1:
			# 単一ページの作品
			image_url = work['image_urls']['large']
			self.aapi.download(image_url, path=save_dir_base)
			time.sleep(2) # !!!XXX: APIの呼び出し後はsleep必須!!!

			# 保存後にリネーム
			self.rename_image(save_dir_base, image_id, image_title, 0, True)
		else:
			# 複数ページの作品
			work_detail = self.api.works(image_id).response
			time.sleep(2) # !!!XXX: APIの呼び出し後はsleep必須!!!

			work_pages = work_detail[0]['metadata']['pages']
			save_dir = f'{save_dir_base}/{image_title}'

			page_count = 0
			for page in work_pages:
				image_url = page['image_urls']['large']
				os.makedirs(save_dir, exist_ok=True)
				self.aapi.download(image_url, path=save_dir)
				time.sleep(2) # !!!XXX: APIの呼び出し後はsleep必須!!!

				# 保存後にリネーム
				self.rename_image(save_dir, image_id, image_title, page_count)
				page_count += 1

	def make_image_save_dir(self, user_info: dict) -> str:
		"""指定したユーザーIDの画像保存用フォルダを作成する。
			Args:
				user_id (str): ユーザーID
			Returns:
				(str): 保存先の相対パス
		"""
		user_name = user_info['user']['name']
		save_dir = f'images/{user_name}'
		os.makedirs(save_dir, exist_ok=True)
		return save_dir

	def fetch_user_info(self, user_id: str):
		"""指定したユーザーIDのユーザー情報を取得する。
			Args:
				user_id (str): ユーザーID
		"""
		user_info = self.aapi.user_detail(user_id)
		time.sleep(2) # !!!XXX: APIの呼び出し後はsleep必須!!!
		return user_info
	
	def rename_image(self, save_dir: str, image_id: int, image_title: str, page_no: int, is_remove_page: bool = False):
		"""ファイル名をリネームする
			Args:
				save_dir (str): ファイル保存先のディレクトリパス
				image_id (int): 画像ID
				image_title (str): 画像タイトル
				page_no (int): 画像の連番
				is_remove_page (bool): 末尾のページ数を消すかどうか(デフォルトは消さない)
		"""
		image_id_str = str(image_id)
		file_name_org = f'{save_dir}/{image_id_str}_p{page_no}.jpg'

		# 置換対象の文字列を設定
		replace_target = f'{image_id_str}'
		if is_remove_page:
			replace_target += f'_p{page_no}'

		file_name = file_name_org.replace(replace_target, image_title)
		move(file_name_org, file_name)


if __name__ == '__main__':

	# リフレッシュトークンを取得
	rtm = RefTokenManipulator()
	ref_token = rtm.fetch_ref_token()

	# 画像ダウンロード実行

	idl = ImageDownloader(ref_token)
	idl.fetch_image_all_by_userid(9675329)
