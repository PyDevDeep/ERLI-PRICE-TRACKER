"""
Tests for src/exceptions.py — custom exception hierarchy.

Coverage targets:
- BaseAppError: message attribute, str representation
- SerperAPIError: fields (url, status_code), message format, None status_code
- ParserError: fields (url, raw_data), message format
- DatabaseError: fields (operation, details), message format
"""

import pytest

from src.exceptions import BaseAppError, DatabaseError, ParserError, SerperAPIError


class TestBaseAppError:
    @pytest.mark.unit
    def test_message_attribute_set(self) -> None:
        err = BaseAppError("something went wrong")
        assert err.message == "something went wrong"

    @pytest.mark.unit
    def test_is_exception_subclass(self) -> None:
        assert issubclass(BaseAppError, Exception)

    @pytest.mark.unit
    def test_str_representation(self) -> None:
        err = BaseAppError("boom")
        assert "boom" in str(err)


class TestSerperAPIError:
    @pytest.mark.unit
    def test_stores_url(self) -> None:
        err = SerperAPIError(url="https://erli.pl/p", status_code=404, message="not found")
        assert err.url == "https://erli.pl/p"

    @pytest.mark.unit
    def test_stores_status_code(self) -> None:
        err = SerperAPIError(url="https://erli.pl/p", status_code=401, message="unauthorized")
        assert err.status_code == 401

    @pytest.mark.unit
    def test_none_status_code_allowed(self) -> None:
        err = SerperAPIError(url="https://erli.pl/p", status_code=None, message="timeout")
        assert err.status_code is None

    @pytest.mark.unit
    def test_message_contains_status_code(self) -> None:
        err = SerperAPIError(url="https://erli.pl/p", status_code=403, message="forbidden")
        assert "403" in err.message

    @pytest.mark.unit
    def test_is_base_app_error_subclass(self) -> None:
        assert issubclass(SerperAPIError, BaseAppError)

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "status_code,msg",
        [
            (400, "bad request"),
            (401, "unauthorized"),
            (403, "forbidden"),
            (404, "not found"),
            (500, "server error"),
            (None, "network failure"),
        ],
    )
    def test_various_status_codes(self, status_code: int | None, msg: str) -> None:
        err = SerperAPIError(url="https://erli.pl/p", status_code=status_code, message=msg)
        assert err.url == "https://erli.pl/p"
        assert err.status_code == status_code


class TestParserError:
    @pytest.mark.unit
    def test_stores_url(self) -> None:
        err = ParserError(url="https://erli.pl/p", message="parse failed")
        assert err.url == "https://erli.pl/p"

    @pytest.mark.unit
    def test_none_url_allowed(self) -> None:
        err = ParserError(url=None, message="no url context")
        assert err.url is None

    @pytest.mark.unit
    def test_stores_raw_data(self) -> None:
        raw = {"text": "some text", "jsonld": {}}
        err = ParserError(url=None, message="err", raw_data=raw)
        assert err.raw_data == raw

    @pytest.mark.unit
    def test_raw_data_defaults_to_none(self) -> None:
        err = ParserError(url=None, message="err")
        assert err.raw_data is None

    @pytest.mark.unit
    def test_message_contains_description(self) -> None:
        err = ParserError(url=None, message="invalid json")
        assert "invalid json" in err.message

    @pytest.mark.unit
    def test_is_base_app_error_subclass(self) -> None:
        assert issubclass(ParserError, BaseAppError)


class TestDatabaseError:
    @pytest.mark.unit
    def test_stores_operation(self) -> None:
        err = DatabaseError(operation="add_product", details="constraint violation")
        assert err.operation == "add_product"

    @pytest.mark.unit
    def test_stores_details(self) -> None:
        err = DatabaseError(operation="add_product", details="unique constraint")
        assert err.details == "unique constraint"

    @pytest.mark.unit
    def test_message_contains_operation(self) -> None:
        err = DatabaseError(operation="delete_product", details="fk violation")
        assert "delete_product" in err.message

    @pytest.mark.unit
    def test_is_base_app_error_subclass(self) -> None:
        assert issubclass(DatabaseError, BaseAppError)
