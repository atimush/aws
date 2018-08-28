## AWS Automation Tools

### EC2:
* [migrate_security_groups.py](EC2/migrate_security_groups.py) - Automatic Migration/Synchronization of Security Groups between Regions/VPCs.
* [ebs_snaphots.py](EC2/ebs_snapshots.py) - Automatic EBS snapshotting defined by custom retention policies.

### Cloud Formation:
* [ebs_snapshots.yaml](CloudFormation/ebs_snapshots.yaml) - Auto provisioning of EC2: [ebs_snaphots.py](EC2/ebs_snaphots.py).
