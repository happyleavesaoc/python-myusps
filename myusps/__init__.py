"""My USPS interface."""

import datetime
import logging
import os.path
import pickle
import re
from bs4 import BeautifulSoup
from dateutil.parser import parse
import requests
from requests.auth import AuthBase
import requests_cache


_LOGGER = logging.getLogger(__name__)
HTML_PARSER = 'html.parser'
BASE_URL = 'https://reg.usps.com'
MY_USPS_URL = BASE_URL + '/login?app=MyUSPS'
AUTHENTICATE_URL = BASE_URL + '/entreg/json/AuthenticateAction'
LOGIN_URL = BASE_URL + '/entreg/LoginAction'
DASHBOARD_URL = 'https://informeddelivery.usps.com/box/pages/secure/DashboardAction_input.action'
INFORMED_DELIVERY_IMAGE_URL = 'https://informeddelivery.usps.com/box/pages/secure/'
PROFILE_URL = 'https://store.usps.com/store/myaccount/profile.jsp'
COOKIE_PATH = './usps_cookies.pickle'
CACHE_NAME = 'usps_cache'
ATTRIBUTION = 'Information provided by www.usps.com'
USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) ' \
             'Chrome/41.0.2228.0 Safari/537.36'
EFMJ_HEADER = 'x-efmj'
UUID_TOKEN_REGEX = re.compile(r'"uniqueStateKey",100,"(.+?)"', re.MULTILINE)
PAYLOAD_KEY_REGEX = re.compile(r'httpMethods:\["POST"\]\}\],"(.+?)"', re.MULTILINE)



class USPSError(Exception):
    """USPS error."""

    pass


def _save_cookies(requests_cookiejar, filename):
    """Save cookies to a file."""
    with open(filename, 'wb') as handle:
        pickle.dump(requests_cookiejar, handle)


def _load_cookies(filename):
    """Load cookies from a file."""
    with open(filename, 'rb') as handle:
        return pickle.load(handle)


def _get_primary_status(row):
    """Get package primary status."""
    try:
        return row.find('div', {'class': 'pack_h3'}).string
    except AttributeError:
        return


def _get_secondary_status(row):
    """Get package secondary status."""
    try:
        return row.find('div', {'id': 'coltextR3'}).contents[1]
    except (AttributeError, IndexError):
        return


def _get_shipped_from(row):
    """Get where package was shipped from."""
    try:
        spans = row.find('div', {'id': 'coltextR2'}).find_all('span')
        if len(spans) < 2:
            return
        return spans[1].string
    except AttributeError:
        return


def _get_status_timestamp(row):
    """Get latest package timestamp."""
    try:
        divs = row.find('div', {'id': 'coltextR3'}).find_all('div')
        if len(divs) < 2:
            return
        timestamp_string = divs[1].string
    except AttributeError:
        return
    try:
        return parse(timestamp_string)
    except ValueError:
        return


def _get_delivery_date(row):
    """Get delivery date (estimated or actual)."""
    try:
        month = row.find('div', {'class': 'date-small'}).string
        day = row.find('div', {'class': 'date-num-large'}).string
    except AttributeError:
        return
    try:
        return parse('{} {}'.format(month, day)).date()
    except ValueError:
        return


def _get_tracking_number(row):
    """Get package tracking number."""
    try:
        return row.find('div', {'class': 'pack_h4'}).string
    except AttributeError:
        return


def _get_mailpiece_image(row):
    """Get mailpiece image url."""
    try:
        return row.find('img', {'class': 'mailpieceIMG'}).get('src')
    except AttributeError:
        return


def _get_mailpiece_id(image):
    parts = image.split('=')
    if len(parts) != 2:
        return
    return parts[1]


def _get_mailpiece_url(image):
    """Get mailpiece url."""
    return '{}{}'.format(INFORMED_DELIVERY_IMAGE_URL, image)


def _get_login_metadata(session):
    """Get login metadata."""
    resp = session.get(MY_USPS_URL)
    # Token for login form submission
    parsed = BeautifulSoup(resp.text, HTML_PARSER)
    form = parsed.find('form', {'name': 'loginForm'})
    token_elem = form.find('input', {'name': 'token'})
    # UUID token and payload key for GTM compatibility
    uuid_token_result = UUID_TOKEN_REGEX.search(resp.text)
    payload_key_result = PAYLOAD_KEY_REGEX.search(resp.text)
    if token_elem and uuid_token_result and payload_key_result:
        _LOGGER.debug('login form token: %s', token_elem.get('value'))
        _LOGGER.debug('gtm uuid token: %s', uuid_token_result.group(1))
        _LOGGER.debug('gtm payload key: %s', payload_key_result.group(1))
        return token_elem.get('value'), uuid_token_result.group(1), payload_key_result.group(1)
    raise USPSError('No login metadata found')


