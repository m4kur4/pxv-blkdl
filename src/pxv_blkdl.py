import argparse
import json
import logging
import os
import pickle
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
from tqdm import tqdm
from typing import Callable
from urllib.parse import urlencode

class TokenManipulator:
	"""[Abstract]トークン操作機能
	"""
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


class RefTokenManipulator(TokenManipulator):
	"""リフレッシュトークン操作機能
		APIコール用のリフレッシュトークンを取得する。
	"""

	def __init__(self):
		TokenManipulator.__init__(self)

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
				(str): 認可コード
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
				(dict): トークン
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
		"""ログインする
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
		"""指定したデータをsha256でハッシュ化して返却する。
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
		# クラス変数の設定
		self.cache_manager = CacheManager()
		self.unsafe_char_filter = UnsafeCharcterFilter()

		# OAuth認証
		print(f'[INFO]REF_TOKEN ==> {ref_token}')
		self.api = PixivAPI()
		self.api.auth(refresh_token=ref_token)
		time.sleep(1) # !!!XXX: APIの呼び出し後はsleep必須!!!
		self.aapi = AppPixivAPI()
		self.aapi.auth(refresh_token=ref_token)
		time.sleep(1) # !!!XXX: APIの呼び出し後はsleep必須!!!

	def fetch_image_all_by_userid(self, user_id: str) -> None:
		"""指定したIDのユーザーが投稿した全イラストをダウンロードする。
			Args:
				user_id (str): ユーザーID
		"""
		user_info = self.fetch_user_info(user_id)

		# 画像の保存先を作っておく(作家さんの名前)
		save_dir_base = self.make_image_save_dir(user_info)

		# 全作品をループしてダウンロード
		json_result = self.api.users_works(int(user_id), per_page=300)
		time.sleep(2) # !!!XXX: APIの呼び出し後はsleep必須!!!
		works = json_result['response']

		tqdm_works = tqdm(works)
		try:
			for work in tqdm_works:
				self.fetch_image(work, save_dir_base)
		except FileNotFoundError:
			# ファイル名の変換に失敗した場合
			logger = logging.getLogger(__name__)
			logger.setLevel(logging.ERROR)

			log_file_handler = logging.FileHandler('log/pxv_blkdl.log')
			logger.addHandler(log_file_handler)
			log_info = {
				'error': 'FileNotFoundError',
				'work': work
			}
			logger.error(log_info)
			print('[ERR]Unexpected original filename')

	def fetch_image(self, work: dict, save_dir_base: str) -> None:
		"""画像を保存する
		"""
		author_id = work['user']['id']
		image_id = work['id']
		image_title = self.unsafe_char_filter.conv_file_name_safe(work['title'])
		image_page_count = work['page_count']

		if self.cache_manager.is_exist_saved_image_id(author_id, image_id):
			# 保存済みとしてキャッシュされている作品はスキップする
			#print(f'[INFO]Skipped(Cache) ==> user_{author_id} | {image_id}:{image_title}')
			return
		else:
			# 未キャッシュのものはキャッシュへ追加する
			self.cache_manager.save_cache(author_id, image_id)
			#print(f'[INFO]Cached ==> user_{author_id} | {image_id}:{image_title}')

		if image_page_count == 1:
			# 単一ページの作品
			image_url = work['image_urls']['large']
			self.aapi.download(image_url, path=save_dir_base)
			time.sleep(1) # !!!XXX: APIの呼び出し後はsleep必須!!!

			# 保存後にリネーム
			self.rename_image(save_dir_base, image_id, image_title, image_url, 0, True)
		else:
			# 複数ページの作品
			work_detail = self.api.works(image_id).response
			time.sleep(1) # !!!XXX: APIの呼び出し後はsleep必須!!!

			work_pages = work_detail[0]['metadata']['pages']
			save_dir = f'{save_dir_base}/{image_title}'

			page_count = 0
			for page in work_pages:
				image_url = page['image_urls']['large']
				os.makedirs(save_dir, exist_ok=True)
				self.aapi.download(image_url, path=save_dir)
				time.sleep(1) # !!!XXX: APIの呼び出し後はsleep必須!!!

				# 保存後にリネーム
				self.rename_image(save_dir, image_id, image_title, image_url, page_count)
				page_count += 1

	def make_image_save_dir(self, user_info: dict) -> str:
		"""指定したユーザーIDの画像保存用フォルダを作成する。
			Args:
				user_id (str): ユーザーID
			Returns:
				(str): 保存先の相対パス
		"""
		user_id = user_info['user']['id']
		user_name = self.unsafe_char_filter.conv_file_name_safe(user_info['user']['name'])

		# 同名ユーザーの場合にごちゃるのでIDもつけておく
		save_dir = f'images/{user_name}({user_id})'
		os.makedirs(save_dir, exist_ok=True)
		return save_dir

	def fetch_user_info(self, user_id: str):
		"""指定したユーザーIDのユーザー情報を取得する。
			Args:
				user_id (str): ユーザーID
		"""
		user_info = self.aapi.user_detail(user_id)
		time.sleep(1) # !!!XXX: APIの呼び出し後はsleep必須!!!
		return user_info

	def rename_image(self, save_dir: str, image_id: int, image_title: str, image_url: str, page_no: int, is_remove_page: bool = False):
		"""画像ファイルをリネームする
			Args:
				save_dir (str): ファイル保存先のディレクトリパス
				image_id (int): 画像ID
				image_title (str): 画像タイトル
				image_url (str): 画像URL
				page_no (int): 画像の連番
				is_remove_page (bool): 末尾のページ数を消すかどうか(デフォルトは消さない)
		"""
		# あらかじめ使用不可の文字を置換する
		image_title = self.unsafe_char_filter.conv_file_name_safe(image_title)

		# 拡張子が決まっていないのでDLしてきたファイルより取得
		ext = image_url.rsplit('.',1)[1:][0]

		image_id_str = str(image_id)
		file_name_org = f'{save_dir}/{image_id_str}_p{page_no}.{ext}'

		# 置換対象の文字列を設定
		replace_target = f'{image_id_str}'
		if is_remove_page:
			replace_target += f'_p{page_no}'

		file_name = file_name_org.replace(replace_target, image_title)
		move(file_name_org, file_name)


