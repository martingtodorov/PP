"""The customer must get the courier's own waybill and the courier's tracking page.

NextLevel's internal `awb` is not a tracking number: it starts with 1, no courier site finds it,
and BoxNow parcel ids never start with 1 at all.
"""
import nextlevel


def test_the_internal_nextlevel_awb_is_never_shown():
    shipment = {"awb": "1234567", "courier": "Econt", "courier_awb": "1234567"}
    out = nextlevel.customer_tracking(shipment)
    assert out["tracking_number"] == "" and out["tracking_url"] == "" and out["ready"] is False


def test_a_boxnow_number_starting_with_one_is_refused():
    assert nextlevel.is_courier_number("BoxNow", "1050123456", "9999") is False
    assert nextlevel.is_courier_number("BoxNow", "3050123456", "9999") is True


def test_the_courier_number_builds_the_courier_link():
    out = nextlevel.customer_tracking({"awb": "1000001", "courier": "Econt",
                                       "courier_awb": "1051234567"})
    assert out["tracking_number"] == "1051234567"
    assert out["tracking_url"] == "https://www.econt.com/services/track-shipment/1051234567"
    assert out["carrier"] == "Econt" and out["ready"] is True


def test_boxnow_gets_its_own_tracking_page():
    out = nextlevel.customer_tracking({"awb": "1000002", "courier": "BoxNow",
                                       "courier_awb": "3050123456"})
    assert out["tracking_url"] == "https://boxnow.bg/tracking?parcelId=3050123456"
    assert out["ready"] is True


def test_no_number_yet_means_an_empty_tracking_block():
    out = nextlevel.customer_tracking({"awb": "1000003", "courier": "Speedy", "courier_awb": None})
    assert out == {"tracking_number": "", "tracking_url": "", "carrier": "Speedy", "ready": False}


def test_the_shipment_email_shows_the_courier_number():
    import email_templates as et

    order = {"order_number": "PP1001", "customer_name": "Иван", "locale": "bg",
             "currency": "EUR", "total_eur": 100, "payment_method": "bank_transfer", "id": "abc",
             "shipment": {"awb": "1000004", "courier": "Econt", "courier_awb": "1051234567",
                          "tracking_link": "https://www.econt.com/services/track-shipment/1051234567"}}
    _, html = et.render_shipment(order, "bg", "info@purepeptide.bg")
    assert "1051234567" in html
    assert "1000004" not in html                      # the internal id stays in the admin
    assert "econt.com/services/track-shipment/1051234567" in html
