"""My USPS interface."""

import os.path
import pickle
from dateutil.parser import parse
from lxml import html
import requests
from requests.auth import AuthBase


LOGIN_FORM_XPATH = './/form[@name="loginForm"]'
PROFILE_XPATH = './/div[@class="atg_store_myProfileInfo"]'
DASHBOARD_XPATH = './/div[@id="dash-detail"]'
ERROR_XPATH = './/span[@class="error"]'

TRACKING_NUMBER_XPATH = './/h2[contains(@class, "mobile-status-")]'
STATUS_XPATH = './/span[@class="mypost-tracked-item-details-status"]'
DATE_XPATH = './/div[@class="mypost-tracked-item-details-date"]'
LOCATION_XPATH = './/span[@class="mypost-tracked-item-details-location"]'
SHIPPED_FROM_XPATH = './/div[@class="mobile-from"]/div'

MY_USPS_URL = 'https://reg.usps.com/login?app=MyUSPS'
LOGIN_URL = 'https://reg.usps.com/entreg/LoginAction'
DASHBOARD_URL = 'https://my.usps.com/mobileWeb/pages/myusps/HomeAction_input'
PROFILE_URL = 'https://store.usps.com/store/myaccount/profile.jsp'

COOKIE_PATH = './usps_cookies.pickle'
ATTRIBUTION = 'Information provided by www.usps.com'
USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) ' \
             'Chrome/41.0.2228.0 Safari/537.36'


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


def _get_elem(response, xpath):
    """Get element from a response."""
    tree = html.fromstring(response.text)
    elems = tree.xpath(xpath)
    if len(elems) > 0:
        return elems[0]

def _require_elem(response, xpath):
    """Require that an element exist."""
    login_form = _get_elem(response, LOGIN_FORM_XPATH)
    if login_form is not None:
        raise USPSError('Not logged in')
    elem = _get_elem(response, xpath)
    if elem is None:
        raise ValueError('No element found')
    return elem


def _get_token(session):
    """Get login token."""
    form = _get_elem(session.get(MY_USPS_URL), LOGIN_FORM_XPATH)
    inputs = form.xpath('.//input')
    for element in inputs:
        if 'name' in element.attrib and element.attrib['name'] == 'token':
            return element.attrib['value']
    raise USPSError('No login token found')


def _login(session):
    """Login."""
    token = _get_token(session)
    error = _get_elem(session.post(LOGIN_URL, {
        'userName': session.auth.username,
        'password': session.auth.password,
        'token': token,
        'struts.token.name': 'token'
    }), ERROR_XPATH)
    if error is not None:
        raise USPSError(error.text.strip())
    _save_cookies(session.cookies, session.auth.cookie_path)


def authenticated(function):
    """Re-authenticate if session expired."""
    def wrapped(*args):
        """Wrap function."""
        try:
            return function(*args)
        except USPSError:
            _login(*args)
            return function(*args)
    return wrapped


@authenticated
def get_profile(session):
    """Get profile data."""
    profile = _require_elem(session.get(PROFILE_URL), PROFILE_XPATH)
    data = {}
    for row in profile.xpath('.//tr'):
        data[row[0].text.strip().lower().replace(' ', '_')] = row[1].text.strip()
    return data

@authenticated
def get_packages(session):
    """Get package data."""
    packages = []
    dashboard = _require_elem(session.get(DASHBOARD_URL), DASHBOARD_XPATH)
    for row in dashboard.xpath('ul/li'):
        status = row.xpath(STATUS_XPATH)[0].text.strip().split(',')
        origin = row.xpath(SHIPPED_FROM_XPATH)[1].text
        packages.append({
            'tracking_number': row.xpath(TRACKING_NUMBER_XPATH)[0].text.strip(),
            'primary_status': status[0].strip(),
            'secondary_status': status[1].strip() if len(status) == 2 else '',
            'date': str(parse(' '.join(row.xpath(DATE_XPATH)[0].text.split()))),
            'location': ' '.join(row.xpath(LOCATION_XPATH)[0].text.split()).replace(' ,', ','),
            'shipped_from': origin.strip() if origin != None else ''
        })
    return packages


def get_session(username, password, cookie_path=COOKIE_PATH):
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

    session = requests.session()
    session.auth = USPSAuth(username, password, cookie_path)
    session.headers.update({'User-Agent': USER_AGENT})
    if os.path.exists(cookie_path):
        session.cookies = _load_cookies(cookie_path)
    return session
