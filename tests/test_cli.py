import pytest
from botocore.exceptions import ClientError

from seller_support.__main__ import main


def test_cli_lists_cases_without_credentials(monkeypatch, capsys):
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.setattr("sys.argv", ["seller-support", "--list-cases"])
    assert main() == 0
    assert "CASE-001: SG-1042" in capsys.readouterr().out


@pytest.mark.parametrize(
    "code",
    [
        "ThrottlingException",
        "AccessDeniedException",
        "ExpiredTokenException",
        "ValidationException",
    ],
)
def test_provider_error_exposes_diagnostic_not_full_response(monkeypatch, capsys, code):
    def fail(definitions):
        raise ClientError(
            {
                "Error": {"Code": code, "Message": "Provider diagnostic."},
                "ResponseMetadata": {"internal": "do-not-dump"},
            },
            "Converse",
        )

    monkeypatch.setattr("seller_support.__main__.create_models", fail)
    monkeypatch.setattr("sys.argv", ["seller-support", "--case", "CASE-001", "--trace"])
    assert main() == 1
    output = capsys.readouterr()
    assert not output.out
    assert f"Bedrock {code}: Provider diagnostic." in output.err
    assert "do-not-dump" not in output.err


def test_programming_errors_keep_their_traceback(monkeypatch):
    def fail(definitions):
        raise AttributeError("broken constructor")

    monkeypatch.setattr("seller_support.__main__.create_models", fail)
    monkeypatch.setattr("sys.argv", ["seller-support", "--case", "CASE-001"])
    with pytest.raises(AttributeError, match="broken constructor"):
        main()
