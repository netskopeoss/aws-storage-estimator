#!/usr/bin/python3
import boto3, botocore
import sys, pathlib, argparse
import json
import csv


def list_accounts_in_org(organizations):
	account_list = []
   
	# Try to get the accounts from the organization.  If we don't have privilege, we'll have to return no accounts
	try:
		response = organizations.list_accounts()
	except botocore.exceptions.ClientError as error:
		file_stats['errors'].append("Couldn't list accounts in organization ("+str(error)+")")
		response = None
		pass

	# Didn't or couldn't receive accounts
	if not response or 'Accounts' not in response:
		return account_list

	for account in response['Accounts']:
		account_list.append(account)

	# If AWS NextToken is not set, then there are no further results
	if 'NextToken' not in response:
		return account_list

	# Keep looking for accounts while NextToken is set
	while response['NextToken']:
		next_token = response['NextToken']
		response = organizations.list_accounts(NextToken=next_token)

		for account in response['Accounts']:
			account_list.append(account)

		if 'NextToken' not in response:
			break

	return account_list


def filter_objects(object_list, account_id, bucket_name, filter_list):
	for obj in object_list:
		# Obtain extension from the filename
		file_extension = pathlib.Path(obj['Key']).suffix.strip('.').lower()

		if options.debug: oprint(str(obj['Size'])+" "+obj['Key']+" ("+file_extension+")")

		# Apply filters to file and move on if file properties do not match
		if obj['Size'] > filter_list.maxsize:
			continue
		if obj['Size'] < filter_list.minsize:
			continue
		if filter_list.allowext and file_extension not in filter_list.allowext:
			continue
		if filter_list.blockext and file_extension in filter_list.blockext:
			continue

		# Setup counters for overall totals
		if file_extension not in file_stats['total']['size.ext']:
			file_stats['total']['size.ext'][file_extension] = 0

		if file_extension not in file_stats['total']['files.ext']:
			file_stats['total']['files.ext'][file_extension] = 0

		# Increment overall counters
		file_stats['total']['size'] += obj['Size']
		file_stats['total']['files'] += 1
		file_stats['total']['size.ext'][file_extension] += obj['Size']
		file_stats['total']['files.ext'][file_extension] += 1

		# Setup counters for per-account totals
		if file_extension not in file_stats['account'][account_id]['size.ext']:
			file_stats['account'][account_id]['size.ext'][file_extension] = 0

		if file_extension not in file_stats['account'][account_id]['files.ext']:
			file_stats['account'][account_id]['files.ext'][file_extension] = 0

		# Increment per-account counters
		file_stats['account'][account_id]['size'] += obj['Size']
		file_stats['account'][account_id]['files'] += 1
		file_stats['account'][account_id]['size.ext'][file_extension] += obj['Size']
		file_stats['account'][account_id]['files.ext'][file_extension] += 1

		# Setup counters for per-account, per-bucket totals
		if file_extension not in file_stats['account.bucket'][account_id][bucket_name]['size.ext']:
			file_stats['account.bucket'][account_id][bucket_name]['size.ext'][file_extension] = 0

		if file_extension not in file_stats['account.bucket'][account_id][bucket_name]['files.ext']:
			file_stats['account.bucket'][account_id][bucket_name]['files.ext'][file_extension] = 0

		# Increment per-account, per-bucket counters
		file_stats['account.bucket'][account_id][bucket_name]['size'] += obj['Size']
		file_stats['account.bucket'][account_id][bucket_name]['files'] += 1
		file_stats['account.bucket'][account_id][bucket_name]['size.ext'][file_extension] += obj['Size']
		file_stats['account.bucket'][account_id][bucket_name]['files.ext'][file_extension] += 1

	return


