import unittest
from unittest import mock

import pytest

from ScoutSuite.providers import get_provider
from ScoutSuite.providers.aws.authentication_strategy import AWSCredentials
from ScoutSuite.providers.base.authentication_strategy import AuthenticationException
from ScoutSuite.providers.base.authentication_strategy_factory import get_authentication_strategy
from ScoutSuite.providers.aws.resources.ec2.instances import EC2Instances

class Object(object):
    pass


# Test methods for AWS Provider
class TestAWSProviderClass(unittest.TestCase):
    @mock.patch("ScoutSuite.providers.aws.authentication_strategy.boto3")
    @mock.patch("ScoutSuite.providers.aws.authentication_strategy.get_caller_identity")
    def test_authenticate(self, mock_get_caller_identity, mock_boto3):

        aws_authentication_strategy = get_authentication_strategy("aws")

        boto3_session = Object()
        boto3_session._session = Object()
        mock_boto3.Session.return_value = boto3_session

        test_cases = [
            # no params
            {
                "profile": None,
                "aws_access_key_id": None,
                "aws_secret_access_key": None,
                "aws_session_token": None,
                "call_dict": {},
            },
            # profile
            {
                "profile": "123",
                "aws_access_key_id": None,
                "aws_secret_access_key": None,
                "aws_session_token": None,
                "call_dict": {"profile_name": "123"},
            },
            # access and secret key
            {
                "profile": None,
                "aws_access_key_id": "456",
                "aws_secret_access_key": "789",
                "aws_session_token": None,
                "call_dict": {
                    "aws_access_key_id": "456",
                    "aws_secret_access_key": "789",
                },
            },
            # access, secret key and token
            {
                "profile": None,
                "aws_access_key_id": "456",
                "aws_secret_access_key": "789",
                "aws_session_token": "101112",
                "call_dict": {
                    "aws_access_key_id": "456",
                    "aws_secret_access_key": "789",
                    "aws_session_token": "101112",
                },
            },
        ]

        for test_case in test_cases:
            result = aws_authentication_strategy.authenticate(
                test_case["profile"],
                test_case["aws_access_key_id"],
                test_case["aws_secret_access_key"],
                test_case["aws_session_token"],
            )
            mock_boto3.Session.assert_called_with(**test_case["call_dict"])
            mock_get_caller_identity.assert_called_with(boto3_session)
            assert isinstance(result, AWSCredentials)
            assert result.session == boto3_session

        # exception test
        mock_boto3.Session.side_effect = Exception("an exception")
        with pytest.raises(AuthenticationException):
            result = aws_authentication_strategy.authenticate(None, None, None, None)

    # mock two separate places from which get_aws_account_id is called
    @mock.patch("ScoutSuite.providers.aws.facade.base.get_aws_account_id")
    @mock.patch("ScoutSuite.providers.aws.facade.base.get_partition_name")
    @mock.patch("ScoutSuite.providers.aws.provider.get_aws_account_id")
    @mock.patch("ScoutSuite.providers.aws.provider.get_partition_name")
    def test_get_report_name(
            self,
            mock_get_partiton_name,
            mock_get_aws_account_id,
            mock_facade_aws_account_id,
            mock_facade_aws_partition_name,
    ):
        # no account_id, no profile
        mock_get_aws_account_id.return_value = None
        mock_get_partiton_name.return_value = None
        aws_provider = get_provider(
            provider="aws", credentials=mock.MagicMock(session="123"),
        )
        assert aws_provider.get_report_name() == "aws"

        # profile and account_id
        mock_get_aws_account_id.return_value = "12345"
        aws_provider = get_provider(
            provider="aws", profile="9999", credentials=mock.MagicMock(session="123"),
        )
        assert aws_provider.get_report_name() == "aws-9999"

        # account_id
        aws_provider = get_provider(
            provider="aws", credentials=mock.MagicMock(session="123"),
        )
        assert aws_provider.get_report_name() == "aws-12345"

    def test_identify_user_data_secrets(self):

        SAMPLE_USER_DATA = """
# Various AWS Access Key exercisers
AKIASHORT # too short
AKIA0123456789ABCDEF # just right
AKIA0123456789ABCDEF0 # too long
AKIA0123456789abcdef # invalid characters
FAKIA0123456789ABCDE # wrong prefix
in middle AKIAFEDCBA9876543210 of line
line ends with AKIAFFFFFFFFFFFFFFFF

# Various AWS Secret Access Key exercisers
ThisIsTooShort
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
ThisOneIsJustALittleBitLongerThanItShouldBe
middle="0000000000/1111111111/2222222222/3333333" + "of line"
hats off to TRON: HereIsSomethingThatAppearsAtEndOfLineMCP
        """

        results = EC2Instances._identify_user_data_secrets(SAMPLE_USER_DATA)
        print(results)
        self.maxDiff = None
        assert results["AWS Access Key IDs"] == [
            "AKIA0123456789ABCDEF",
            "AKIAFEDCBA9876543210",
            "AKIAFFFFFFFFFFFFFFFF"
        ]
        assert results["AWS Secret Access Keys"] == [
            "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",
            "0000000000/1111111111/2222222222/3333333",
            "HereIsSomethingThatAppearsAtEndOfLineMCP"
        ]