def _login(session):
    """Login."""
    _LOGGER.debug("attempting login")
    session.cookies.clear()
    session.remove_expired_responses()
    token, uuid_token, payload_key = _get_login_metadata(session)
    resp = session.post(AUTHENTICATE_URL, {
        'username':  session.auth.username,
        'password': session.auth.password
    }, headers={
        EFMJ_HEADER+'uniqueStateKey': uuid_token,
        EFMJ_HEADER+payload_key: ''
    })
    data = resp.json()
    if 'rs' not in data:
        raise USPSError('authentication failed')
    if data['rs'] != 'success':
        raise USPSError('authentication failed')
    resp = session.post(LOGIN_URL, {
        'username': session.auth.username,
        'password': session.auth.password,
        'token': token,
        'struts.token.name': 'token'
    }, allow_redirects=False)
    parsed = BeautifulSoup(resp.text, HTML_PARSER)
    error = parsed.find('span', {'class': 'error'})
    if error is not None:
        raise USPSError(error.text.strip())
    _save_cookies(session.cookies, session.auth.cookie_path)


def _get_dashboard(session, date=None):
    # Default to today's date
    if not date:
        date = datetime.datetime.now().date()
    response = session.get(DASHBOARD_URL, params={
        'selectedDate': '{0:%m}/{0:%d}/{0:%Y}'.format(date)
    }, allow_redirects=False)
    # If we get a HTTP redirect, the session has expired and
    # we need to login again (handled by @authenticated)
    if response.status_code == 302:
        raise USPSError('expired session')
    return response


def authenticated(function):
    """Re-authenticate if session expired."""
    def wrapped(*args):
        """Wrap function."""
        try:
            return function(*args)
        except USPSError:
            _LOGGER.info("attempted to access page before login")
            _login(args[0])
            return function(*args)
    return wrapped


@authenticated
def get_profile(session):
    """Get profile data."""
    response = session.get(PROFILE_URL, allow_redirects=False)
    if response.status_code == 302:
        raise USPSError('expired session')
    parsed = BeautifulSoup(response.text, HTML_PARSER)
    profile = parsed.find('div', {'class': 'atg_store_myProfileInfo'})
    data = {}
    for row in profile.find_all('tr'):
        cells = row.find_all('td')
        if len(cells) == 2:
            key = ' '.join(cells[0].find_all(text=True)).strip().lower().replace(' ', '_')
            value = ' '.join(cells[1].find_all(text=True)).strip()
            data[key] = value
    return data


@authenticated
def get_packages(session):
    """Get package data."""
    _LOGGER.info("attempting to get package data")
    response = _get_dashboard(session)
    parsed = BeautifulSoup(response.text, HTML_PARSER)
    packages = []
    for row in parsed.find_all('div', {'class': 'pack_row'}):
        packages.append({
            'tracking_number': _get_tracking_number(row),
            'primary_status': _get_primary_status(row),
            'secondary_status': _get_secondary_status(row),
            'status_timestamp': _get_status_timestamp(row),
            'shipped_from': _get_shipped_from(row),
            'delivery_date': _get_delivery_date(row)
        })
    return packages


@authenticated
def get_mail(session, date=None):
    """Get mail data."""
    _LOGGER.info("attempting to get mail data")
    if not date:
        date = datetime.datetime.now().date()
    response = _get_dashboard(session, date)
    parsed = BeautifulSoup(response.text, HTML_PARSER)
    mail = []
    for row in parsed.find_all('div', {'class': 'mailpiece'}):
        image = _get_mailpiece_image(row)
        if not image:
            continue
        mail.append({
            'id': _get_mailpiece_id(image),
            'image': _get_mailpiece_url(image),
            'date': date
        })
    return mail


def get_session(username, password, cookie_path=COOKIE_PATH, cache=True, cache_expiry=300):
    """Get session, existing or new."""
    class USPSAuth(AuthBase):  # pylint: disable=too-few-public-methods
        """USPS authorization storage."""

        def __init__(self, username, password, cookie_path):
            """Init."""
            self.username = username
            self.password = password
            self.cookie_path = cookie_path

        def __call__(self, r):
            """Call is no-op."""
            return r

    session = requests.Session()
    if cache:
        session = requests_cache.core.CachedSession(cache_name=CACHE_NAME,
                                                    expire_after=cache_expiry)
    session.auth = USPSAuth(username, password, cookie_path)
    session.headers.update({'User-Agent': USER_AGENT})
    if os.path.exists(cookie_path):
        _LOGGER.debug("cookie found at: %s", cookie_path)
        session.cookies = _load_cookies(cookie_path)
    else:
        _login(session)
    return session