def list_objects_in_bucket(s3, account_id, bucket_name, filter_list):
	# Try to list the objects in the bucket
	try:
		response = s3.list_objects_v2(Bucket=bucket_name)
	except botocore.exceptions.ClientError as error:
		file_stats['errors'].append("Couldn't get bucket objects for account:"+account_id+", bucket:"+bucket_name+" ("+str(error)+")")
		response = None
		pass

	# If the bucket was empty or we couldn't list objects, then we have to return
	if not response or 'Contents' not in response:
		return

	# Pass contents of the bucket to our filter to find files that match
	filter_objects(response['Contents'],account_id,bucket_name,filter_list)

	# If AWS IsTruncated is set, then there are more results to gather
	while response['IsTruncated']:
		oprint(".",end='',flush=True)

		# If we are in test mode, then stop iterating further results
		if filter_list.test:
			break

		# Token used to request further results
		continuation_token = response['NextContinuationToken']

		# Continue listing the bucket
		response = s3.list_objects_v2(Bucket=bucket_name,ContinuationToken=continuation_token)

		# Pass contents of the bucket to our filter to find files that match
		filter_objects(response['Contents'],account_id,bucket_name,filter_list)

	return


def list_buckets(s3):
	# Get buckets from account
	try:
		response = s3.list_buckets()
	except botocore.exceptions.ClientError as error:
		file_stats['errors'].append("Couldn't list buckets for account:"+account_id+" ("+str(error)+")")
		response = None
		pass

	if response is None:
		return {}

	return response['Buckets'] if 'Buckets' in response else {}


def get_options():
	parser = argparse.ArgumentParser(allow_abbrev=False)
	parser.add_argument("--quiet", "-q", help="Suppress all output", action='store_true', default=False, required=False)
	parser.add_argument("--debug", "-d", help="Enable debugging mode", action='store_true', default=False, required=False)
	parser.add_argument("--config", "-c", help="Configuration JSON file with script options", metavar='FILE', type=str, required=False)
	parser.add_argument("--json", help="Output JSON file to write with results", metavar='FILE', type=str, required=False)
	parser.add_argument("--csv", help="Output CSV file to write with results", metavar='FILE', type=str, required=False)
	parser.add_argument("--summary", "-s", help="Summary only of accounts and buckets, does not enumerate bucket contents", action='store_true', default=False, required=False)
	parser.add_argument("--test", "-t", help="Do not iteratively scan buckets for testing", action='store_true', default=False, required=False)
	parser.add_argument("--org", "-o", help="Scan for accounts in the organization", action='store_true', default=False, required=False)
	parser.add_argument("--role", "-r", help="Role to use for AssumeRole, defaults to OrganizationAccountAccessRole", metavar='ASSUME_ROLE', type=str, default="OrganizationAccountAccessRole", required=False)
	parser.add_argument("--maxsize", "-x", help="Maximum size file allowed in scan", metavar='BYTES', type=int, default=33554432, required=False)
	parser.add_argument("--minsize", "-n", help="Minimum size file allowed in scan", metavar='BYTES', type=int, default=1, required=False)
	parser.add_argument("--allowext", "-a", help="List of extensions allowed in scan", metavar='EXT', type=str, nargs='+', default=[], required=False)
	parser.add_argument("--blockext", "-b", help="List of extensions excluded from scan", metavar='EXT', type=str, nargs='+', default=[], required=False)
	parser.add_argument("--include", "-i", help="List of accounts included in scan", metavar='ACCOUNTID', type=str, nargs='+', default=[], required=False)
	parser.add_argument("--exclude", "-e", help="List of accounts excluded from scan", metavar='ACCOUNTID', type=str, nargs='+', default=[], required=False)

	if len(sys.argv) < 2:
		parser.print_usage()
		sys.exit(1)

	args = parser.parse_args()

	# If we were provided a json config file, then start baseline arguments and override with file options
	if args.config and pathlib.Path(args.config).is_file():
		with open(args.config) as f:
			  json_args = json.load(f)
			  vargs = vars(args)
			  dargs = {**vargs, **json_args}
			  args  = argparse.Namespace(**dargs)

	return args


def oprint(data='', **kwargs):
	if not options.quiet: print(data,**kwargs)

