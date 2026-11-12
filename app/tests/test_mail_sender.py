from neocloud.core.config import Settings
from neocloud.core.mail import ses_source


def _s(**kw) -> Settings:
    return Settings(**kw)


def test_sender_has_display_name() -> None:
    assert ses_source(_s(ses_from_email="crm@tensorbay.io")) == "TensorBay <crm@tensorbay.io>"


def test_sender_without_name_or_address() -> None:
    assert ses_source(_s(ses_from_email="crm@tensorbay.io", ses_from_name="")) == "crm@tensorbay.io"
    assert ses_source(_s(ses_from_email=None)) is None
    assert ses_source(_s(ses_from_email="  ")) is None


def test_display_name_cannot_inject_headers_and_is_encoded() -> None:
    out = ses_source(_s(ses_from_email="crm@tensorbay.io", ses_from_name="Evil\r\nBcc: x@y.com"))
    assert "\r" not in out and "\n" not in out
    assert out.endswith("<crm@tensorbay.io>")
    assert "=?utf-8?" in ses_source(_s(ses_from_email="crm@tensorbay.io", ses_from_name="Tensor Báy"))
