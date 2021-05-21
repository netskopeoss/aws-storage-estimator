#!/usr/bin/python3
import boto3, botocore
import sys, pathlib, argparse
import json


def listAccountsInOrg(organizations):
    account_list = []
   
    ### Try to get the accounts from the organization.  If we don't have privilege, we'll have to return no accounts
    try:
        response = organizations.list_accounts()
    except botocore.exceptions.ClientError as error:
        file_stats['errors'].append("Couldn't list accounts in organization ("+str(error)+")")
        response = None
        pass

    ### Didn't or couldn't receive accounts
    if not response or 'Accounts' not in response:
        return account_list

    for account in response['Accounts']:
        account_list.append(account)

    ### If AWS NextToken is not set, then there are no further results
    if 'NextToken' not in response:
        return account_list

    ### Keep looking for accounts while NextToken is set
    while response['NextToken']:
        next_token = response['NextToken']
        response = organizations.list_accounts(NextToken=next_token)

        for account in response['Accounts']:
            account_list.append(account)

    return account_list


def filterObjects(object_list, accountId, bucketName, filter_list):
    for obj in object_list:
        ### Obtain extension from the filename
        file_extension = pathlib.Path(obj['Key']).suffix.strip('.').lower()

        if options.debug: oprint(str(obj['Size'])+" "+obj['Key']+" ("+file_extension+")")

        ### Apply filters to file and move on if file properties do not match
        if obj['Size'] > filter_list.maxsize:
            continue
        if obj['Size'] < filter_list.minsize:
            continue
        if filter_list.allowext and file_extension not in filter_list.allowext:
            continue
        if filter_list.blockext and file_extension in filter_list.blockext:
            continue

        ### Setup counters for overall totals
        if file_extension not in file_stats['total']['size.ext']:
            file_stats['total']['size.ext'][file_extension] = 0

        if file_extension not in file_stats['total']['files.ext']:
            file_stats['total']['files.ext'][file_extension] = 0

        ### Increment overall counters
        file_stats['total']['size'] += obj['Size']
        file_stats['total']['files'] += 1
        file_stats['total']['size.ext'][file_extension] += obj['Size']
        file_stats['total']['files.ext'][file_extension] += 1

        ### Setup counters for per-account totals
        if file_extension not in file_stats['account'][accountId]['size.ext']:
            file_stats['account'][accountId]['size.ext'][file_extension] = 0

        if file_extension not in file_stats['account'][accountId]['files.ext']:
            file_stats['account'][accountId]['files.ext'][file_extension] = 0

        ### Increment per-account counters
        file_stats['account'][accountId]['size'] += obj['Size']
        file_stats['account'][accountId]['files'] += 1
        file_stats['account'][accountId]['size.ext'][file_extension] += obj['Size']
        file_stats['account'][accountId]['files.ext'][file_extension] += 1

        ### Setup counters for per-account, per-bucket totals
        if file_extension not in file_stats['account.bucket'][accountId][bucketName]['size.ext']:
            file_stats['account.bucket'][accountId][bucketName]['size.ext'][file_extension] = 0

        if file_extension not in file_stats['account.bucket'][accountId][bucketName]['files.ext']:
            file_stats['account.bucket'][accountId][bucketName]['files.ext'][file_extension] = 0

        ### Increment per-account, per-bucket counters
        file_stats['account.bucket'][accountId][bucketName]['size'] += obj['Size']
        file_stats['account.bucket'][accountId][bucketName]['files'] += 1
        file_stats['account.bucket'][accountId][bucketName]['size.ext'][file_extension] += obj['Size']
        file_stats['account.bucket'][accountId][bucketName]['files.ext'][file_extension] += 1

    return


def listObjectsInBucket(s3, accountId, bucketName, filter_list):
    ### Try to list the objects in the bucket
    try:
        response = s3.list_objects_v2(Bucket=bucketName)
    except botocore.exceptions.ClientError as error:
        file_stats['errors'].append("Couldn't get bucket objects for account:"+accountId+", bucket:"+bucketName+" ("+str(error)+")")
        response = None
        pass

    ### If the bucket was empty or we couldn't list objects, then we have to return
    if not response or 'Contents' not in response:
        return

    ### Pass contents of the bucket to our filter to find files that match
    filterObjects(response['Contents'],accountId,bucketName,filter_list)

    ### If AWS IsTruncated is set, then there are more results to gather
    while response['IsTruncated']:
        oprint(".",end='',flush=True)

        ### If we are in test mode, then stop iterating further results
        if filter_list.test:
            break

        ### Token used to request further results
        continuation_token = response['NextContinuationToken']

        ### Continue listing the bucket
        response = s3.list_objects_v2(Bucket=bucketName,ContinuationToken=continuation_token)

        ### Pass contents of the bucket to our filter to find files that match
        filterObjects(response['Contents'],accountId,bucketName,filter_list)

    return


