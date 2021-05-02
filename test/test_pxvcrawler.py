import json
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from pxvcrawler import RefTokenManipulator

class TestRefTokenManipulatorMethods(unittest.TestCase):
	"""テストの実行には同じディレクトリへ setting.json を配置する必要があります。"""

	def test_fetch_ref_token(self):
		rtm = RefTokenManipulator()
		rtm.fetch_ref_token()

	def test_login(self):
		rtm = RefTokenManipulator()
		rtm.login()

	def test_transform_sha256(self):
		rtm = RefTokenManipulator()
		# NOTE: hogeだけ渡すとエラー
		# Unicode-objects must be encoded before hashing
		rtm.transform_sha256('hoge'.encode('ascii')) 

	def test_oauth_pkce(self):
		rtm = RefTokenManipulator()
		rtm.oauth_pkce(rtm.transform_sha256)


if __name__ == '__main__':
  unittest.main()