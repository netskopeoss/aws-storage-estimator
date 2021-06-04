# aws-s3-scanner

```
usage: netskope-scanner.py [-h] [--config FILE] [--write FILE] [--test] [--org] [--maxsize BYTES] [--minsize BYTES] [--allowext EXT [EXT ...]] [--blockext EXT [EXT ...]]
                           [--include ACCOUNTID [ACCOUNTID ...]] [--exclude ACCOUNTID [ACCOUNTID ...]]

optional arguments:
  -h, --help            show this help message and exit
  --config FILE, -c FILE
                        Configuration JSON file with script options
  --write FILE, -w FILE
                        Output JSON file to write with results
  --test, -t            Do not iteratively scan buckets for testing
  --org, -o             Scan for accounts in the organization
  --maxsize BYTES, -x BYTES
                        Maximum size file allowed in scan
  --minsize BYTES, -n BYTES
                        Minimum size file allowed in scan
  --allowext EXT [EXT ...], -a EXT [EXT ...]
                        List of extensions allowed in scan
  --blockext EXT [EXT ...], -b EXT [EXT ...]
                        List of extensions excluded from scan
  --include ACCOUNTID [ACCOUNTID ...], -i ACCOUNTID [ACCOUNTID ...]
                        List of accounts included in scan
  --exclude ACCOUNTID [ACCOUNTID ...], -e ACCOUNTID [ACCOUNTID ...]
                        List of accounts excluded from scan
```

## Installing

Python3.6 or later is required

pip3 install -r requirements.txt

This script expects that AWS credentials are accessible to the AWS boto3 python module.
* By exporting AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY to the shell environment variables
* By using the AWS shared credential file (~/.aws/credentials)
* By using awscli configure and the AWS config file (~/.aws/config)
* By using the boto.cfg file (/etc/boto.cfg, ~/.boto)

See https://boto3.amazonaws.com/v1/documentation/api/latest/guide/quickstart.html#installation for more information.

## Running

With no options, this script will attach to the account with supplied credentials and 
look at every S3 bucket in the account.  (First time run may benefit from --test option to perform shallow 
scans of the S3 buckets if there are a large number of them to make sure accessibility isn't an issue.) 

It won't scan empty files or files bigger than 32MB by default.  The options --maxsize and --minsize will 
change this behavior.

If using --org to run for the organization, it will include all accounts in the org.  This can be
overriden with --include or --exclude flags which take a list of account IDs each.

In order to scan an entire organization, this script must run under the master account or 
a delegated account that can access AssumeRole for the each accounts IAM role OrganizationAccountAccessRole.

Output is in JSON format and sent to STDOUT by default.  To write a file use the --write /path/to/file.json option.

This script will read a JSON configuration file of options, and several examples are in the config directory

## Examples

There is a folder called config with example JSON configurations
