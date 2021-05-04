import json
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from pxv_blkdl import RefTokenManipulator, UnsafeCharcterFilter

class TestRefTokenManipulatorMethods(unittest.TestCase):

	def test_fetch_ref_token(self):
		rtm = RefTokenManipulator()
		rtm.fetch_ref_token()

	# 設定ファイル読み込むのが面倒なので一旦コメントアウト
	# def test_login(self):
	# 	rtm = RefTokenManipulator()
	# 	rtm.login()

	def test_transform_sha256(self):
		rtm = RefTokenManipulator()
		# NOTE: hogeだけ渡すとエラー
		# Unicode-objects must be encoded before hashing
		rtm.transform_sha256('hoge'.encode('ascii')) 

	def test_oauth_pkce(self):
		rtm = RefTokenManipulator()
		rtm.oauth_pkce(rtm.transform_sha256)

class TestUnsafeCharcterFilterMethods(unittest.TestCase):

	def test_conv_file_name_safe(self):
		ucf = UnsafeCharcterFilter()

		expected = '￥／：＊？＜＞｜’”'
		actual = ucf.conv_file_name_safe('\\/:*?<>|\'\"')
		self.assertEqual(expected, actual)

if __name__ == '__main__':
  unittest.main()