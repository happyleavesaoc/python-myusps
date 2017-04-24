"""My USPS interface."""

import datetime
import os.path
import pickle
from bs4 import BeautifulSoup
from dateutil.parser import parse
import requests
from requests.auth import AuthBase


HTML_PARSER = 'html.parser'
LOGIN_FORM_TAG = 'form'
LOGIN_FORM_ATTRS = {'name': 'loginForm'}
PROFILE_TAG = 'div'
PROFILE_ATTRS = {'class': 'atg_store_myProfileInfo'}
NO_PACKAGES_TAG = 'p'
NO_PACKAGES_ATTRS = {'id': 'package-status'}
INFORMED_DELIVERY_TAG = 'div'
INFORMED_DELIVERY_ATTRS = {'id': 'realMail'}
MAIL_IMAGE_TAG = 'div'
MAIL_IMAGE_ATTRS = {'class': 'mailImageBox'}
DASHBOARD_TAG = 'div'
DASHBOARD_ATTRS = {'id': 'dash-detail'}
SHIPPED_FROM_TAG = 'div'
SHIPPED_FROM_ATTRS = {'class': 'mobile-from'}
LOCATION_TAG = 'span'
LOCATION_ATTRS = {'class': 'mypost-tracked-item-details-location'}
DATE_TAG = 'div'
DATE_ATTRS = {'class': 'mypost-tracked-item-details-date'}
STATUS_TAG = 'span'
STATUS_ATTRS = {'class': 'mypost-tracked-item-details-status'}
TRACKING_NUMBER_TAG = 'h2'
TRACKING_NUMBER_ATTRS = {'class': ['mobile-status-green', 'mobile-status-blue',
                                   'mobile-status-red']}
ERROR_TAG = 'span'
ERROR_ATTRS = {'class': 'error'}

MY_USPS_URL = 'https://reg.usps.com/login?app=MyUSPS'
AUTHENTICATE_URL = 'https://reg.usps.com/entreg/json/AuthenticateAction'
LOGIN_URL = 'https://reg.usps.com/entreg/LoginAction'
DASHBOARD_URL = 'https://my.usps.com/mobileWeb/pages/myusps/HomeAction_input'
INFORMED_DELIVERY_URL = 'https://informeddelivery.usps.com/box/pages/secure/HomeAction_input.action'
INFORMED_DELIVERY_IMAGE_URL = 'https://informeddelivery.usps.com/box/pages/secure/'
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


def _get_elem(response, tag, attr):
    """Get element from a response."""
    parsed = BeautifulSoup(response.text, HTML_PARSER)
    return parsed.find(tag, attr)


def _require_elem(response, tag, attrs):
    """Require that an element exist."""
    login_form = _get_elem(response, LOGIN_FORM_TAG, LOGIN_FORM_ATTRS)
    if login_form is not None:
        raise USPSError('Not logged in')
    elem = _get_elem(response, tag, attrs)
    if elem is None:
        raise ValueError('No element found')
    return elem


def _get_location(row):
    """Get package location."""
    return ' '.join(list(row.find(LOCATION_TAG, LOCATION_ATTRS).strings)[0]
                    .split()).replace(' ,', ',')


def _get_status(row):
    """Get package status."""
    return row.find(STATUS_TAG, STATUS_ATTRS).string.strip().split(',')


def _get_shipped_from(row):
    """Get where package was shipped from."""
    shipped_from_elems = row.find(SHIPPED_FROM_TAG, SHIPPED_FROM_ATTRS).find_all('div')
    if len(shipped_from_elems) > 1 and shipped_from_elems[1].string:
        return shipped_from_elems[1].string.strip()
    return ''


def _get_date(row):
    """Get latest package date."""
    date_string = ' '.join(row.find(DATE_TAG, DATE_ATTRS).string.split())
    try:
        return str(parse(date_string))
    except ValueError:
        return None


def _get_tracking_number(row):
    """Get package tracking number."""
    return row.find(TRACKING_NUMBER_TAG, TRACKING_NUMBER_ATTRS).string.strip()


def _get_token(session):
    """Get login token."""
    form = _get_elem(session.get(MY_USPS_URL), LOGIN_FORM_TAG, LOGIN_FORM_ATTRS)
    token_elem = form.find('input', {'name': 'token'})
    if token_elem:
        return token_elem.get('value')
    raise USPSError('No login token found')


def _login(session):
    """Login."""
    token = _get_token(session)
    resp = session.post(AUTHENTICATE_URL, {
        'username':  session.auth.username,
        'password': session.auth.password
    })
    if resp.json()['rs'] != 'success':
        raise USPSError('authentication failed')
    error = _get_elem(session.post(LOGIN_URL, {
        'username': session.auth.username,
        'password': session.auth.password,
        'token': token,
        'struts.token.name': 'token'
    }), ERROR_TAG, ERROR_ATTRS)
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
            _login(args[0])
            return function(*args)
    return wrapped


@authenticated
def get_profile(session):
    """Get profile data."""
    profile = _require_elem(session.get(PROFILE_URL), PROFILE_TAG, PROFILE_ATTRS)
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
    packages = []
    response = session.get(DASHBOARD_URL)
    no_packages = _get_elem(response, NO_PACKAGES_TAG, NO_PACKAGES_ATTRS)
    if no_packages is not None:
        return packages
    dashboard = _require_elem(response, DASHBOARD_TAG, DASHBOARD_ATTRS)
    for row in dashboard.find('ul').find_all('li', recursive=False):
        status = _get_status(row)
        packages.append({
            'tracking_number': _get_tracking_number(row),
            'primary_status': status[0].strip(),
            'secondary_status': status[1].strip() if len(status) == 2 else '',
            'date': _get_date(row),
            'location': _get_location(row),
            'shipped_from': _get_shipped_from(row)
        })
    return packages


@authenticated
def get_mail(session, date=datetime.datetime.now().date()):
    """Get mail data."""
    mail = []
    response = session.post(INFORMED_DELIVERY_URL, {
        'selectedDate': '{0:%m}/{0:%d}/{0:%Y}'.format(date)
    })
    container = _require_elem(response, INFORMED_DELIVERY_TAG, INFORMED_DELIVERY_ATTRS)
    for row in container.find_all(MAIL_IMAGE_TAG, MAIL_IMAGE_ATTRS):
        img = row.find('img').get('src')
        mail.append({
            'id': img.split('=')[1],
            'date': str(date),
            'image': '{}{}'.format(INFORMED_DELIVERY_IMAGE_URL, img)
        })
    return mail


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
    else:
        _login(session)
    return session