def listBuckets(s3):
    ### Get buckets from account
    try:
        response = s3.list_buckets()
    except botocore.exceptions.ClientError as error:
        file_stats['errors'].append("Couldn't list buckets for account:"+accountId+" ("+str(error)+")")
        response = None
        pass

    return response['Buckets'] if 'Buckets' in response else {}


def getOptions():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quiet", "-q", help="Suppress all output", action='store_true', default=False, required=False)
    parser.add_argument("--debug", "-d", help="Enable debugging mode", action='store_true', default=False, required=False)
    parser.add_argument("--config", "-c", help="Configuration JSON file with script options", metavar='FILE', type=str, required=False)
    parser.add_argument("--write", "-w", help="Output JSON file to write with results", metavar='FILE', type=str, required=False)
    parser.add_argument("--test", "-t", help="Do not iteratively scan buckets for testing", action='store_true', default=False, required=False)
    parser.add_argument("--org", "-o", help="Scan for accounts in the organization", action='store_true', default=False, required=False)
    parser.add_argument("--maxsize", "-x", help="Maximum size file allowed in scan", metavar='BYTES', type=int, default=33554432, required=False)
    parser.add_argument("--minsize", "-n", help="Minimum size file allowed in scan", metavar='BYTES', type=int, default=1, required=False)
    parser.add_argument("--allowext", "-a", help="List of extensions allowed in scan", metavar='EXT', type=str, nargs='+', default=[], required=False)
    parser.add_argument("--blockext", "-b", help="List of extensions excluded from scan", metavar='EXT', type=str, nargs='+', default=[], required=False)
    parser.add_argument("--include", "-i", help="List of accounts included in scan", metavar='ACCOUNTID', type=str, nargs='+', default=[], required=False)
    parser.add_argument("--exclude", "-e", help="List of accounts excluded from scan", metavar='ACCOUNTID', type=str, nargs='+', default=[], required=False)

    args = parser.parse_args()

    ### If we were provided a json config file, then start baseline arguments and override with file options
    if args.config and pathlib.Path(args.config).is_file():
        with open(args.config) as f:
              json_args = json.load(f)
              vargs = vars(args)
              dargs = {**vargs, **json_args}
              args  = argparse.Namespace(**dargs)

    return args


def oprint(data='', **kwargs):
    if not options.quiet: print(data,**kwargs)


### MAIN ###==============================================================

if __name__ == "__main__":

    file_stats    = {'errors':[], 'total':{'size':0, 'files':0, 'size.ext':{}, 'files.ext':{}}, 'account':{}, 'account.bucket':{}}
    options       = getOptions()
    sts           = boto3.client('sts')
    organizations = boto3.client('organizations')
    
    try:
        myId = sts.get_caller_identity().get('Account')
    except botocore.exceptions.ClientError as error:
        raise error

    accounts = listAccountsInOrg(organizations) if options.org else [{'Id':myId}]

    oprint(options)

    ### Iterate through each account (or current account if not using organizations)
    for account in accounts:
        accountId = account['Id']

        ### Skip accounts that are not in the inclusion list
        if options.include and accountId not in options.include:
            continue

        ### Skip accounts that are in the exclusion list
        if options.exclude and accountId in options.exclude:
            continue

        ### Reset counters for account and initialize account/bucket statistics
        file_stats['account'][accountId]        = {'size':0, 'files':0, 'size.ext':{}, 'files.ext':{}}
        file_stats['account.bucket'][accountId] = {}

        oprint("Account: "+accountId)

        ### If accountId is our own, then we didn't (was not asked to do so) or couldn't enumerate the organizationa for assumed roles
        if accountId == myId:
            s3 = boto3.client('s3')
        else:
            assumed_role = None

            ### Attempt to assume role to obtain credentials for account requested
            try:
                assumed_role = sts.assume_role(RoleArn="arn:aws:iam::"+accountId+":role/OrganizationAccountAccessRole",RoleSessionName="NetskopeScan")
            except botocore.exceptions.ClientError as error:
                file_stats['error'].append("Couldn't assume role for account "+accountId+" ("+str(error)+")")
                pass

            ### If we didn't get an assumed role object back, move on
            if not assumed_role:
                continue

            ### Obtain the credentials from the assumed role object
            credentials = assumed_role['Credentials']

            ### Active S3 client with credentials
            s3 = boto3.client('s3',aws_access_key_id=credentials['AccessKeyId'],aws_secret_access_key=credentials['SecretAccessKey'],\
                                   aws_session_token=credentials['SessionToken'])

        ### Iterate over each bucket in the account S3
        for bucket in listBuckets(s3):
            bucketName = bucket['Name']

            ### Reset counters for account/bucket statistics
            file_stats['account.bucket'][accountId][bucketName] = {'size':0, 'files':0, 'size.ext':{}, 'files.ext':{}}

            oprint(' + '+bucketName+'...',end='')
            listObjectsInBucket(s3,accountId,bucketName,options)
            oprint()

    if options.write:
        with open(options.write,'w') as outfile:
            json.dump(file_stats,outfile)
    else:
        print(json.dumps(file_stats))


