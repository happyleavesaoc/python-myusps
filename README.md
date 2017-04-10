[![PyPI version](https://badge.fury.io/py/myusps.svg)](https://badge.fury.io/py/myusps)

# python-myusps

Python 3 API for [My USPS](https://my.usps.com/mobileWeb/pages/intro/start.action), a way to track packages.

## Prerequisites

Sign up for My USPS and verify your address.

## Install

`pip install myusps`

## Usage

```python
import myusps

# Establish a session.
# Use the login credentials you use to login to My USPS via the web.
# A login failure raises a `USPSError`.
session = myusps.get_session("username", "password")

# Get your profile information as a dict. Includes name, address, phone, etc.
profile = myusps.get_profile(session)

# Get all packages that My UPS knows about.
packages = myusps.get_packages(session)
```

## Caching
Session cookies are cached by default in `./usps_cookies.pickle` and will be used if available instead of logging in. If the cookies expire, a new session will be established automatically.

## Development

### Lint

`tox`

### Release

`make release`

### Contributions

Contributions are welcome. Please submit a PR that passes `tox`.

## Disclaimer
Not affiliated with USPS. Does not use [USPS Web Tools API](https://www.usps.com/business/web-tools-apis/welcome.htm). Use at your own risk.