def ocsv(data):
	file_exts = {}
	csv       = []
	for account in data['account.bucket']:
		for bucket in data['account.bucket'][account]:
			for file_ext in data['account.bucket'][account][bucket]['size.ext']:
				if file_ext not in file_exts:
					file_exts[file_ext] = 0
				file_exts[file_ext] += 1

	for account in data['account.bucket']:
		for bucket in data['account.bucket'][account]:
			row = {'account':account, 'bucket':bucket}
			for file_ext in file_exts:
				if file_ext in data['account.bucket'][account][bucket]['size.ext']:
					row['bytes_'+file_ext]= data['account.bucket'][account][bucket]['size.ext'][file_ext]
				else:
					row['bytes_'+file_ext] = 0
			csv.append(row)
	return csv
	


# MAIN #==============================================================

if __name__ == "__main__":


	file_stats    = {'errors':[], 'total':{'size':0, 'files':0, 'size.ext':{}, 'files.ext':{}}, 'account':{}, 'account.bucket':{}}
	options       = get_options()
	sts           = boto3.client('sts')
	organizations = boto3.client('organizations')

	if not options.json or not options.csv:
		options.json = 'output.json'

	try:
		my_id = sts.get_caller_identity().get('Account')
	except botocore.exceptions.ClientError as error:
		raise error

	accounts = list_accounts_in_org(organizations) if options.org else [{'Id':my_id}]

	#oprint(options)

	oprint("Accounts found: " + str(len(accounts)))

	# Iterate through each account (or current account if not using organizations)
	for account in accounts:
		account_id = account['Id']

		# Skip accounts that are not in the inclusion list
		if options.include and account_id not in options.include:
			continue

		# Skip accounts that are in the exclusion list
		if options.exclude and account_id in options.exclude:
			continue

		# Reset counters for account and initialize account/bucket statistics
		file_stats['account'][account_id]        = {'size':0, 'files':0, 'size.ext':{}, 'files.ext':{}}
		file_stats['account.bucket'][account_id] = {}

		oprint("Account: " + account_id)

		# If account_id is our own, then we didn't (was not asked to do so) or couldn't enumerate the organizationa for assumed roles
		if account_id == my_id:
			s3 = boto3.client('s3')
		else:
			assumed_role = None

			# Attempt to assume role to obtain credentials for account requested
			try:
				assumed_role = sts.assume_role(RoleArn="arn:aws:iam::"+account_id+":role/"+options.role,RoleSessionName="NetskopeScan")
			except botocore.exceptions.ClientError as error:
				file_stats['errors'].append("Couldn't assume role for account "+account_id+" ("+str(error)+")")
				pass

			# If we didn't get an assumed role object back, move on
			if not assumed_role:
				oprint(" - couldn't assume role for this account")
				continue

			# Obtain the credentials from the assumed role object
			credentials = assumed_role['Credentials']

			# Active S3 client with credentials
			s3 = boto3.client('s3',aws_access_key_id=credentials['AccessKeyId'],aws_secret_access_key=credentials['SecretAccessKey'],\
								   aws_session_token=credentials['SessionToken'])

		if options.summary:
			buckets = list_buckets(s3)
			oprint(" - total buckets: " + str(len(buckets)))
			continue

		# Iterate over each bucket in the account S3
		for bucket in list_buckets(s3):
			bucket_name = bucket['Name']

			# Reset counters for account/bucket statistics
			file_stats['account.bucket'][account_id][bucket_name] = {'size':0, 'files':0, 'size.ext':{}, 'files.ext':{}}

			oprint(' + '+bucket_name+'...',end='')
			list_objects_in_bucket(s3,account_id,bucket_name,options)
			oprint()

	if options.json:
		with open(options.json,'w') as outfile:
			json.dump(file_stats,outfile,indent=4,sort_keys=True)

	if options.csv:
		csv_data = ocsv(file_stats)
		if csv_data:
			with open(options.csv,'w') as outfile:
				writer = csv.DictWriter(outfile,fieldnames=csv_data[0].keys())
				writer.writeheader()
				for row in csv_data:
					writer.writerow(row)


