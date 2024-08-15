# ScoutMerge
ScoutMerge is an extension for the cloud auditing tool ScoutSuite. When working with large cloud environments with hundreds, if not thousands, of projects(GCP)/accounts(AWS), cloud auditing tools such as ScoutSuite break due to the large amount of data they have to handle. ScoutMerge allows you to run the 'scout' command per project then proceeds to aggregate the results for you in one text file that shows each affected project/account for each ScoutSuite finding, if any.

### Supported Cloud Providers
- AWS
- GCP

# Usage
**Requirements:** See ScoutSuite [wiki](https://github.com/nccgroup/ScoutSuite/wiki/Setup)

### AWS
1. Authenticate and run ScoutSuite for each AWS account in scope. Save all output in one main directory
2. Run the `aws.py` script with the the `-d` flag pointing to the main directory with the scoutsuite output. It is assumed that your directory structure is as follows:

```
> tree -L 1
scoutsuite_output_directory
├── backup-us-pre
├── backup-us-prod
├── datalake-us-pre`
├── datalake-us-prod
├── command-central-us-pre
├── command-central-us-prod
├── failure-mb-us-pre
├── failure-mb-us-prod
├── compliance-dev
└── compliance-us-prod
```

### GCP
For GCP, the script takes a Folder ID as input, finds all projects in specified folder as well as subfolders, runs the `scout` command on each project found, then proceeds to aggregate the results into one text file.
1. Authenticate with `gcloud`
2. Do not set default project
3. Run `gcp.py` with the `-f` flag for the Folder ID housing the projects in scope

## Feature Roadmap
&#9745; GCP

&#9745; AWS

&#9744; Azure