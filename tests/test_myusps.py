import datetime
import tempfile
import unittest
from bs4 import BeautifulSoup
import requests_mock
import myusps

PACKAGE_ROW_HTML = """<div class="pack_row">
                        <div class="pack_status-bigNumber">
                        <div class="date-small pack_green">Sep</div>
                    <div class="date-num-large pack_green">7</div>
                        <img src="/box/CP_images/Delivered.png" width="80px" height="80px" alt="image of delivery status" class="newDonut" width="80px" height="80px" /></div>
                        <div class="pack_status">
                        <div id="coltextR" class="pack_coltext"><span class="pack_green">Delivered</span></div></div>
                        <div class="pack_details"><div id="coltextR2" class="pack_coltext">
                        <span style="font-weight:bold;text-transform:none;"></span><br><span class="pack_green">from</span><div class="pack_h4">12345</div></div></div>
                        <div class="pack_lastscan"><div id="coltextR3" class="pack_coltext"><div class="pack_h3 pack_green">primary</div>secondary<div>Sep 07, 2017 at 07:14 PM</div></div></div>
                        <div class="pack_carat-left"><a href="/box/pages/secure/packageDashboardAction?selectedTrckNum=12345" tabindex="12"></a></div>
                </div>
        <div style="clear: both;"></div>"""


MAILPIECE_ROW_HTML = """<div class="mailpiece" style="display:block">
                 <img class="mailpieceIMG" alt="Scanned image of your mail piece" src="getMailpieceImageFile.action?id=12345" />
                <div class="mailDetail" style="display:block">
                  <a href='/box/pages/secure/mailDetailAction?selectedDate=09/22/2017&deliveryDayType=Today&selectedMailpieceId=12345'
                  class="mailDetailLink" title="Click for more detail of mailpiece" tabindex="8">
                     <img src="/box/CP_images/DropDownCarat.svg" class="mailDetailIcon" alt="image of expanding icon" />
                  </a>
                </div>
                </div>"""


class TestMyUSPSCookies(unittest.TestCase):

    def test_cookies(self):
        data = {'test': 'ok'}
        with tempfile.NamedTemporaryFile() as temp_file:
            myusps._save_cookies(data, temp_file.name)
            self.assertEqual(myusps._load_cookies(temp_file.name), data)


class TestMyUSPSPackages(unittest.TestCase):

    row = BeautifulSoup(PACKAGE_ROW_HTML, myusps.HTML_PARSER)

    def test_get_primary_status(self):
        self.assertEqual(myusps._get_primary_status(TestMyUSPSPackages.row), 'primary')

    def test_get_secondary_status(self):
        self.assertEqual(myusps._get_secondary_status(TestMyUSPSPackages.row), 'secondary')

    def test_get_tracking_number(self):
        self.assertEqual(myusps._get_tracking_number(TestMyUSPSPackages.row), '12345')

    def test_get_shipped_from(self):
        self.assertEqual(myusps._get_shipped_from(TestMyUSPSPackages.row), 'from')

    def test_get_status_timestamp(self):
        self.assertEqual(myusps._get_status_timestamp(TestMyUSPSPackages.row), datetime.datetime(2017, 9, 7, 19, 14, 0))


    def test_get_delivery_date(self):
        self.assertEqual(myusps._get_delivery_date(TestMyUSPSPackages.row), datetime.datetime(2017, 9, 7).date())


class TestMyUSPSMailpieces(unittest.TestCase):

    row = BeautifulSoup(MAILPIECE_ROW_HTML, myusps.HTML_PARSER)

    def test_get_mailpiece_image(self):
        self.assertEqual(myusps._get_mailpiece_image(TestMyUSPSMailpieces.row), 'getMailpieceImageFile.action?id=12345')

    def test_get_mailpiece_id(self):
        self.assertEqual(myusps._get_mailpiece_id('getMailpieceImageFile.action?id=12345'), '12345')

    def test_get_mailpiece_url(self):
        self.assertEqual(myusps._get_mailpiece_url('getMailpieceImageFile.action?id=12345'), 'https://informeddelivery.usps.com/box/pages/secure/getMailpieceImageFile.action?id=12345')
