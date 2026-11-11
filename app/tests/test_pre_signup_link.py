"""Tests for the Cognito Pre sign-up trigger that links Google sign-ins to the
invited (native) user. The handler lives with the infra code; load it by path."""

import importlib.util
from pathlib import Path

import pytest

HANDLER = (
    Path(__file__).resolve().parents[2]
    / "infra/terraform/modules/identity/lambda/pre_signup/handler.py"
)


@pytest.fixture
def mod():
    spec = importlib.util.spec_from_file_location("pre_signup_handler", HANDLER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeCognito:
    def __init__(self, users=None, fail_link=False):
        self.users = users or []
        self.fail_link = fail_link
        self.list_calls = []
        self.links = []

    def list_users(self, **kwargs):
        self.list_calls.append(kwargs)
        return {"Users": self.users}

    def admin_link_provider_for_user(self, **kwargs):
        if self.fail_link:
            raise RuntimeError("boom")
        self.links.append(kwargs)


def native(username="uuid-1", email="lizi@tensorbay.io", status="FORCE_CHANGE_PASSWORD"):
    return {
        "Username": username,
        "UserStatus": status,
        "Attributes": [{"Name": "email", "Value": email}],
    }


def event(user_name="Google_116192", email="Lizi@Tensorbay.io", verified="true",
          source="PreSignUp_ExternalProvider"):
    return {
        "triggerSource": source,
        "userPoolId": "pool-1",
        "userName": user_name,
        "request": {"userAttributes": {"email": email, "email_verified": verified}},
        "response": {},
    }


def run(mod, monkeypatch, fake, ev):
    monkeypatch.setattr(mod, "_client", fake)
    out = mod.handler(ev, None)
    assert out is ev  # the event is always handed back so sign-in proceeds
    return out


def test_links_google_identity_to_invited_user(mod, monkeypatch):
    fake = FakeCognito([native()])
    run(mod, monkeypatch, fake, event())
    assert len(fake.links) == 1
    link = fake.links[0]
    assert link["UserPoolId"] == "pool-1"
    assert link["DestinationUser"] == {"ProviderName": "Cognito", "ProviderAttributeValue": "uuid-1"}
    assert link["SourceUser"] == {
        "ProviderName": "Google",
        "ProviderAttributeName": "Cognito_Subject",
        "ProviderAttributeValue": "116192",  # the Google subject, prefix stripped
    }
    # Email is matched lower-cased and exactly.
    assert fake.list_calls[0]["Filter"] == 'email = "lizi@tensorbay.io"'


def test_ignores_non_external_provider_triggers(mod, monkeypatch):
    fake = FakeCognito([native()])
    run(mod, monkeypatch, fake, event(source="PreSignUp_AdminCreateUser"))
    run(mod, monkeypatch, fake, event(source="PreSignUp_SignUp"))
    assert fake.links == [] and fake.list_calls == []


def test_ignores_other_providers(mod, monkeypatch):
    fake = FakeCognito([native()])
    run(mod, monkeypatch, fake, event(user_name="Facebook_123"))
    assert fake.links == [] and fake.list_calls == []


@pytest.mark.parametrize("verified", ["false", "", None, "False"])
def test_never_links_unverified_email(mod, monkeypatch, verified):
    fake = FakeCognito([native()])
    run(mod, monkeypatch, fake, event(verified=verified))
    assert fake.links == [] and fake.list_calls == []


def test_no_invited_user_means_no_link(mod, monkeypatch):
    fake = FakeCognito([])
    run(mod, monkeypatch, fake, event())
    assert fake.links == []


def test_never_links_to_another_federated_user(mod, monkeypatch):
    fake = FakeCognito([native(username="Google_999", status="EXTERNAL_PROVIDER")])
    run(mod, monkeypatch, fake, event())
    assert fake.links == []


def test_ambiguous_match_is_not_linked(mod, monkeypatch):
    fake = FakeCognito([native("a"), native("b")])
    run(mod, monkeypatch, fake, event())
    assert fake.links == []


def test_filter_result_is_rechecked(mod, monkeypatch):
    # If the service ever returned a different email, don't trust it.
    fake = FakeCognito([native(email="someone.else@tensorbay.io")])
    run(mod, monkeypatch, fake, event())
    assert fake.links == []


@pytest.mark.parametrize("email", ['a"b@x.io', "a\\b@x.io"])
def test_rejects_filter_unsafe_emails(mod, monkeypatch, email):
    fake = FakeCognito([native()])
    run(mod, monkeypatch, fake, event(email=email))
    assert fake.list_calls == [] and fake.links == []


def test_link_failure_does_not_block_sign_in(mod, monkeypatch):
    fake = FakeCognito([native()], fail_link=True)
    run(mod, monkeypatch, fake, event())  # must not raise


def test_lookup_failure_does_not_block_sign_in(mod, monkeypatch):
    class Broken(FakeCognito):
        def list_users(self, **kwargs):
            raise RuntimeError("throttled")

    run(mod, monkeypatch, Broken(), event())  # must not raise
