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
