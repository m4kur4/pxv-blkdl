import time
import json
import re
import requests

from argparse import ArgumentParser
from base64 import urlsafe_b64encode
from hashlib import sha256
from pprint import pprint
from secrets import token_urlsafe
from sys import exit
from urllib.parse import urlencode
from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

USER_AGENT = "PixivAndroidApp/5.0.234 (Android 11; Pixel 5)"
REDIRECT_URI = "https://app-api.pixiv.net/web/v1/users/auth/pixiv/callback"
LOGIN_URL = "https://app-api.pixiv.net/web/v1/login"
AUTH_TOKEN_URL = "https://oauth.secure.pixiv.net/auth/token"
CLIENT_ID = "MOBrBDS8blbauoSck0ZfDbtuzpyT"
CLIENT_SECRET = "lsACyCD94FhDUtGTXi3QzcFE2uU1hqtDaKeqrdwj"

def s256(data):
    """S256 transformation method."""

    return urlsafe_b64encode(sha256(data).digest()).rstrip(b"=").decode("ascii")