class CacheManager:
	"""キャッシュ管理機能
	"""

	def __init__(self):
		# self.clear_cache()
		cache = self.load_cache()
		if 'saved_image_ids' not in cache:
			# キャッシュが壊れている場合は初期化する
			self.clear_cache()

	def save_cache(self, user_id: int, image_id: int) -> None:
		"""保存した画像IDをキャッシュに保存する
			Args:
				user_id (int): 投稿者のユーザーID
				image_id (int): 画像ID
		"""
		cache = self.load_cache()
		# そのユーザーの作品を一度も保存されていない場合はキャッシュにユーザーID追加
		if not self.is_exist_saved_user_id(user_id):
			cache['saved_image_ids'][user_id] = []

		cache['saved_image_ids'][user_id].append(image_id)
		with open(f'{os.path.dirname(__file__)}/cache.pkl', 'wb') as f:
			pickle.dump(cache, f)

	def load_cache(self) -> dict:
		"""キャッシュを読み込む
		"""
		with open(f'{os.path.dirname(__file__)}/cache.pkl', 'rb') as f:
			return pickle.load(f)

	def is_exist_saved_image_id(self, user_id: int, image_id: int) -> bool:
		"""指定した画像IDが保存済みとしてキャッシュされているかを判定する
			Args:
				user_id (int): 投稿者のユーザーID
				image_id (int): 画像ID
		"""
		cache = self.load_cache()
		saved_user_ids = cache['saved_image_ids'].keys()

		if not self.is_exist_saved_user_id(user_id):
			# そのユーザーの作品を一度も保存してないならキャッシュされていない
			return False

		saved_image_ids = cache['saved_image_ids'][user_id]
		if image_id in saved_image_ids:
			return True

		return False

	def is_exist_saved_user_id(self, user_id: int):
		"""指定したユーザーIDがキャッシュされているかを判定する
			Args:
				user_id (int): ユーザーID
		"""
		cache = self.load_cache()
		saved_user_ids = cache['saved_image_ids'].keys()
		if user_id in saved_user_ids:
			return True
		
		return False

	def clear_cache(self) -> None:
		"""キャッシュを初期化する
		"""
		with open(f'{os.path.dirname(__file__)}/cache.pkl', 'wb') as f:
			cache = {}
			cache['saved_image_ids'] = {}
			pickle.dump(cache, f)


class UnsafeCharcterFilter:
	"""使用禁止文字の変換機能
	"""
	def __init__(self):
		# ファイル名に使用禁止の文字
		self.unsafe_char_map_file_name = {
			'\\':'￥',
			'/': '／',
			':': '：',
			'*': '＊',
			'?': '？',
			'<': '＜',
			'>': '＞',
			'|': '｜'
		}

	def conv_file_name_safe(self, file_name):
		"""ファイルパスに使用できない文字を変換する
			結合後のフルパスではなくファイル名のみに使用するよう注意
			Args:
				file_name (str): 変換対象の文字列
		"""
		if file_name == None or file_name == '':
			return file_name

		# 変換前：変換後のマッピング(とりあえず使用禁止文字は全角にしておけば良い感)
		conv_table = str.maketrans(self.unsafe_char_map_file_name)
		return file_name.translate(conv_table)


if __name__ == '__main__':

	parser = argparse.ArgumentParser(description='指定したIDの作家さんが投稿している作品を一括DLします。')
	parser.add_argument('user_id', help='(必須)作家さんのユーザーID')
	parser.add_argument('-r', '--refresh', action='store_true', help='(任意)キャッシュクリアします。(このツールを複数回実行しても、一度DLした画像はキャッシュクリアするまでDLされません)')
	args = parser.parse_args()

	if args.refresh:
		# キャッシュクリアの指定があった場合実行する
		cm = CacheManager()
		cm.clear_cache()
		print('[INFO]Cache cleared')

	# リフレッシュトークンを取得
	rtm = RefTokenManipulator()
	ref_token = rtm.fetch_ref_token()

	# # 画像ダウンロード実行
	idl = ImageDownloader(ref_token)
	idl.fetch_image_all_by_userid(args.user_id)