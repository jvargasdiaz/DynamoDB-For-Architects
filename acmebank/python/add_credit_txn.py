
# Load the AWS SDK for Python
import boto3
from botocore.exceptions import ClientError

TABLE_NAME="acme-bank-v11"

# Get information for the account
# For further processing we need (LAST_ACCT_TXN_NUMBER, ACCT_BALANCE)
CUST_NUMBER="CUST#102"
ACCT_NUMBER="ACCT#510"

# Change these to add transaction with 
TXN_AMOUNT="50"
TXN_DATE="2023/01/01"
TXN_TYPE="atm"

ERROR_HELP_STRINGS = {
    # Operation specific errors
    'TransactionCanceledException': 'Transaction Cancelled, implies a client issue, fix before retrying',
    'TransactionInProgressException': 'The transaction with the given request token is already in progress, consider changing retry strategy for this type of error',
    'IdempotentParameterMismatchException': 'Request rejected because it was retried with a different payload but with a request token that was already used,' +
                                            'change request token for this payload to be accepted',
    # Common Errors
    'InternalServerError': 'Internal Server Error, generally safe to retry with exponential back-off',
    'ProvisionedThroughputExceededException': 'Request rate is too high. If you\'re using a custom retry strategy make sure to retry with exponential back-off.' +
                                              'Otherwise consider reducing frequency of requests or increasing provisioned capacity for your table or secondary index',
    'ResourceNotFoundException': 'One of the tables was not found, verify table exists before retrying',
    'ServiceUnavailable': 'Had trouble reaching DynamoDB. generally safe to retry with exponential back-off',
    'ThrottlingException': 'Request denied due to throttling, generally safe to retry with exponential back-off',
    'UnrecognizedClientException': 'The request signature is incorrect most likely due to an invalid AWS access key ID or secret key, fix before retrying',
    'ValidationException': 'The input fails to satisfy the constraints specified by DynamoDB, fix input before retrying',
    'RequestLimitExceeded': 'Throughput exceeds the current throughput limit for your account, increase account level throughput before retrying',
}

# Use the following function instead when using DynamoDB Local
def create_dynamodb_client(region="localhost"):
   return boto3.client("dynamodb", region_name="localhost", endpoint_url="http://localhost:8000", aws_access_key_id="access_key_id", aws_secret_access_key="secret_access_key")

# Use the following function instead when using DynamoDB on AWS cloud
# def create_dynamodb_client(region="us-east-1"):
#     return boto3.client("dynamodb", region_name=region)

# Create expression for the query
def create_account_query_input(cust, account):
    return {
        "TableName": TABLE_NAME,
        "KeyConditionExpression": "#PK = :cust_number And #SK = :account_number",
        "ExpressionAttributeNames": {"#PK":"PK","#SK":"SK"},
        "ExpressionAttributeValues": {":cust_number": {"S":"CUST#102"},":account_number": {"S":"ACCT#510"}}
    }

# Execute the query
def execute_account_query(dynamodb_client, input):
    try:
        response = dynamodb_client.query(**input)
        print("Account Query successful.")
        return response
        # Handle response
    except ClientError as error:
        handle_error(error)
    except BaseException as error:
        print("Unknown error while querying: " + error.response['Error']['Message'])



# Operation#1 = Update account balance
#               Upd
#(LAST_ACCOUNT_TXN_NUMBER, LATEST_TXN_NUMBER,TXN_DATE,TXN_TYPE,TXN_AMOUNT )
def create_transact_write_items_input(cust_number, acct_number,last_account_txn_number, latest_txn_number,txn_date,txn_type,txn_amount):
    return {
        "TransactItems": [
            {
                "Update": {
                    "TableName": TABLE_NAME,
                    "Key": {
                        "PK": {"S":cust_number}, 
                        "SK": {"S":acct_number}
                    },
                    "UpdateExpression": "SET #acct_balance = #acct_balance + :txn_amount, #acct_last_txn=:latest_txn_number",
                    "ConditionExpression": "attribute_exists(#sk) And #acct_last_txn = :acct_last_txn",
                    "ExpressionAttributeNames": {"#acct_balance":"acct_balance","#sk":"SK","#acct_balance":"acct_balance","#acct_last_txn": "acct_last_txn"},
                    "ExpressionAttributeValues": {":txn_amount": {"N":txn_amount},":acct_last_txn": {"N":last_account_txn_number},":latest_txn_number":{"N":latest_txn_number}}
                }
            },
            {
                "Update": {
                    "TableName": TABLE_NAME,
                    "Key": {
                        "PK": {"S":latest_txn_number}, 
                        "SK": {"S":acct_number}
                    },
                    "UpdateExpression": "SET #txn_amount = :txn_amount, #txn_date = :txn_date, #txn_type = :txn_type, #GSI1_PK = :GSI1_PK, #GSI1_SK = :GSI1_SK",
                    "ConditionExpression": "attribute_not_exists(#PK) And attribute_not_exists(#SK)",
                    "ExpressionAttributeNames": {"#txn_amount":"txn_amount","#txn_date":"txn_date","#txn_type":"txn_type","#GSI1_PK":"GSI1_PK","#GSI1_SK":"GSI1_SK","#PK":"PK","#SK":"SK"},
                    "ExpressionAttributeValues": {":txn_amount": {"N":txn_amount},":txn_date": {"S":txn_date},":txn_type": {"S":txn_type},":GSI1_PK": {"S":txn_date},":GSI1_SK": {"S":acct_number}}
                }
            }
        ]
    }


def execute_transact_write_items(dynamodb_client, input):
    try:
        response = dynamodb_client.transact_write_items(**input)
        print("TransactWriteItems executed successfully.")
        # Handle response
    except ClientError as error:
        handle_error(error)
    except BaseException as error:
        print("Unknown error executing TransactWriteItem operation: " +
              error.response['Error']['Message'])


def handle_error(error):
    error_code = error.response['Error']['Code']
    error_message = error.response['Error']['Message']

    error_help_string = ERROR_HELP_STRINGS[error_code]

    print('[{error_code}] {help_string}. Error message: {error_message}'
          .format(error_code=error_code,
                  help_string=error_help_string,
                  error_message=error_message))


def main():
    # Create the DynamoDB Client with the region you want
    dynamodb_client = create_dynamodb_client()

    # 1. Create the account query input
    query_input = create_account_query_input(CUST_NUMBER, ACCT_NUMBER)
    # 2. Run the query
    account_info = execute_account_query(dynamodb_client, query_input)
    # 3. Get the balance & last txn number
    LAST_ACCOUNT_TXN_NUMBER=account_info['Items'][0]['acct_last_txn']['N']
    ACCT_BALANCE=account_info['Items'][0]['acct_balance']['N']
    print("Query Sucessful :   Acct Balance = {},  Last Txn Number = {}".format(ACCT_BALANCE,LAST_ACCOUNT_TXN_NUMBER))
    
    # 4. Next txn number
    LATEST_TXN_NUMBER=int(LAST_ACCOUNT_TXN_NUMBER)+1

    # 5. Create the dictionary containing arguments for transact_write_items call
    transact_write_items_input = create_transact_write_items_input(CUST_NUMBER,ACCT_NUMBER,LAST_ACCOUNT_TXN_NUMBER, str(LATEST_TXN_NUMBER),TXN_DATE,TXN_TYPE,TXN_AMOUNT )

    print(transact_write_items_input)

    # 6. Call DynamoDB's transact_write_items API
    execute_transact_write_items(dynamodb_client, transact_write_items_input)


if __name__ == "__main__":
    main()
